"""Thin, testable client for the College Scorecard API.

Handles authentication, pagination, retries with exponential backoff on
429/5xx responses, and a polite delay between pages.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

log = logging.getLogger(__name__)


class ScorecardError(RuntimeError):
    """Raised when the API returns an error we can't recover from."""


def build_session(total_retries: int = 5, backoff: float = 2.0) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff,  # 2s, 4s, 8s, ...
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "college-roi-analysis/0.1"})
    return session


class ScorecardClient:
    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        per_page: int = config.PER_PAGE,
        page_delay: float = 0.5,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.API_KEY
        if not self.api_key:
            raise ScorecardError(
                "Missing API key. Get one at https://api.data.gov/signup/ "
                "and put SCORECARD_API_KEY=... in your .env file."
            )
        self.session = session or build_session()
        self.per_page = min(per_page, 100)
        self.page_delay = page_delay

    def get_page(
        self, fields: list[str], filters: dict[str, str], page: int, **extra: str
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "fields": ",".join(fields),
            "per_page": self.per_page,
            "page": page,
            **filters,
            **extra,
        }
        resp = self.session.get(config.API_URL, params=params, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code != 200:
            # Never log the full URL: it contains the API key.
            raise ScorecardError(f"HTTP {resp.status_code} on page {page}: {resp.text[:300]}")
        payload = resp.json()
        if "results" not in payload or "metadata" not in payload:
            raise ScorecardError(f"Unexpected response shape on page {page}: {list(payload)}")
        return payload

    def iter_results(
        self, fields: list[str], filters: dict[str, str], max_pages: int | None = None, **extra: str
    ) -> Iterator[dict[str, Any]]:
        """Yield every result record across all pages."""
        page = 0
        while True:
            payload = self.get_page(fields, filters, page, **extra)
            meta = payload["metadata"]
            total = int(meta.get("total", 0))
            results = payload["results"]
            log.info(
                "page %d: %d records (%d/%d)",
                page,
                len(results),
                min((page + 1) * self.per_page, total),
                total,
            )
            yield from results

            page += 1
            if not results or page * self.per_page >= total:
                break
            if max_pages is not None and page >= max_pages:
                log.warning("Stopping early at max_pages=%d", max_pages)
                break
            time.sleep(self.page_delay)
