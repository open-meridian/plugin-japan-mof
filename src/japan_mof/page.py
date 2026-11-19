"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, in its
order, each also a read tool for agents on the deployment's MCP under the
role's names (`read_connection`, `read_datasets`). Each record is the
role's (`meridian.roles.data`), extended with the Ministry of Finance's
fields; each template is the role's, with the Ministry's nuance at its
blocks only, as plugin-ecb's are.

A data plugin shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03):

- **Connection** (`/`): "Key" -- the mode (Live or Sample data), "No key
  needed", what the Ministry serves; "Limits and use" -- the Ministry
  states no figure, the requests made, the last check and error; "Stream":
  it does not stream. Then a tab of its own (`?tab=sources`), **Sources**,
  one line per file -- the current month and the history: its state, the
  latest day read, its calls, its last error, and in its detail where it
  reads and when.
- **Datasets** (`/datasets`): "Served", "Wants" and "Subjects", with its
  dataset; then a tab of its own (`?tab=records`), **Records**: the curve's
  record, with its convention and the deployment's instrument for it or why
  there is none -- one line a row, searched and paged by the kit's om-pager
  to fit one screen.

Neither shows a rate: rates are the reading roles' to show.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

from . import records
from .declared import CATALOGUE, MOF_CURVES
from .feed import Feed, SourceStatus, Status
from .portal import BASE, CURRENT, HISTORY, PATHS, SOURCES
from .series import TENORS

TITLE = "Ministry of Finance"
#: The kit these pages are built on: 0.12.0's "Facts" and "Next step".
KIT = "0.12.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS_PAGE = "/datasets"

MOST_QUERY = 100
CONNECTION_TABS = {"connection": "Connection", "sources": "Sources"}
TABS = {"served": "Served", "records": "Records"}
#: The source citation the Public Data License asks for.
ATTRIBUTION = (
    "Source: Ministry of Finance, Japan, JGB Interest Rate "
    f"({BASE}/english/policy/jgbs/reference/interest_rate/index.htm)"
)
SOURCE_NAMES = {CURRENT: "The current month's interest rates", HISTORY: "The history since 1974"}
SHORT_NAMES = {CURRENT: "Current month", HISTORY: "History"}
WHEN = {
    CURRENT: "Published at 9:30 Tokyo time the next business day; read every hour",
    HISTORY: (
        "Holds every day before the current month; read only when the lake wants such a day, "
        "at most once a day"
    ),
}
CONVENTION = (
    "par yields, semiannual compounding, as the Ministry states them; NL/365, the plugin's "
    "statement: the Ministry states no day count"
)

_held: dict[str, Any] = {}


def hold(feed: Feed) -> None:
    """The feed the pages read, once the plugin has registered."""
    _held["feed"] = feed


def _status() -> tuple[Status, Feed | None]:
    feed: Feed | None = _held.get("feed")
    return (feed.status if feed is not None else Status(), feed)


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds") if moment else ""


def _day(day: date | None) -> str:
    return day.isoformat() if day else ""


def _source_state(held: SourceStatus, mode: str) -> str:
    if held.error and held.read_at is None:
        return "Not answering"
    if held.read_at is None and held.source != CURRENT:
        return "Pulled when wanted"
    if held.error:
        return "Answering"
    if held.read_at is None:
        return "Checking the Ministry"
    return "Sample data" if mode == "synthetic" else "Answering"


def _state(status: Status) -> tuple[str, str, str]:
    """The head's status: its state, what it means, and its detail."""
    error = status.error
    if error and not status.read:
        return "error", "Not answering", error
    if error:
        return "warn", "Answering", error
    if not status.read:
        return "busy", "Checking the Ministry", ""
    misses = [h.code for h in status.records.values() if h.miss]
    if misses:
        plural = "record" if len(misses) == 1 else "records"
        return "warn", f"{len(misses)} {plural} not held", ", ".join(sorted(misses))
    if status.mode == "synthetic":
        return "ok", "Sample data", ""
    return "ok", "Answering", ""


