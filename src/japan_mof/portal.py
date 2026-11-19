"""The Ministry of Finance's website, where its JGB interest rates are
served, and its stand-in.

Two requests are made, and nothing else
(https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/index.htm):

- the current month's interest rates --
  `/english/policy/jgbs/reference/interest_rate/jgbcme.csv`, every hour;
- the history since 24 September 1974 --
  `/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv`,
  some 1.2 MB, only when the lake wants a day before the current month's,
  and at most once a day a process.

Read from the Ministry itself: no key, no account. Its site states no rate
limit; the plugin asks one request at a time, at most one every two seconds,
says who it is in its User-Agent, and checks the current month every hour.

`SyntheticPortal` answers from the real responses committed under
responses/ (responses/index.json), recorded on 2026-11-19: the current
month's file (2 to 18 November 2026) and the history (24 September 1974 to
30 October 2026), each as received, so the plugin's tests and its e2e run
on them, offline, the same on any day.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import resources
from typing import Protocol

BASE = "https://www.mof.go.jp"
CURRENT, HISTORY = "current", "history"
SOURCES = (CURRENT, HISTORY)
_RATES = "/english/policy/jgbs/reference/interest_rate/"
#: Each source's address.
PATHS = {CURRENT: _RATES + "jgbcme.csv", HISTORY: _RATES + "historical/jgbcme_all.csv"}
USER_AGENT = "meridian-japan-mof (+https://github.com/open-meridian/plugin-japan-mof)"
SPACING = 2.0
TIMEOUT = 120.0
#: The most an answer may be: the history is some 1.2 MB.
MOST_BYTES = 16 * 1024 * 1024
#: The Ministry's files' encoding.
ENCODING = "cp932"


def source_of(path: str) -> str:
    """Which source an address asks: current or history."""
    return next((s for s, at in PATHS.items() if path == at), "")


class PortalUnreachable(Exception):  # noqa: N818 - what the Ministry's website was
    """The website could not be asked: no answer, or not in time."""


@dataclass(frozen=True)
class Fetched:
    """One answer, as received."""

    path: str
    status: int
    body: bytes
    fetched_at: datetime
    date: str = ""

    @property
    def url(self) -> str:
        return BASE + self.path

    @property
    def text(self) -> str:
        return self.body.decode(ENCODING, errors="replace")


class Portal(Protocol):
    mode: str

    async def get(self, path: str) -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class LivePortal:
    """The Ministry's website itself."""

    mode = "live"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def get(self, path: str) -> Fetched:
        async with self._lock:
            wait = self._last + SPACING - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await asyncio.to_thread(self._get, path)
            finally:
                self._last = time.monotonic()

    def _get(self, path: str) -> Fetched:
        request = urllib.request.Request(BASE + path, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - the Ministry's https address
                body = answer.read(MOST_BYTES + 1)
                status = answer.status
                said = answer.headers
        except urllib.error.HTTPError as refused:
            body = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status, said = refused.code, refused.headers
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise PortalUnreachable(f"{BASE}{path[:80]}: {type(reason).__name__}") from failed
        if len(body) > MOST_BYTES:
            raise PortalUnreachable(f"{BASE}{path[:80]}: answered more than {MOST_BYTES} bytes")
        return Fetched(path, status, body, self._now(), date=said.get("Date", "") if said else "")


@dataclass(frozen=True)
class Recording:
    """One recorded answer, its Date and last day."""

    body: bytes
    said: str
    last_day: date


class SyntheticPortal:
    """The responses committed under responses/: each file answered whole,
    under its recording's Date."""

    mode = "synthetic"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("responses")
        index = json.loads(held.joinpath("index.json").read_text(encoding="utf-8"))
        self.recordings = {}
        for source in SOURCES:
            body = held.joinpath(index[source]["file"]).read_bytes()
            self.recordings[source] = Recording(
                gzip.decompress(body) if index[source]["file"].endswith(".gz") else body,
                str(index[source]["date"]),
                date.fromisoformat(index[source]["last_day"]),
            )
        self.asked: list[str] = []

    async def get(self, path: str) -> Fetched:
        self.asked.append(path)
        recording = self.recordings.get(source_of(path))
        if recording is None:
            return Fetched(path, 404, b"Not found", self._now())
        return Fetched(path, 200, recording.body, self._now(), recording.said)


def portal(synthetic: bool, now: Callable[[], datetime] = utc_now) -> Portal:
    return SyntheticPortal(now) if synthetic else LivePortal(now)
