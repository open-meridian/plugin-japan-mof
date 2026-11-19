"""The Ministry of Finance's answers, read as the Ministry wrote them.

Each interest rate CSV -- the current month's and the history since 1974 --
is a title line, `Interest Rate (November 2026)` or `Interest Rate`, its
last cell `(Unit : %)`; a header line, `Date` then each tenor (`1Y` to
`40Y`); then one line a business day, its date as `2026/11/2`, each tenor's
rate as the Ministry writes it, `-` where it states none: no value, never a
zero. The current month's file ends with a note to the reader, which is not
a day. The files are in the Ministry's Japanese encoding (Shift_JIS); the
figures are ASCII.

A value is kept as the text the Ministry wrote, and read as a `Decimal`
from it, never a float; a value that does not read is kept as not read, and
never recorded.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .series import TENORS

MISSING = {"", "-"}
#: The unit the title line states.
PER_CENT = "(Unit : %)"


class NotRead(Exception):  # noqa: N818 - what the answer was not
    """An answer that is not what was asked for."""


@dataclass(frozen=True)
class Observation:
    """One value as the Ministry stated it: its day, tenor and text."""

    day: date
    tenor: str
    text: str

    @property
    def value(self) -> Decimal:
        return Decimal(self.text)


@dataclass
class Observations:
    """An answer read: its values in order, and the values that did not read."""

    source: str
    observations: list[Observation] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)

    @property
    def days(self) -> list[date]:
        return sorted({o.day for o in self.observations})

    def on(self, day: date) -> dict[str, Observation]:
        return {o.tenor: o for o in self.observations if o.day == day}


def _number(text: str) -> bool:
    try:
        return Decimal(text).is_finite()
    except InvalidOperation:
        return False


def parse(text: str, source: str) -> Observations:
    """An interest rate CSV, read; NotRead where it is not one, or does not
    state its unit as per cent."""
    read = Observations(source)
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if len(rows) < 2 or not rows[0] or not rows[0][0].startswith("Interest Rate"):
        raise NotRead(f"the answer is not the Ministry's interest rate CSV: {text[:80]!r}")
    if PER_CENT not in [c.strip() for c in rows[0]]:
        raise NotRead(f"the table does not state its unit as per cent: {rows[0][-1][:40]!r}")
    header = [h.strip() for h in rows[1]]
    if header[:1] != ["Date"] or not {h for h in header[1:] if h} <= set(TENORS):
        raise NotRead(f"the table's header is not Date and the tenors: {header[:4]!r}")
    for row in rows[2:]:
        first = row[0].strip() if row else ""
        if not first[:1].isdigit():
            continue  # an empty line or the note to the reader
        try:
            day = datetime.strptime(first, "%Y/%m/%d").date()
        except ValueError:
            read.unread.append(f"{source}: a day {first[:20]!r}")
            continue
        for tenor, stated in zip(header[1:], row[1:], strict=False):
            said = stated.strip()
            if not tenor or said in MISSING:
                continue
            if not _number(said):
                read.unread.append(f"{tenor} {day}: {said[:40]!r}")
                continue
            read.observations.append(Observation(day, tenor, said))
    read.observations.sort(key=lambda o: (o.day, TENORS.index(o.tenor)))
    return read
