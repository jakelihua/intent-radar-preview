"""
Multi-source High-Intent Signal & Competitor Intelligence Collector (v3.1).
Enforces production pilot invariants:
1. Full untruncated raw_content & normalized content preservation (zero 500/600-char body truncation).
2. RFC-compliant Retry-After parsing (both integer/float seconds AND HTTP-date format).
3. Shared per-source rate limiting & cooldown state: if Retry-After exceeds current run budget,
   immediately defers the source instead of sleeping 5s and retrying early.
4. True non-blocking timeout isolation in CollectorHub.run(): uses explicit executor.shutdown(wait=False, cancel_futures=True)
   and propagates monotonic deadline into request budgets.
5. Persistent SQLite deduplication & version tracking via IntentStateStore, plus separated published_at vs updated_at.
6. Explicit dataset_kind ('live_production' vs 'historical_benchmark'), freshness_status, and delivery_eligible flags.
"""

import concurrent.futures
import email.utils
import hashlib
import html
import logging
import random
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests

from .state_store import IntentStateStore, compute_content_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Collector")

DEFAULT_TIMEOUT = 8.0
DEFAULT_MAX_WAIT_BUDGET = 3.0
HEADERS = {
    "User-Agent": "IntentRadar-VerificationEngine/3.1 (+https://github.com/jakelihua/intent-radar-preview)"
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


def parse_retry_after(header_val: Optional[str], now_epoch: Optional[float] = None) -> Optional[float]:
    """
    Parses HTTP Retry-After header supporting both delay-seconds and HTTP-date (RFC 7231 / RFC 2822).
    Returns non-negative wait seconds, or None if unparseable.
    """
    if not header_val:
        return None
    raw = str(header_val).strip()
    if not raw:
        return None
    # 1. Numeric seconds (integer or float)
    try:
        secs = float(raw)
        return max(0.0, secs)
    except ValueError:
        pass
    # 2. HTTP-date format (e.g. "Wed, 21 Oct 2026 07:28:00 GMT")
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ref_now = now_epoch if now_epoch is not None else time.time()
            delta = dt.timestamp() - ref_now
            return max(0.0, delta)
    except Exception:
        pass
    return None


class SourceRateLimiter:
    """
    Shared per-source rate limiter and cooldown registry.
    Prevents concurrent queries to the same host from firing simultaneously or ignoring a 429 cooldown.
    """

    def __init__(self, min_interval_sec: float = 0.05):
        self.min_interval_sec = min_interval_sec
        self._lock = threading.Lock()
        self._next_allowed_mono: Dict[str, float] = {}
        self._cooldown_until_mono: Dict[str, float] = {}
        self._deferred_sources: Dict[str, str] = {}

    @staticmethod
    def _source_key(url: str) -> str:
        try:
            return urllib.parse.urlsplit(url).netloc.lower() or url
        except Exception:
            return url

    def check_or_wait(self, url: str, deadline: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Checks if the source is currently in cooldown or needs rate-spacing.
        Returns (allowed: bool, reason_if_blocked: Optional[str]).
        """
        key = self._source_key(url)
        now = time.monotonic()
        with self._lock:
            cd_until = self._cooldown_until_mono.get(key, 0.0)
            if cd_until > now:
                remaining_cd = cd_until - now
                reason = f"Source {key} is in cooldown for another {remaining_cd:.2f}s"
                self._deferred_sources[key] = reason
                return False, reason

            next_ok = self._next_allowed_mono.get(key, 0.0)
            wait_needed = max(0.0, next_ok - now)
            if deadline is not None and (now + wait_needed) >= deadline:
                reason = f"Source {key} rate spacing exceeds deadline"
                return False, reason

            target_time = max(now, next_ok)
            self._next_allowed_mono[key] = target_time + self.min_interval_sec

        if wait_needed > 0:
            time.sleep(wait_needed)
        return True, None

    def set_cooldown(self, url: str, cooldown_seconds: float, reason: str = "") -> None:
        key = self._source_key(url)
        now = time.monotonic()
        with self._lock:
            until = now + max(0.0, cooldown_seconds)
            if until > self._cooldown_until_mono.get(key, 0.0):
                self._cooldown_until_mono[key] = until
            if reason:
                self._deferred_sources[key] = reason

    def get_cooldown_remaining(self, url: str) -> float:
        key = self._source_key(url)
        with self._lock:
            return max(0.0, self._cooldown_until_mono.get(key, 0.0) - time.monotonic())

    def get_deferred_sources(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._deferred_sources)

    def reset(self) -> None:
        with self._lock:
            self._next_allowed_mono.clear()
            self._cooldown_until_mono.clear()
            self._deferred_sources.clear()


GLOBAL_RATE_LIMITER = SourceRateLimiter(min_interval_sec=0.05)


def request_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = 2,
    max_retry_wait_budget: float = DEFAULT_MAX_WAIT_BUDGET,
    deadline: Optional[float] = None,
    rate_limiter: Optional[SourceRateLimiter] = None,
) -> Optional[requests.Response]:
    """
    Bounded HTTP GET with:
    - Shared per-source rate limiting & cooldown check
    - RFC Retry-After (numeric + HTTP-date) compliance: if Retry-After > max_retry_wait_budget (or exceeds deadline),
      immediately marks the source on cooldown and defers without sleeping early or retrying!
    - Per-attempt connect/read timeout clamped to remaining deadline budget.
    """
    limiter = rate_limiter or GLOBAL_RATE_LIMITER
    req_headers = {**HEADERS, **(headers or {})}

    for attempt in range(max_retries + 1):
        now_mono = time.monotonic()
        if deadline is not None and now_mono >= deadline:
            logger.warning(f"Aborting request to {url}: global deadline reached.")
            return None

        allowed, block_reason = limiter.check_or_wait(url, deadline=deadline)
        if not allowed:
            logger.warning(f"Deferring request to {url}: {block_reason}")
            return None

        # Compute effective per-attempt timeout respecting deadline
        effective_timeout: float = float(timeout)
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0.02:
                return None
            effective_timeout = min(effective_timeout, remaining)

        try:
            res = requests.get(
                url,
                params=params,
                headers=req_headers,
                timeout=(min(3.0, effective_timeout), effective_timeout),
            )
            if res.status_code == 200:
                return res

            if res.status_code in (429, 502, 503, 504):
                retry_after_raw = res.headers.get("Retry-After")
                parsed_wait = parse_retry_after(retry_after_raw)

                if parsed_wait is not None:
                    # Record shared cooldown on the source immediately
                    limiter.set_cooldown(
                        url,
                        parsed_wait,
                        reason=f"HTTP {res.status_code} Retry-After={parsed_wait:.1f}s",
                    )
                    # If Retry-After exceeds budget or deadline, DO NOT sleep a truncated duration and retry early!
                    if parsed_wait > max_retry_wait_budget:
                        logger.warning(
                            f"Source {url} requested Retry-After={parsed_wait:.1f}s (> budget {max_retry_wait_budget:.1f}s); deferring source for this run."
                        )
                        return res
                    if deadline is not None and (time.monotonic() + parsed_wait) >= deadline:
                        logger.warning(
                            f"Source {url} Retry-After={parsed_wait:.1f}s exceeds run deadline; deferring source."
                        )
                        return res
                    wait_sec = parsed_wait
                else:
                    wait_sec = (0.35 * (2 ** attempt)) + random.uniform(0.05, 0.2)

                if attempt < max_retries:
                    if deadline is not None and (time.monotonic() + wait_sec) >= deadline:
                        return res
                    # Clear our own cooldown lock if we are waiting out the exact short Retry-After
                    time.sleep(wait_sec)
                    continue

            logger.warning(f"Source {url} returned HTTP {res.status_code}")
            return res
        except requests.RequestException as e:
            if attempt < max_retries:
                backoff = (0.25 * (2 ** attempt)) + random.uniform(0.03, 0.15)
                if deadline is not None and (time.monotonic() + backoff) >= deadline:
                    return None
                time.sleep(backoff)
            else:
                logger.warning(f"Source request failed after {max_retries + 1} attempts ({url}): {e}")
    return None


def strip_html_tags(raw: str) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n\n".join(ln for ln in lines if ln).strip()


def evaluate_freshness(
    timestamp_str: Optional[str],
    dataset_kind: str = "live_production",
    fresh_days_window: int = 30,
) -> Tuple[str, bool]:
    """
    Evaluates signal freshness from UTC timestamp and dataset_kind.
    Returns (freshness_status, delivery_eligible).
    - Historical benchmark samples ('historical_benchmark') are NEVER eligible for automated live sales delivery.
    - Live signals published within fresh_days_window days are 'fresh_within_window' and delivery_eligible=True.
    """
    if dataset_kind != "live_production":
        return "historical_benchmark_archive", False

    if not timestamp_str:
        return "unknown_timestamp", False

    clean_ts = timestamp_str.replace("UTC", "").strip()
    parsed_dt = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed_dt = datetime.strptime(clean_ts[:19].strip(), fmt)
            break
        except ValueError:
            continue

    if parsed_dt is None:
        try:
            dt_obj = email.utils.parsedate_to_datetime(timestamp_str)
            if dt_obj is not None:
                parsed_dt = dt_obj.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

    if parsed_dt is None:
        return "unknown_timestamp", False

    age_days = (datetime.utcnow() - parsed_dt).total_seconds() / 86400.0
    if age_days <= fresh_days_window:
        return "fresh_within_window", True
    elif age_days <= 90:
        return "recent_research_90d", False
    return "historical_archive", False


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
        updated_at: Optional[str] = None,
        comments_count: int = 0,
        engagement_metric: str = "",
        source_id: Optional[str] = None,
        collected_at: Optional[str] = None,
        evidence_quote: Optional[str] = None,
        qualification_meta: Optional[Dict[str, Any]] = None,
        raw_content: Optional[str] = None,
        dataset_kind: str = "live_production",
        freshness_status: Optional[str] = None,
        delivery_eligible: Optional[bool] = None,
    ):
        self.title = title.strip()
        self.url = url.strip()
        self.normalized_url = normalize_url(self.url)
        self.source = source
        # Preserve 100% full raw content and full normalized content (never truncate body)
        self.raw_content = (raw_content if raw_content is not None else content).strip()
        self.content = content.strip()
        self.summary_excerpt = self.content[:280] + ("..." if len(self.content) > 280 else "")
        self.author = author
        self.keyword = keyword
        self.timestamp = timestamp or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        self.updated_at = updated_at or self.timestamp
        self.collected_at = collected_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        self.comments_count = comments_count
        self.engagement_metric = engagement_metric
        self.source_id = source_id or hashlib.md5(f"{self.source}:{self.normalized_url}".encode("utf-8")).hexdigest()[:12]
        self.id = str(source_id) if source_id else hashlib.md5(f"{self.source}:{self.source_id}".encode("utf-8")).hexdigest()[:12]
        self.evidence_quote = (evidence_quote or self.content or self.title).strip()
        self.dataset_kind = dataset_kind
        calc_fresh, calc_elig = evaluate_freshness(self.timestamp, dataset_kind=self.dataset_kind)
        self.freshness_status = freshness_status if freshness_status is not None else calc_fresh
        self.delivery_eligible = delivery_eligible if delivery_eligible is not None else calc_elig
        self.content_hash = compute_content_hash(self.title, self.raw_content or self.content)
        self.version_num = 1
        self.sync_status = "new"
        self.first_seen_at = self.collected_at
        self.last_seen_at = self.collected_at

        raw_qm = dict(qualification_meta or {})
        for k in ("team_scale", "budget_status", "decision_authority", "migration_urgency"):
            if isinstance(raw_qm.get(k), dict):
                item = dict(raw_qm[k])
                src_val = item.get("source") or item.get("provenance") or "未知"
                item["source"] = src_val
                item["provenance"] = src_val
                if "evidence" not in item:
                    item["evidence"] = item.get("evidence_snippet") or ""
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
            "normalized_url": self.normalized_url,
            "source": self.source,
            "raw_content": self.raw_content,
            "content": self.content,
            "summary_excerpt": self.summary_excerpt,
            "evidence_quote": self.evidence_quote,
            "author": self.author,
            "keyword": self.keyword,
            "timestamp": self.timestamp,
            "updated_at": self.updated_at,
            "collected_at": self.collected_at,
            "comments_count": self.comments_count,
            "engagement_metric": self.engagement_metric,
            "dataset_kind": self.dataset_kind,
            "freshness_status": self.freshness_status,
            "delivery_eligible": self.delivery_eligible,
            "content_hash": self.content_hash,
            "version_num": self.version_num,
            "sync_status": self.sync_status,
            "qualification_meta": self.qualification_meta,
        }


class HackerNewsCollector:
    """Collects buying intent & competitor discussions from Hacker News via Algolia API (full untruncated text)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://hn.algolia.com/api/v1/search_by_date"

    def fetch(self, query: str, limit: int = 5, deadline: Optional[float] = None) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {
            "query": query,
            "tags": "(story,ask_hn)",
            "hitsPerPage": limit,
        }
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout, deadline=deadline)
        if res and res.status_code == 200:
            data = res.json()
            for hit in data.get("hits", []):
                if deadline is not None and time.monotonic() >= deadline:
                    break
                obj_id = str(hit.get("objectID") or "")
                title = hit.get("title") or ""
                if title.lower().startswith(("show hn:", "launch hn:")):
                    continue
                url = f"https://news.ycombinator.com/item?id={obj_id}" if obj_id else (hit.get("url") or "")
                raw_html = hit.get("story_text") or hit.get("comment_text") or ""
                full_story = strip_html_tags(raw_html)
                content = full_story if full_story else title
                author = hit.get("author") or "HN User"
                points = hit.get("points") or 0
                num_comments = hit.get("num_comments") or 0
                created_str = (hit.get("created_at") or "")[:16].replace("T", " ") + " UTC"
                updated_str = (hit.get("updated_at") or hit.get("created_at") or "")[:16].replace("T", " ") + " UTC"

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
                            raw_content=raw_html or content,
                            content=content,
                            author=author,
                            keyword=query,
                            timestamp=created_str,
                            updated_at=updated_str,
                            comments_count=num_comments,
                            engagement_metric=engagement_metric,
                            source_id=f"hn_{obj_id}" if obj_id else None,
                            evidence_quote=full_story[:280] if full_story else title,
                            dataset_kind="live_production",
                        )
                    )
        return signals


