"""One source per killable process; queries share its limiter and cooldown.

Only collection settings are passed on stdin (never model keys or webhooks).
Results are written before process exit, so the supervisor never blocks reading
an incomplete IPC message at its deadline.
"""
import json
import os
import sys
import time
from pathlib import Path

from .collector import (GLOBAL_RATE_LIMITER, SOURCE_OUTCOMES, HackerNewsCollector, GitHubCollector,
                        DevToCollector, GoogleNewsRSSCollector, V2EXCollector)


def collect(source, settings):
    SOURCE_OUTCOMES.clear()
    GLOBAL_RATE_LIMITER.reset()
    deadline = time.monotonic() + settings['remaining_seconds']
    limit = settings['limit']
    collectors = {'hn': HackerNewsCollector, 'github': GitHubCollector,
                  'devto': DevToCollector, 'news': GoogleNewsRSSCollector, 'v2ex': V2EXCollector}
    collector = collectors[source]()
    items = []
    for query in settings['queries']:
        if time.monotonic() >= deadline:
            break
        if source == 'news':
            batch = collector.fetch(query, limit, 'en', deadline)
        else:
            batch = collector.fetch(query, limit, deadline)
        items.extend(batch)
    return {'signals': [item.to_dict() for item in items], 'outcomes': dict(SOURCE_OUTCOMES),
            'deferred': GLOBAL_RATE_LIMITER.get_deferred_sources(),
            'cooldowns': {host: GLOBAL_RATE_LIMITER.get_cooldown_remaining('https://' + host)
                          for host in GLOBAL_RATE_LIMITER.get_deferred_sources()}}


def atomic_write_json(target_path: Path, data: dict) -> None:
    tmp_path = target_path.with_suffix(target_path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp_path, target_path)


if __name__ == '__main__':
    result = collect(sys.argv[1], json.load(sys.stdin))
    atomic_write_json(Path(sys.argv[2]), result)
