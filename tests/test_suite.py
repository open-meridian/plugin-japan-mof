"""The data suite (meridian.suites), each case the Ministry of Finance's
series present mapped to the plugin's own conversion of the Ministry's
recorded answers, the whole suite passing.

The JGB interest rates are a curve of par yields, recorded as `Rate` rows
(contract v27), so it presents `a-curve-for-a-date` (the 40-year first
published on 6 November 2007, the day before holding fourteen tenors) and
`a-tenor-not-published` (5 November 2007, no 40-year), and
`a-same-day-revision`: a rate the Ministry revises within the current month
is the same row key's next version. The cases a rates-only plugin never
presents -- every case about a price, a trade, a quote or an outcome -- are
the SDK's `RATES_NOT_PRESENTED`, each with why. Beside them this plugin
names its own:

- the rates cases about what the Ministry never states here -- a fixing, a
  bill's two conventions, a rate index, another source's curve point --
  each with why;
- the calendars' two: its dataset declares no calendar (the platform holds
  none for the yen yet), and it never computes a settlement date;
- `reports-its-feed-delay`: the Ministry states no published time for a
  value;
- `records-a-datasets-liveness`: it polls hourly and records no liveness.

The cases every suite holds that the SDK answers (a replacement, the
template catalogue, an event group heard) are the SDK's.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data.testing import RATES_NOT_PRESENTED
from meridian.suites import ANSWERED_BY_SDK, Recorder, run

from japan_mof.portal import Fetched, SyntheticPortal

from conftest import AT, CURVES, INSTANCE, JGB, feed, resolving, want

PRESENTED = ("a-curve-for-a-date", "a-tenor-not-published", "a-same-day-revision")

NOT_PRESENTED = {
    **{c: why for c, why in RATES_NOT_PRESENTED.items() if c not in PRESENTED},
    "a-rate-fixing": "the Ministry publishes a curve of par yields: no fixing",
    "two-conventions-one-tenor": "the Ministry publishes no bill here: one convention a point",
    "a-curve-point-from-another-source": (
        "the Ministry publishes its curve whole: no single-point series"
    ),
    "an-index-level": "the Ministry publishes no rate index",
    "records-a-derived-series": "the Ministry's rates are rates: no derived series",
    "reads-a-calendar": "its dataset declares no calendar: the platform holds none for the yen yet",
    "asks-for-a-settlement-date": (
        "records each value as published; never computes a settlement date"
    ),
    "reports-its-feed-delay": "the Ministry states no published time for a value",
    "records-a-datasets-liveness": (
        "it polls the Ministry hourly and records no liveness: its rates change once a day"
    ),
}


class Revised(SyntheticPortal):
    """The Ministry's website, the current month read twice: as recorded,
    then with the 10-year of 17 November revised."""

    def __init__(self) -> None:
        super().__init__(lambda: AT)
        self.reads = 0

    async def get(self, path: str) -> Fetched:
        got = await super().get(path)
        if not path.endswith("/jgbcme.csv"):
            return got
        self.reads += 1
        if self.reads == 1:
            return got
        text = got.body.decode("cp932")
        line = next(x for x in text.splitlines() if x.startswith("2026/11/17,"))
        cells = line.split(",")
        cells[10] = "2.999"
        body = text.replace(line, ",".join(cells))
        assert body != text
        return Fetched(path, 200, body.encode("cp932"), got.fetched_at, got.date)


def _heard(recorder: Recorder, message: Any) -> None:
    recorder.answer("ObservationsWanted", lambda _: message)


def producers(tmp: Path) -> dict[str, Callable[[Recorder], Awaitable[None]]]:
    async def two_records(recorder: Recorder) -> None:
        resolving(recorder, ambiguous=True)
        await feed(tmp, recorder).check()

    async def revised(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder, portal=Revised())
        await work.check()
        await work.check()
        batches = [
            sorted(r.meta.row_key for r in b.rates if r.meta.business_date == "2026-11-17")
            for b in recorder.on("RecordRates")
        ]
        keys = [held for held in batches if held]
        assert len(keys) == 2 and keys[0] == keys[1]

    async def changed(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        start = datetime(2007, 11, 5, tzinfo=ZoneInfo("Asia/Tokyo"))
        _heard(
            recorder,
            want(
                "w-c",
                [JGB],
                valid_from_ns=int(start.timestamp()) * 10**9,
                valid_until_ns=int((start + timedelta(days=2)).timestamp()) * 10**9,
            ).message,
        )
        await recorder.hear(work)

    async def gap(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        _heard(recorder, want("w-g", [JGB], day="2007-11-05").message)
        await recorder.hear(work)
        sent = [r for b in recorder.on("RecordRates") for r in b.rates]
        assert sent and (40, ops.TENOR_UNIT_YEAR) not in {
            (r.tenor.count, r.tenor.unit) for r in sent
        }

    async def licences(recorder: Recorder) -> None:
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=CURVES)]),
        )
        work = feed(tmp, recorder)
        await work.wants.read_licences()
        assert work.wants.licensed == {CURVES}

    async def declined(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        _heard(recorder, want("w-2", ["INS-NOT-CARRIED"], day="2026-11-17").message)
        await recorder.hear(work)

    async def withdrawn(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        recorder.answer(
            "WantWithdrawn",
            lambda _: ops.WantWithdrawnEvent(want_id="w-standing", dataset=CURVES),
        )
        await recorder.hear(work)

    return {
        "an-asset-that-does-not-resolve": two_records,
        "a-subject-declined": declined,
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        "a-same-day-revision": revised,
        "a-curve-for-a-date": changed,
        "a-tenor-not-published": gap,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED, instance_id=INSTANCE)
    assert report.passed, report.failures
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)
    assert len(report.passed_cases) == 7 + len(ANSWERED_BY_SDK)
    assert set(PRESENTED) <= set(report.passed_cases)
    assert report.answered_by_sdk == list(ANSWERED_BY_SDK)