class GitHubCollector:
    """Collects engineering team migration & tool replacement discussions from GitHub Issues (full body + separated created_at/updated_at)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://api.github.com/search/issues"

    def fetch(self, query: str, limit: int = 5, deadline: Optional[float] = None) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {
            "q": f"{query} is:issue",
            "sort": "updated",
            "order": "desc",
            "per_page": limit,
        }
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout, deadline=deadline)
        if res and res.status_code == 200:
            items = res.json().get("items", [])
            for item in items:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                issue_id = str(item.get("id") or "")
                title = item.get("title") or ""
                url = item.get("html_url") or ""
                comments = item.get("comments", 0)
                raw_body = item.get("body") or ""
                norm_body = re.sub(r"[ \t]+", " ", raw_body).strip()
                author = item.get("user", {}).get("login", "GitHub User")
                created_at = (item.get("created_at") or item.get("updated_at") or "")[:16].replace("T", " ") + " UTC"
                updated_at = (item.get("updated_at") or item.get("created_at") or "")[:16].replace("T", " ") + " UTC"
                if title and url:
                    signals.append(
                        IntentSignal(
                            title=title,
                            url=url,
                            source="GitHub Issues",
                            raw_content=raw_body or title,
                            content=norm_body or title,
                            author=author,
                            keyword=query,
                            timestamp=created_at,
                            updated_at=updated_at,
                            comments_count=comments,
                            engagement_metric=f"💬 {comments} 条技术讨论",
                            source_id=f"gh_{issue_id}" if issue_id else None,
                            evidence_quote=norm_body[:280] if norm_body else title,
                            dataset_kind="live_production",
                        )
                    )
        return signals


class DevToCollector:
    """Collects software alternative guides & developer migration discussions from Dev.to API."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://dev.to/api/articles"

    def fetch(self, tag: str = "alternative", limit: int = 5, deadline: Optional[float] = None) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        params = {"tag": tag, "per_page": limit}
        res = request_with_retry(self.base_url, params=params, timeout=self.timeout, deadline=deadline)
        if res and res.status_code == 200:
            for item in res.json():
                if deadline is not None and time.monotonic() >= deadline:
                    break
                art_id = str(item.get("id") or "")
                title = item.get("title") or ""
                url = item.get("url") or ""
                full_body = item.get("body_markdown") or strip_html_tags(item.get("body_html") or "") or item.get("description") or title
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
                            raw_content=full_body,
                            content=full_body,
                            author=author,
                            keyword=tag,
                            timestamp=ts,
                            updated_at=ts,
                            comments_count=comments,
                            engagement_metric=f"💬 {comments} 讨论 · 👍 {reactions} 赞同",
                            source_id=f"devto_{art_id}" if art_id else None,
                            evidence_quote=full_body[:280],
                            dataset_kind="live_production",
                        )
                    )
        return signals


