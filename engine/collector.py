"""
Multi-source High-Intent Signal & Competitor Intelligence Collector.
Enforces production invariants:
- Per-source timeout isolation & bounded retry with jitter + Retry-After compliance
- Primary-key deduplication by source_id + normalized URL
- Verbatim evidence quote & provenance preservation
"""

import concurrent.futures
import hashlib
import html
import logging
import random
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Collector")

DEFAULT_TIMEOUT = 8
HEADERS = {
    "User-Agent": "IntentRadar-VerificationEngine/2.6 (+https://github.com/jakelihua/intent-radar-preview)"
}


def normalize_url(url: str) -> str:
    """Normalizes URLs for secondary deduplication by stripping fragments and tracking query params."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        filtered_q = [
            (k, v)
            for k, v in query_pairs
            if not k.lower().startswith(("utm_", "ref", "fbclid", "gclid"))
        ]
        clean_query = urllib.parse.urlencode(sorted(filtered_q))
        return urllib.parse.urlunsplit((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            clean_query,
            "",
        ))
    except Exception:
        return url.strip()


def request_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 2,
) -> Optional[requests.Response]:
    """Bounded HTTP GET with jittered exponential backoff and Retry-After header support."""
    req_headers = {**HEADERS, **(headers or {})}
    for attempt in range(max_retries + 1):
        try:
            res = requests.get(url, params=params, headers=req_headers, timeout=timeout)
            if res.status_code == 200:
                return res
            if res.status_code in (429, 502, 503, 504) and attempt < max_retries:
                retry_after = res.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_sec = min(float(retry_after), 5.0)
                else:
                    wait_sec = (0.4 * (2 ** attempt)) + random.uniform(0.05, 0.25)
                time.sleep(wait_sec)
                continue
            logger.warning(f"Source {url} returned HTTP {res.status_code}")
            return res
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep((0.3 * (2 ** attempt)) + random.uniform(0.05, 0.2))
            else:
                logger.warning(f"Source request failed after {max_retries + 1} attempts ({url}): {e}")
    return None


def strip_html_tags(raw: str) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<p>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class IntentSignal:
    def __init__(
        self,
        title: str,
        url: str,
        source: str,
        content: str = "",
        author: str = "Unknown",
        keyword: str = "",
        timestamp: Optional[str] = None,
        comments_count: int = 0,
        engagement_metric: str = "",
        source_id: Optional[str] = None,
        collected_at: Optional[str] = None,
        evidence_quote: Optional[str] = None,
        qualification_meta: Optional[Dict[str, Any]] = None,
    ):
        self.title = title.strip()
        self.url = url.strip()
        self.source = source
        self.content = content.strip()
        self.author = author
        self.keyword = keyword
        self.timestamp = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        self.collected_at = collected_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        self.comments_count = comments_count
        self.engagement_metric = engagement_metric
        self.source_id = source_id or hashlib.md5(f"{self.source}:{normalize_url(self.url)}".encode("utf-8")).hexdigest()[:12]
        self.id = str(source_id) if source_id else hashlib.md5(f"{self.source}:{self.source_id}".encode("utf-8")).hexdigest()[:12]
        self.evidence_quote = (evidence_quote or self.content or self.title).strip()[:320]
        raw_qm = dict(qualification_meta or {})
        for k in ("team_scale", "budget_status", "decision_authority", "migration_urgency"):
            if isinstance(raw_qm.get(k), dict):
                item = dict(raw_qm[k])
                src_val = item.get("source") or item.get("provenance") or "未知"
                item["source"] = src_val
                item["provenance"] = src_val
                raw_qm[k] = item
        if isinstance(raw_qm.get("blocking_conditions"), str):
            raw_qm["blocking_conditions"] = [raw_qm["blocking_conditions"]]
        self.qualification_meta = raw_qm

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "content": self.content,
            "evidence_quote": self.evidence_quote,
            "author": self.author,
            "keyword": self.keyword,
            "timestamp": self.timestamp,
            "collected_at": self.collected_at,
            "comments_count": self.comments_count,
            "engagement_metric": self.engagement_metric,
            "qualification_meta": self.qualification_meta,
        }


class HackerNewsCollector:
    """Collects buying intent & competitor discussions from Hacker News via Algolia API."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://hn.algolia.com/api/v1/search_by_date"

    def fetch(self, query: str, limit: int = 5) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {
            "query": query,
            "tags": "(story,ask_hn)",
            "hitsPerPage": limit,
        }
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout)
        if res and res.status_code == 200:
            data = res.json()
            for hit in data.get("hits", []):
                obj_id = str(hit.get("objectID") or "")
                title = hit.get("title") or ""
                if title.lower().startswith(("show hn:", "launch hn:")):
                    continue
                url = f"https://news.ycombinator.com/item?id={obj_id}" if obj_id else (hit.get("url") or "")
                raw_story = strip_html_tags(hit.get("story_text") or hit.get("comment_text") or "")
                content = raw_story if raw_story else title
                author = hit.get("author") or "HN User"
                points = hit.get("points") or 0
                num_comments = hit.get("num_comments") or 0
                ts = (hit.get("created_at") or "")[:16].replace("T", " ") + " UTC"

                engagement = []
                if points:
                    engagement.append(f"🔥 {points} 点赞")
                if num_comments:
                    engagement.append(f"💬 {num_comments} 条讨论")
                engagement_metric = " · ".join(engagement) if engagement else "⚡ 社区新帖"

                if title and url:
                    signals.append(
                        IntentSignal(
                            title=title,
                            url=url,
                            source="Hacker News",
                            content=content[:600],
                            author=author,
                            keyword=query,
                            timestamp=ts,
                            comments_count=num_comments,
                            engagement_metric=engagement_metric,
                            source_id=f"hn_{obj_id}" if obj_id else None,
                            evidence_quote=raw_story[:280] if raw_story else title,
                        )
                    )
        return signals


