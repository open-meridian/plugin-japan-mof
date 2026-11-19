"""The Ministry of Finance's JGB interest rates into the lake: the current
month recorded as the Ministry publishes it, and any day recorded when the
lake wants it (W10.4, W10.7), through the SDK's rates helpers
(`meridian.roles.data.rates`) and its `Wants`.

**Push.** At start and every hour, the current month's file is read. An
answer whose values read as the last one this process recorded records
nothing; any other is recorded whole, in the lake's batches, and the lake
answers each value it holds unchanged. A value the Ministry revises is the
same row key's next version.

**Pull.** A want of a day in the current month's file is read from it; a
day before it from the history since 1974, read at most once a day a
process and kept for the day.

**Rows** (series.py says each): each tenor's rate a `par_yield` at its
tenor on the curve's record, semiannually compounded. A tenor the Ministry
states nothing for is no row, never a zero. Each is read from the
Ministry's text as a `Decimal`, never a float.

**Published time.** The Ministry releases the rates "at 9:30 a.m. on the
next business day" and states no time on a value: no row states one, rather
than a wrong one.

**Subject.** The curve's record by its code at `mof` (series.py), resolved
once per process; where the deployment does not hold it, it is reported
missing and its values wait. The plugin mints nothing.

**Wants.** A want of `mof_curves` for the curve's record -- a business
date, a range of at most a year, or the latest -- is read from the Ministry
and recorded against the want; a day the Ministry states nothing for, or
one not come yet, is declined `source_silent`; any other subject, or
another kind of data, `not_covered`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from .answers import NotRead, Observations, parse
from .declared import DAY_TIME_ZONE, KEYS, MOF_CURVES, RATE
from .portal import CURRENT, HISTORY, PATHS, SOURCES, Fetched, Portal, PortalUnreachable, utc_now
from .raw import RawStore
from .series import JGB_RECORD, SEMIANNUAL, SOURCE, Record

log = logging.getLogger("japan_mof")

TOKYO = ZoneInfo(DAY_TIME_ZONE)
#: The most days one want is answered for: a year.
MOST_DAYS = 366


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


@dataclass(frozen=True)
class Outcome:
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    unresolved: tuple[str, ...] = ()


@dataclass
class Held:
    """A record as the plugin last saw it: the deployment's instrument, or
    why there is none, and the latest day recorded."""

    code: str
    name: str = ""
    instrument_id: str = ""
    miss: str = ""
    latest_day: date | None = None


@dataclass
class SourceStatus:
    """What the plugin last did with one source, for its pages."""

    source: str
    checked_at: datetime | None = None
    read_at: datetime | None = None
    error: str = ""
    first_day: date | None = None
    latest_day: date | None = None
    fetches: int = 0
    unread: dict[str, int] = field(default_factory=dict)


@dataclass
class Status:
    """What the plugin last did, for its pages; lost on a restart."""

    mode: str = "live"
    started_at: datetime | None = None
    sources: dict[str, SourceStatus] = field(
        default_factory=lambda: {s: SourceStatus(s) for s in SOURCES}
    )
    records: dict[str, Held] = field(default_factory=dict)

    @property
    def checked_at(self) -> datetime | None:
        stamps = [s.checked_at for s in self.sources.values() if s.checked_at]
        return max(stamps) if stamps else None

    @property
    def error(self) -> str:
        return next((s.error for s in self.sources.values() if s.error), "")

    @property
    def fetches(self) -> int:
        return sum(s.fetches for s in self.sources.values())

    @property
    def read(self) -> bool:
        return any(s.read_at for s in self.sources.values())


class Feed(data.Role):
    """The plugin's data role class, its acts made on itself -- registered
    with `meridian.run`, or bound to the suite's recorder in its tests."""

    def __init__(
        self, portal: Portal, raw: RawStore, now: Callable[[], datetime] = utc_now
    ) -> None:
        self.portal = portal
        self.raw = raw
        self.now = now
        self.wants = data.Wants(self, KEYS, clock_ns=lambda: _ns(self.now()))
        self.rates = rates.Feed(
            self, SOURCE, wants=self.wants, day_zone=DAY_TIME_ZONE, clock_ns=lambda: _ns(self.now())
        )
        self.status = Status(mode=portal.mode, started_at=now())
        self._recorded = ""
        #: The history as read today: its day, what it held and its key.
        self._history: tuple[date, Observations, str] | None = None

    def today(self) -> date:
        return self.now().astimezone(TOKYO).date()

    def use(self, portal: Portal) -> None:
        """Read from `portal` from now on: sample data turned on or off."""
        if portal.mode != self.portal.mode:
            self.portal = portal
            self.status.mode = portal.mode
            self._recorded = ""
            self._history = None

    # ── Reading ─────────────────────────────────────────────────────────

    async def read(self, source: str) -> tuple[Observations, str]:
        """`source`'s file read, and the answer's key in storage.
        PortalUnreachable or NotRead otherwise."""
        held = self.status.sources[source]
        held.checked_at = self.now()
        try:
            fetched: Fetched = await self.portal.get(PATHS[source])
            held.fetches += 1
            key = self.raw.keep(fetched)
            if fetched.status != 200:
                raise PortalUnreachable(f"{fetched.url[:120]} answered {fetched.status}")
            read = parse(fetched.text, source)
        except (PortalUnreachable, NotRead) as failed:
            held.error = str(failed)
            raise
        held.error, held.read_at = "", self.now()
        if read.days:
            held.first_day, held.latest_day = read.days[0], read.days[-1]
        for line in read.unread:
            held.unread[line] = held.unread.get(line, 0) + 1
        return read, key

    async def history(self) -> tuple[Observations, str]:
        """The history since 1974, read at most once a day a process."""
        if self._history is not None and self._history[0] == self.today():
            return self._history[1], self._history[2]
        read, key = await self.read(HISTORY)
        self._history = (self.today(), read, key)
        return read, key

    # ── Resolving ───────────────────────────────────────────────────────

    async def record_of(self, record: Record) -> str:
        """A record's instrument, by its code at `mof`; empty, reported
        missing, where the deployment holds none."""
        held = self.status.records.setdefault(record.code, Held(record.code, record.description))
        if held.instrument_id:
            return held.instrument_id
        found = await self.rates.subject(
            record.identifier,
            description=record.description,
            instrument_type=record.instrument_type,
        )
        held.instrument_id, held.miss = found, "" if found else "not held: reported missing"
        return found

    # ── Recording ───────────────────────────────────────────────────────

    async def _rows(self, read: Observations, key: str, days: set[date] | None) -> list[Any]:
        rows: list[Any] = []
        subject = await self.record_of(JGB_RECORD)
        if not subject:
            return rows
        held = self.status.records[JGB_RECORD.code]
        for seen in read.observations:
            if days is not None and seen.day not in days:
                continue
            raw_key = self.raw.noted(f"{seen.tenor}:{seen.day}={seen.text}", seen.day, key)[0].key
            rows.append(
                self.rates.rate(
                    subject,
                    MOF_CURVES,
                    "par_yield",
                    rates.percent(seen.text),
                    business_date=seen.day,
                    convention=SEMIANNUAL,
                    tenor=seen.tenor,
                    series=JGB_RECORD.code,
                    raw_key=raw_key,
                )
            )
            if held.latest_day is None or seen.day > held.latest_day:
                held.latest_day = seen.day
        return rows

    async def record(
        self,
        read: Observations,
        key: str,
        *,
        want_id: str = "",
        days: Iterable[date] | None = None,
    ) -> tuple[Outcome, int]:
        """Record `read` -- on `days` where given -- against `want_id` where
        given. What the lake answered, and how many rows were sent."""
        rows = await self._rows(read, key, set(days) if days is not None else None)
        unresolved = tuple(h.code for h in self.status.records.values() if h.miss)
        self.raw.save_firsts()
        counts = self.wants.sent_to(MOF_CURVES)
        before = (counts.recorded, counts.restated, counts.unchanged)
        if rows:
            await self.rates.record(MOF_CURVES, rows, want_id)
        outcome = Outcome(
            counts.recorded - before[0],
            counts.restated - before[1],
            counts.unchanged - before[2],
            unresolved,
        )
        return outcome, len(rows)

    async def check(self) -> Outcome | None:
        """Read the current month and record it where this process has not
        recorded it as it reads now."""
        try:
            read, key = await self.read(CURRENT)
        except (PortalUnreachable, NotRead) as failed:
            log.warning("the current month was not read: %s", failed)
            return None
        digest = digest_of(read)
        if digest == self._recorded:
            return None
        outcome, _ = await self.record(read, key)
        if not outcome.unresolved:
            self._recorded = digest
        held = self.status.sources[CURRENT]
        log.info(
            "rates of %s to %s: %d recorded, %d restated, %d unchanged%s",
            held.first_day,
            held.latest_day,
            outcome.recorded,
            outcome.restated,
            outcome.unchanged,
            f"; not held: {', '.join(outcome.unresolved)}" if outcome.unresolved else "",
        )
        return outcome

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)
        log.info("standing want %s withdrawn", heard.message.want_id)

    def _days(self, want: ops.ObservationsWantedEvent) -> list[date] | None:
        """The days a want asks; None where it asks only the latest."""
        if want.business_date:
            return [date.fromisoformat(want.business_date)]
        if want.valid_from_ns or want.valid_until_ns:
            # Whole seconds, so the last nanosecond before a midnight is
            # that day's, never rounded into the next.
            start = datetime.fromtimestamp(want.valid_from_ns // 10**9, TOKYO).date()
            until = want.valid_until_ns - 1 if want.valid_until_ns else _ns(self.now())
            end = datetime.fromtimestamp(until // 10**9, TOKYO).date()
            span = [start + timedelta(days=n) for n in range((end - start).days + 1)]
            return span[-MOST_DAYS:]
        return None

    async def _wanted(
        self, days: list[date] | None
    ) -> tuple[list[tuple[Observations, str]], set[date]]:
        """The answers holding `days` (the latest where None), and the days
        to record from them."""
        current, key = await self.read(CURRENT)
        if days is None:
            return [(current, key)], set(current.days[-1:])
        # The current month's file holds its month; a day before is the
        # history's. Before its first publication of a month the file holds
        # none, and every day is the history's.
        cut = current.days[0].replace(day=1) if current.days else self.today() + timedelta(days=1)
        reads = [(current, key)]
        if min(days) < cut:
            history, history_key = await self.history()
            older = Observations(HISTORY, [o for o in history.observations if o.day < cut])
            reads.append((older, history_key))
        return reads, set(days)

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from the Ministry: its values recorded against
        it, and each subject declined, with why."""
        if key != MOF_CURVES or want.data_type not in ("", RATE):
            return {s: "not_covered" for s in subjects}
        if kinds and ops.RATE_KIND_PAR_YIELD not in kinds:
            return {s: "not_covered" for s in subjects}
        held = await self.record_of(JGB_RECORD)
        declined = {s: "not_covered" for s in subjects if not held or s != held}
        if held not in subjects:
            return declined
        if want.standing:
            self.wants.stand(want, [held], kinds)
        days = self._days(want)
        if days is not None:
            days = [d for d in days if d <= self.today()]
        sent = 0
        if days is None or days:
            try:
                reads, wanted = await self._wanted(days)
                for read, raw_key in reads:
                    _, rows = await self.record(read, raw_key, want_id=want.want_id, days=wanted)
                    sent += rows
            except (PortalUnreachable, NotRead) as failed:
                log.warning("want %s: the Ministry was not read: %s", want.want_id, failed)
        if not sent:
            declined[held] = "source_silent"
        return declined


def digest_of(read: Observations) -> str:
    """What an answer states, as a short digest: its values alone."""
    stated = repr([(o.day, o.tenor, o.text) for o in read.observations]).encode()
    return hashlib.sha256(stated).hexdigest()[:16]