class GoogleNewsRSSCollector:
    """Collects competitor pricing backlash & migration announcements via Google News RSS."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://news.google.com/rss/search"

    def fetch(self, query: str, limit: int = 5, lang: str = "en", deadline: Optional[float] = None) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        encoded_q = urllib.parse.quote(query)
        if lang == "zh":
            url = f"{self.base_url}?q={encoded_q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        else:
            url = f"{self.base_url}?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"

        res = request_with_retry(url, timeout=self.timeout, deadline=deadline)
        if res and res.status_code == 200:
            try:
                root = ET.fromstring(res.content)
                items = root.findall(".//item")
                for it in items[:limit]:
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    title_elem = it.find("title")
                    link_elem = it.find("link")
                    pub_date = it.find("pubDate")
                    desc_elem = it.find("description")
                    guid_elem = it.find("guid")

                    title = title_elem.text if title_elem is not None else ""
                    link = link_elem.text if link_elem is not None else ""
                    raw_desc = desc_elem.text if desc_elem is not None else ""
                    content = strip_html_tags(raw_desc) or title
                    ts = pub_date.text if pub_date is not None else None
                    guid = (guid_elem.text if guid_elem is not None else "") or link
                    g_hash = hashlib.md5(guid.encode("utf-8")).hexdigest()[:10]

                    if title and link:
                        signals.append(
                            IntentSignal(
                                title=title,
                                url=link,
                                source="Google News RSS",
                                raw_content=raw_desc or content,
                                content=content,
                                author="News Media",
                                keyword=query,
                                timestamp=ts,
                                updated_at=ts,
                                comments_count=0,
                                engagement_metric="📰 行业媒体报道",
                                source_id=f"gnews_{g_hash}",
                                evidence_quote=content[:280],
                                dataset_kind="live_production",
                            )
                        )
            except Exception as e:
                logger.warning(f"Error parsing Google News RSS XML: {e}")
        return signals


class V2EXCollector:
    """Collects domestic developer/tool alternative recommendations from V2EX (full untruncated content)."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.base_url = "https://www.v2ex.com/api/topics/latest.json"

    def fetch(self, filter_keywords: Optional[List[str]] = None, limit: int = 10, deadline: Optional[float] = None) -> List[IntentSignal]:
        signals: List[IntentSignal] = []
        keywords = filter_keywords or ["替代", "代替", "平替", "求推荐", "迁移到", "替代品"]
        exclude_words = [
            "ns2", "switch2", "游戏", "买车", "卖车", "股票", "基金", "相亲",
            "保险", "医疗", "医保", "意外险", "百万医疗", "电视", "手机", "信用卡", "买房", "装修", "租房"
        ]
        res = request_with_retry(self.base_url, timeout=self.timeout, deadline=deadline)
        if res and res.status_code == 200:
            try:
                topics = res.json()
                for topic in topics:
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    topic_id = str(topic.get("id") or "")
                    title = topic.get("title", "")
                    content = (topic.get("content", "") or "").strip()
                    text_all = f"{title} {content}".lower()

                    if any(ex in text_all for ex in exclude_words):
                        continue

                    matched = [kw for kw in keywords if kw in text_all]
                    if matched:
                        url = topic.get("url") or f"https://www.v2ex.com/t/{topic_id}"
                        author = topic.get("member", {}).get("username", "V2EX User")
                        replies = topic.get("replies", 0)
                        created_ts = (
                            datetime.utcfromtimestamp(topic.get("created", 0)).strftime("%Y-%m-%d %H:%M UTC")
                            if topic.get("created")
                            else None
                        )
                        modified_ts = (
                            datetime.utcfromtimestamp(topic.get("last_modified", topic.get("created", 0))).strftime("%Y-%m-%d %H:%M UTC")
                            if topic.get("last_modified") or topic.get("created")
                            else created_ts
                        )
                        signals.append(
                            IntentSignal(
                                title=title,
                                url=url,
                                source="V2EX",
                                raw_content=content or title,
                                content=content or title,
                                author=author,
                                keyword=",".join(matched),
                                timestamp=created_ts,
                                updated_at=modified_ts,
                                comments_count=replies,
                                engagement_metric=f"💬 {replies} 条回帖" if replies else "⚡ 最新求助",
                                source_id=f"v2ex_{topic_id}" if topic_id else None,
                                evidence_quote=(content[:280] if content else title),
                                dataset_kind="live_production",
                            )
                        )
                        if len(signals) >= limit:
                            break
            except Exception as e:
                logger.warning(f"Error parsing V2EX response: {e}")
        return signals


