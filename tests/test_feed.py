"""The plugin's own conversion of the Ministry of Finance's recorded answers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from japan_mof.answers import NotRead, parse
from japan_mof.portal import HISTORY, PATHS, SyntheticPortal

from conftest import AT, INSTANCE, JGB, feed, resolving, want

TOKYO = ZoneInfo("Asia/Tokyo")


def checked(tmp: Path, *, held: bool = True) -> Recorder:
    plugin = resolving(Recorder(INSTANCE), held=held)
    asyncio.run(feed(tmp, plugin).check())
    return plugin


def rates_of(plugin: Recorder, want_id: str | None = None) -> list[ops.Rate]:
    return [
        r
        for b in plugin.on("RecordRates")
        if want_id is None or b.want_id == want_id
        for r in b.rates
    ]


def heard(tmp: Path, *asked: object, plugin: Recorder | None = None) -> Recorder:
    """The current month checked, then each want heard."""
    held = plugin or resolving(Recorder(INSTANCE))
    work = feed(tmp, held)
    asyncio.run(work.check())
    for one in asked:
        held.answer("ObservationsWanted", lambda _, w=one: w.message)  # type: ignore[misc]
        asyncio.run(held.hear(work))
    return held


def test_the_current_month_pushed_as_par_yields_semiannual(tmp_path: Path) -> None:
    rates = rates_of(checked(tmp_path))
    assert len(rates) == 12 * 15 and {r.meta.business_date for r in rates} >= {"2026-11-18"}
    ten = next(
        r
        for r in rates
        if r.meta.business_date == "2026-11-18"
        and (r.tenor.count, r.tenor.unit) == (10, ops.TENOR_UNIT_YEAR)
    )
    assert ten.kind == ops.RATE_KIND_PAR_YIELD and str(as_decimal(ten.value.value)) == "2.916"
    assert ten.value.unit == ops.VALUE_UNIT_PERCENT and ten.meta.subjects[0].entity_id == JGB
    assert ten.convention.compounding == ops.COMPOUNDING_COMPOUNDED
    assert ten.convention.periods_per_year == 2
    assert ten.convention.day_count == ops.DAY_COUNT_NL_365
    assert not ten.meta.source_times and ten.meta.raw.key.endswith("-current.json.gz")
    assert ten.meta.source.dataset == f"{INSTANCE}:mof_curves"


def test_a_day_before_the_month_read_from_the_history_once_a_day(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE))
    portal = SyntheticPortal(lambda: AT)
    work = feed(tmp_path, plugin, portal=portal)
    asyncio.run(work.check())
    for one in (want("w-1", [JGB], day="2026-10-01"), want("w-2", [JGB], day="2026-10-30")):
        plugin.answer("ObservationsWanted", lambda _, w=one: w.message)  # type: ignore[misc]
        asyncio.run(plugin.hear(work))
    assert portal.asked.count(PATHS[HISTORY]) == 1
    first = rates_of(plugin, "w-1")
    assert len(first) == 15 and {r.meta.business_date for r in first} == {"2026-10-01"}
    assert first[0].meta.raw.key.endswith("-history.json.gz")
    assert {r.meta.business_date for r in rates_of(plugin, "w-2")} == {"2026-10-30"}


def test_a_tenor_not_published_is_no_row(tmp_path: Path) -> None:
    plugin = heard(
        tmp_path,
        want("w-1", [JGB], day="2007-11-05"),
        want("w-2", [JGB], day="1974-09-24"),
    )
    tenors = {(r.tenor.count, r.tenor.unit) for r in rates_of(plugin, "w-1")}
    assert len(tenors) == 14 and (40, ops.TENOR_UNIT_YEAR) not in tenors
    assert len(rates_of(plugin, "w-2")) == 9


def test_a_range_wanted_its_tenor_set_changed(tmp_path: Path) -> None:
    start = datetime(2007, 11, 5, tzinfo=TOKYO)
    asked = want(
        "w-r",
        [JGB],
        valid_from_ns=int(start.timestamp()) * 10**9,
        valid_until_ns=int((start + timedelta(days=2)).timestamp()) * 10**9,
    )
    rates = rates_of(heard(tmp_path, asked), "w-r")
    by_day: dict[str, int] = {}
    for r in rates:
        by_day[r.meta.business_date] = by_day.get(r.meta.business_date, 0) + 1
    assert by_day == {"2007-11-05": 14, "2007-11-06": 15}


def test_the_latest_wanted(tmp_path: Path) -> None:
    rates = rates_of(heard(tmp_path, want("w-l", [JGB])), "w-l")
    assert len(rates) == 15 and {r.meta.business_date for r in rates} == {"2026-11-18"}


def test_the_record_not_held_is_reported_missing_and_waits(tmp_path: Path) -> None:
    plugin = checked(tmp_path, held=False)
    missed = [
        (i.value, i.source) for p in plugin.on("ReportMissingInstrument") for i in p.identifiers
    ]
    assert missed == [("JGB Interest Rate", "mof")] and not rates_of(plugin)


def test_wants_declined(tmp_path: Path) -> None:
    plugin = heard(
        tmp_path,
        want("w-1", [JGB], day="2026-11-17"),
        want("w-2", ["INS-ELSE"], day="2026-11-17"),
        want("w-3", [JGB], day="2026-11-15"),
        want("w-4", [JGB], day="2026-11-20"),
        want("w-5", [JGB], day="2026-11-17", data_type="meridian.v1.Price"),
        want("w-6", [JGB], day="2026-11-17", kinds=(ops.RATE_KIND_ZERO,)),
    )
    against = rates_of(plugin, "w-1")
    assert len(against) == 15 and {r.meta.business_date for r in against} == {"2026-11-17"}
    reasons = [(d.want_id, ops.UnansweredReason.Name(d.reason)) for d in plugin.on("DeclineWant")]
    assert reasons == [
        ("w-2", "UNANSWERED_REASON_NOT_COVERED"),
        ("w-3", "UNANSWERED_REASON_SOURCE_SILENT"),
        ("w-4", "UNANSWERED_REASON_SOURCE_SILENT"),
        ("w-5", "UNANSWERED_REASON_NOT_COVERED"),
        ("w-6", "UNANSWERED_REASON_NOT_COVERED"),
    ]


def test_nothing_recorded_twice_in_a_process(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE))
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    before = len(plugin.on("RecordRates"))
    asyncio.run(work.check())
    assert len(plugin.on("RecordRates")) == before


def test_the_answers_read_as_written() -> None:
    held = SyntheticPortal(lambda: AT).recordings
    current = parse(held["current"].body.decode("cp932"), "current")
    assert current.days[0].isoformat() == "2026-11-02" and not current.unread
    history = parse(held["history"].body.decode("cp932"), "history")
    assert history.days[0].isoformat() == "1974-09-24" and not history.unread
    assert history.days[-1].isoformat() == "2026-10-30"
    with pytest.raises(NotRead):
        parse("<html>Not found</html>", "current")
    with pytest.raises(NotRead):
        parse("Interest Rate,,(Unit : bp)\nDate,1Y\n2026/11/2,1.6\n", "current")
    odd = parse(
        "Interest Rate,,(Unit : %)\nDate,1Y,2Y\n2026/11/2,1.6,x\n2026/13/2,1,1\n", "current"
    )
    assert [o.text for o in odd.observations] == ["1.6"] and len(odd.unread) == 2