def _source(source: str, status: Status, instance: str) -> records.SourceRead:
    held = status.sources[source]
    return records.SourceRead(
        source=SOURCE_NAMES[source],
        dataset=f"{instance}:{MOF_CURVES}",
        kind=source,
        state=_source_state(held, status.mode),
        last_release=_day(held.latest_day),
        calls=held.fetches,
        last_error=held.error,
        reads=(
            "The answer recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else BASE + PATHS[source]
        ),
        history=WHEN[source],
    )


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    instance = feed.plugin.identity.instance_id if feed is not None else "japan-mof"
    answered = status.read or status.mode == "synthetic"
    return records.ConnectionRead(
        mode="Sample data" if status.mode == "synthetic" else "Live",
        credentials=[],
        entitled_at_vendor="The JGB interest rates: no key" if answered else "",
        limit=(
            "The Ministry states no figure; the plugin asks one request at a time, at most one "
            "every two seconds, checks the current month every hour, and reads the history at "
            "most once a day"
        ),
        calls=status.fetches,
        last_call_at=_iso(status.checked_at),
        last_error=status.error,
        sessions=None,
        state=state,
        said=said,
        source=(
            "The answers recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else f"{BASE}'s interest rate files"
        ),
        checked_at=_iso(status.checked_at),
        sources=[_source(source, status, instance) for source in SOURCES],
        responses_kept=len(kept),
        kept_for=window,
    )


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "japan-mof"
    answered = status.read or status.mode == "synthetic"
    served = data.served(
        CATALOGUE,
        instance,
        feed.wants if feed is not None else None,
        "Yes: no key needed" if answered else "Not asked yet",
    )
    rows = [
        records.RecordRead(
            code=h.code,
            name=h.name,
            dataset=MOF_CURVES,
            recorded_as=f"par yields at {TENORS[0]} to {TENORS[-1]}",
            convention=CONVENTION,
            instrument_id=h.instrument_id,
            miss=h.miss,
            latest_day=_day(h.latest_day),
        )
        for h in status.records.values()
    ]
    return records.DatasetsRead(
        served=served,
        wants=list(data.want_rows(feed.wants)) if feed is not None else [],
        reads_instruments=True,
        attribution=ATTRIBUTION,
        records=rows,
        unread=[
            f"{line} ({n} reads)"
            for held in status.sources.values()
            for line, n in sorted(held.unread.items())
        ],
    )


def figures(status: Status, feed: Feed | None) -> list[meridian.Figure]:
    """The data role's figures, in its order (`meridian.roles.data`); the
    Ministry's plugin reports none of its own."""
    state, said, why = _state(status)
    if status.mode == "synthetic" and state == "ok":
        connection: Any = "Sample data"
    elif said == "Not answering":
        connection = meridian.Figure("", said, state="error", why=why[:200])
    else:
        error = status.error
        connection = meridian.Figure(
            "", "Answering", state="warn" if error else None, why=error[:200]
        )
    last = feed.wants.counts.last_ns if feed is not None else 0
    return data.figures(
        connection=connection,
        entitled_at_vendor=f"{len(CATALOGUE)} of {len(CATALOGUE)} datasets",
        stream="Does not stream",
        last_recorded=(datetime.fromtimestamp(last / 10**9, UTC) if last else None),
    )


def _moment(value: str) -> str:
    """An ISO moment as a person reads it, to the minute in UTC."""
    if not value:
        return ""
    if len(value) == 10:
        return value
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _weekday(value: str) -> str:
    return date.fromisoformat(value).strftime("%a %d %b %Y") if value else ""


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    words = query.lower().split()
    held = " ".join(texts).lower()
    return all(word in held for word in words)


pages.environment.filters["moment"] = _moment
pages.environment.filters["day"] = _weekday


@pages.page(
    CONNECTION,
    "Connection",
    levels="admin",
    answers=records.ConnectionRead,
    name="read_connection",
    description=(
        "How this plugin reaches the Ministry of Finance's website and its JGB interest rate "
        "files, as every data plugin's Connection answers it: the mode (Live or Sample "
        "data), no key needed, what the Ministry serves, its limits and the requests made, "
        "the last check and why it failed if it did; it does not stream. Then the Ministry's "
        "own: each file -- the current month and the history since 1974 -- with its state, "
        "the latest day read, its calls and last error; and how many answers are kept. No "
        "rate."
    ),
)
async def connection(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = connection_read(status, feed)
    tab = request.query.get("tab", "connection")
    return pages.answer(
        "connection.html",
        read,
        detail=_state(status)[2],
        # Named apart from the SDK's own `tab` and `tabs` (0.32.3), which
        # would draw the data role's section row in their place.
        view=tab if tab in CONNECTION_TABS else "connection",
        views=CONNECTION_TABS,
        short=SHORT_NAMES,
    )


@pages.page(
    DATASETS_PAGE,
    "Datasets",
    levels="admin",
    answers=records.DatasetsRead,
    name="read_datasets",
    description=(
        "What this plugin serves the lake, as every data plugin's Datasets answers it: its "
        "dataset as the catalogue declares it (the JGB interest rates on a constant maturity "
        "basis, par yields), whether a deployment admin has licensed it, what it recorded "
        "and declined; the standing wants it keeps current and the wants it answered. Then "
        "the Ministry's own: the source citation its terms ask for, and the curve's record "
        "with its convention and the deployment's instrument for it or why there is none. "
        "No rate."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = datasets_read(status, feed)
    # A browser draws one tab, its search narrowing the records drawn; a
    # tool answers every tab.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    tab = request.query.get("tab", "served")
    tab = "records" if query else tab if tab in TABS else "served"
    shown = [r for r in read.records if matching(query, r.code, r.name, r.dataset)]
    return pages.answer(
        "datasets.html",
        read,
        query=query,
        tab=tab,
        tabs=TABS,
        shown=shown,
        state=_state(status),
        checked_at=_iso(status.checked_at),
    )