class CollectorHub:
    """
    Orchestrates all 5 active collectors (Hacker News, GitHub Issues, Dev.to, Google News RSS, V2EX)
    concurrently with:
    - True non-blocking timeout isolation (`executor.shutdown(wait=False, cancel_futures=True)`)
    - Monotonic deadline propagation to in-flight HTTP calls
    - Persistent SQLite deduplication & content update version tracking via IntentStateStore
    """

    ENABLED_SOURCES = ("Hacker News", "GitHub Issues", "Dev.to", "Google News RSS", "V2EX")

    def __init__(self, config: Dict, state_store: Optional[IntentStateStore] = None):
        self.config = config
        self.hn = HackerNewsCollector()
        self.github = GitHubCollector()
        self.devto = DevToCollector()
        self.google_news = GoogleNewsRSSCollector()
        self.v2ex = V2EXCollector()
        self.state_store = state_store or IntentStateStore(config.get("state_db_path"))

    def run(self, global_timeout: Optional[float] = None, only_new_or_updated: bool = False) -> List[IntentSignal]:
        all_signals_by_id: Dict[str, IntentSignal] = {}
        seen_urls = set()
        limit = self.config.get("limit_per_query", 3)
        timeout_budget = float(
            global_timeout if global_timeout is not None else self.config.get("collector_global_timeout", 18.0)
        )
        deadline = time.monotonic() + timeout_budget

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        tasks: List[concurrent.futures.Future] = []
        try:
            hn_queries = self.config.get(
                "hacker_news_queries",
                ["Ask HN Jira alternative", "Ask HN Postman alternative", "Ask HN Salesforce alternative", "DocuSign alternative"],
            )
            for q in hn_queries:
                tasks.append(executor.submit(self.hn.fetch, q, limit, deadline))

            github_queries = self.config.get("github_queries", ["migrate from Jira", "replace Postman"])
            for q in github_queries:
                tasks.append(executor.submit(self.github.fetch, q, limit, deadline))

            if self.config.get("enable_devto", True):
                tasks.append(executor.submit(self.devto.fetch, "alternative", limit, deadline))

            if self.config.get("enable_google_news", True):
                gnews_queries = self.config.get("google_news_queries", ["Postman alternative", "Jira migration"])
                for gq in gnews_queries:
                    tasks.append(executor.submit(self.google_news.fetch, gq, limit, "en", deadline))

            if self.config.get("enable_v2ex", True):
                v2ex_kws = self.config.get("v2ex_keywords", ["替代", "求推荐", "平替", "迁移"])
                tasks.append(executor.submit(self.v2ex.fetch, v2ex_kws, limit * 2, deadline))

            remaining_window = max(0.005, deadline - time.monotonic())
            try:
                for future in concurrent.futures.as_completed(tasks, timeout=remaining_window):
                    try:
                        items = future.result(timeout=0.05)
                        for item in items or []:
                            key = f"{item.source}:{item.source_id}"
                            norm_u = item.normalized_url
                            # If the same source_id appears multiple times in the same run, keep the newer/longer version
                            if key in all_signals_by_id:
                                prev = all_signals_by_id[key]
                                if len(item.content) <= len(prev.content) and item.updated_at <= prev.updated_at:
                                    continue
                            elif norm_u in seen_urls:
                                continue

                            sync_info = self.state_store.upsert_signal(item)
                            if only_new_or_updated and not sync_info["should_analyze"]:
                                continue
                            seen_urls.add(norm_u)
                            all_signals_by_id[key] = item
                    except Exception as e:
                        logger.warning(f"Individual collector task failed: {e}")
            except concurrent.futures.TimeoutError:
                logger.warning(f"Global collector wait window ({timeout_budget:.3f}s) reached; cancelling unfinished tasks immediately.")
        finally:
            # CRITICAL: Do NOT wait for hung/slow background threads when budget expires
            executor.shutdown(wait=False, cancel_futures=True)

        results = list(all_signals_by_id.values())
        logger.info(f"Total deduplicated signals collected concurrently: {len(results)}")
        return results