class GitHubCollector:
    """Collects real engineering team migration & tool replacement discussions from GitHub Issues."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://api.github.com/search/issues"

    def fetch(self, query: str, limit: int = 5) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {
            "q": f"{query} is:issue",
            "sort": "updated",
            "order": "desc",
            "per_page": limit,
        }
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout)
        if res and res.status_code == 200:
            items = res.json().get("items", [])
            for item in items:
                issue_id = str(item.get("id") or "")
                title = item.get("title") or ""
                url = item.get("html_url") or ""
                comments = item.get("comments", 0)
                body = re.sub(r"\s+", " ", (item.get("body") or "")).strip()[:500]
                author = item.get("user", {}).get("login", "GitHub User")
                if title and url:
                    signals.append(
                        IntentSignal(
                            title=title,
                            url=url,
                            source="GitHub Issues",
                            content=body or title,
                            author=author,
                            keyword=query,
                            timestamp=(item.get("updated_at") or "")[:16].replace("T", " ") + " UTC",
                            comments_count=comments,
                            engagement_metric=f"💬 {comments} 条技术讨论",
                            source_id=f"gh_{issue_id}" if issue_id else None,
                            evidence_quote=body[:260] if body else title,
                        )
                    )
        return signals


class DevToCollector:
    """Collects software alternative guides & developer migration discussions from Dev.to API."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://dev.to/api/articles"

    def fetch(self, tag: str = "alternative", limit: int = 5) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {"tag": tag, "per_page": limit}
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout)
        if res and res.status_code == 200:
            for item in res.json():
                art_id = str(item.get("id") or "")
                title = item.get("title") or ""
                url = item.get("url") or ""
                desc = item.get("description") or title
                author = item.get("user", {}).get("username", "Dev.to Author")
                comments = item.get("comments_count", 0)
                reactions = item.get("positive_reactions_count", 0)
                ts = (item.get("published_at") or "")[:16].replace("T", " ") + " UTC"
                if title and url:
                    signals.append(
                        IntentSignal(
                            title=title,
                            url=url,
                            source="Dev.to",
                            content=desc,
                            author=author,
                            keyword=tag,
                            timestamp=ts,
                            comments_count=comments,
                            engagement_metric=f"💬 {comments} 讨论 · 👍 {reactions} 赞同",
                            source_id=f"devto_{art_id}" if art_id else None,
                            evidence_quote=desc[:260],
                        )
                    )
        return signals


