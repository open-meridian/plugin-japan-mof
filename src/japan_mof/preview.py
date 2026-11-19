"""The pages on sample data, each printed as one HTML file:
for looking at them without a deployment.

    python -m japan_mof.preview connection > preview/connection.html

The plugin's work runs on the SDK's suite recorder in place of a sidecar --
the curve's record resolved, every batch recorded -- against the answers
committed under responses/, at 22:00 UTC on 18 November 2026: the current
month read; wants for 1 October and 18 November answered, and one for a
Sunday declined. `connection-sources` and `datasets-records` are each
page's second tab; `connection-first` and `datasets-first` the pages before
the first check; `connection-missing` the record not held.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .feed import Feed
from .page import CONNECTION, DATASETS_PAGE, hold, pages
from .portal import SyntheticPortal
from .raw import RawStore

AT = datetime(2026, 11, 18, 22, 0, tzinfo=UTC)
PAGES = {
    "connection": CONNECTION,
    "connection-sources": CONNECTION,
    "datasets": DATASETS_PAGE,
    "datasets-records": DATASETS_PAGE,
    "datasets-search": DATASETS_PAGE,
    "connection-first": CONNECTION,
    "datasets-first": DATASETS_PAGE,
    "connection-missing": CONNECTION,
}
TABS = {"connection-sources": "sources", "datasets-records": "records"}
SEARCHED = "JGB"
JGB_ID = "LCL-JGB"


def _want(want_id: str, day: str) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset="japan-mof:mof_curves",
            data_type="meridian.v1.Rate",
            subjects=[ops.SubjectRef(entity_id=JGB_ID)],
            business_date=day,
        ),
    )


def _feed(held: bool = True) -> Feed:
    recorder = Recorder("japan-mof")

    def resolved(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        if held:
            return ops.ResolveIdentifierResult(found=True, instrument_id=JGB_ID)
        return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)

    recorder.answer("ResolveIdentifier", resolved)
    return recorder.bind(Feed(SyntheticPortal(lambda: AT), RawStore(), now=lambda: AT))


async def synthetic_feed(held: bool = True) -> Feed:
    feed = _feed(held)
    await feed.check()
    if held:
        await feed.on_observations_wanted(_want("want-1001", "2026-10-01"))
        await feed.on_observations_wanted(_want("want-1118", "2026-11-18"))
        await feed.on_observations_wanted(_want("want-1115", "2026-11-15"))
    return feed


def render(page: str) -> str:
    if page.endswith("-first"):
        feed = _feed()
    else:
        feed = asyncio.run(synthetic_feed(held=page != "connection-missing"))
    hold(feed)
    query = {"q": SEARCHED} if page == "datasets-search" else {}
    if page in TABS:
        query = {"tab": TABS[page]}
    answer = PageClient(pages).get(PAGES[page], "admin", **query)
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