class GoogleNewsRSSCollector:
    """Collects competitor pricing backlash & announcements via Google News RSS."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://news.google.com/rss/search"

    def fetch(self, query: str, limit: int = 5, lang: str = "en") -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        encoded_q = urllib.parse.quote(query)
        if lang == "zh":
            url = f"{self.base_url}?q={encoded_q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        else:
            url = f"{self.base_url}?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"

        res = request_with_retry(url, timeout=self.timeout)
        if res and res.status_code == 200:
            try:
                root = ET.fromstring(res.content)
                items = root.findall(".//item")
                for it in items[:limit]:
                    title_elem = it.find("title")
                    link_elem = it.find("link")
                    pub_date = it.find("pubDate")
                    desc_elem = it.find("description")

                    title = title_elem.text if title_elem is not None else ""
                    link = link_elem.text if link_elem is not None else ""
                    content = strip_html_tags(desc_elem.text if desc_elem is not None else "")
                    ts = pub_date.text if pub_date is not None else None

                    if title and link:
                        signals.append(
                            IntentSignal(
                                title=title,
                                url=link,
                                source="Google News RSS",
                                content=content[:500],
                                author="News Media",
                                keyword=query,
                                timestamp=ts,
                                comments_count=0,
                                engagement_metric="📰 行业媒体报道",
                            )
                        )
            except Exception as e:
                logger.warning(f"Error parsing Google News RSS XML: {e}")
        return signals


class V2EXCollector:
    """Collects domestic developer/tool alternative recommendations from V2EX."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://www.v2ex.com/api/topics/latest.json"

    def fetch(self, filter_keywords: Optional[List[str]] = None, limit: int = 10) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        keywords = filter_keywords or ["替代", "代替", "平替", "求推荐", "迁移到", "替代品"]
        exclude_words = [
            "ns2", "switch2", "游戏", "买车", "卖车", "股票", "基金", "相亲",
            "保险", "医疗", "医保", "意外险", "百万医疗", "电视", "手机", "信用卡", "买房", "装修", "租房"
        ]
        res = request_with_retry(self.base_url, timeout=self.timeout)
        if res and res.status_code == 200:
            try:
                topics = res.json()
                for topic in topics:
                    topic_id = str(topic.get("id") or "")
                    title = topic.get("title", "")
                    content = topic.get("content", "") or ""
                    text_all = f"{title} {content}".lower()

                    if any(ex in text_all for ex in exclude_words):
                        continue

                    matched = [kw for kw in keywords if kw in text_all]
                    if matched:
                        url = topic.get("url") or f"https://www.v2ex.com/t/{topic_id}"
                        author = topic.get("member", {}).get("username", "V2EX User")
                        replies = topic.get("replies", 0)
                        signals.append(
                            IntentSignal(
                                title=title,
                                url=url,
                                source="V2EX",
                                content=content[:500],
                                author=author,
                                keyword=",".join(matched),
                                timestamp=datetime.utcfromtimestamp(topic.get("created", 0)).strftime("%Y-%m-%d %H:%M UTC")
                                if topic.get("created")
                                else None,
                                comments_count=replies,
                                engagement_metric=f"💬 {replies} 条回帖" if replies else "⚡ 最新求助",
                                source_id=f"v2ex_{topic_id}" if topic_id else None,
                                evidence_quote=content[:260] if content else title,
                            )
                        )
                        if len(signals) >= limit:
                            break
            except Exception as e:
                logger.warning(f"Error parsing V2EX response: {e}")
        return signals


class CollectorHub:
    """Orchestrates all collectors concurrently with per-source timeout isolation and primary-key deduplication."""

    def __init__(self, config: Dict):
        self.config = config
        self.hn = HackerNewsCollector()
        self.github = GitHubCollector()
        self.devto = DevToCollector()
        self.google_news = GoogleNewsRSSCollector()
        self.v2ex = V2EXCollector()

    def run(self) -> List[IntentSignal]:
        all_signals: List[IntentSignal] = []
        seen_source_ids = set()
        seen_urls = set()
        limit = self.config.get("limit_per_query", 3)

        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            hn_queries = self.config.get(
                "hacker_news_queries",
                ["Ask HN Jira alternative", "Ask HN Postman alternative", "Ask HN Salesforce alternative", "DocuSign alternative"],
            )
            for q in hn_queries:
                tasks.append(executor.submit(self.hn.fetch, q, limit))

            github_queries = self.config.get("github_queries", ["migrate from Jira", "replace Postman"])
            for q in github_queries:
                tasks.append(executor.submit(self.github.fetch, q, limit))

            tasks.append(executor.submit(self.devto.fetch, "alternative", limit))

            if self.config.get("enable_v2ex", True):
                v2ex_kws = self.config.get("v2ex_keywords", ["替代", "求推荐", "平替", "迁移"])
                tasks.append(executor.submit(self.v2ex.fetch, v2ex_kws, limit * 2))

            try:
                for future in concurrent.futures.as_completed(tasks, timeout=18):
                    try:
                        items = future.result(timeout=2)
                        for item in items:
                            norm_u = normalize_url(item.url)
                            if item.source_id not in seen_source_ids and norm_u not in seen_urls:
                                seen_source_ids.add(item.source_id)
                                seen_urls.add(norm_u)
                                all_signals.append(item)
                    except Exception as e:
                        logger.warning(f"Individual collector task timed out or failed: {e}")
            except concurrent.futures.TimeoutError:
                logger.warning("Global collector wait window reached; returning completed sources.")

        logger.info(f"Total deduplicated signals collected concurrently: {len(all_signals)}")
        return all_signals
