"""The Ministry of Finance's series this version carries, what each one is,
and the record it is recorded against: the plugin's series map.

**The JGB curve** (`mof_curves`, the Ministry's interest rate CSVs). The
Ministry publishes one table a business day, "Interest Rate", in per cent
("(Unit : %)"): the Japanese Government Bonds' interest rates on a constant
maturity basis at 1 to 10, 15, 20, 25, 30 and 40 years. Each is a
`par_yield` (ruling 130: a constant-maturity series is a par yield with its
publisher's convention) at its tenor on one `rate_curve` record, as the
Ministry states it: "The semiannual compound interest rate on a constant
maturity basis calculated on prevailing prices of fixed income JGBs in the
secondary market at the market closing time (3pm) is released"
(https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm).
So the compounding is semiannual, the Ministry's statement. It states no
day count; the plugin states the JGBs' own, actual/365 with no leap day
counted (NL/365), and says so on the Datasets page. A tenor the Ministry
writes as `-` (the 40-year before 6 November 2007, the 15 to 30-year
before their first issue) is no row, never a zero.

The record is asked of the deployment by the Ministry's name for the table,
"JGB Interest Rate", as a `symbol` at the source `mof`, a name **proposed**
with this version for the platform's seed; the platform seeds none yet, so
until a deployment holds the record its values wait, reported missing,
never minted.
"""

from __future__ import annotations

from dataclasses import dataclass

from meridian.operations import RateConvention

SOURCE = "mof"
RATE_CURVE = "rate_curve"

#: The Ministry's compounding (semiannual), with the JGBs' day count, the
#: plugin's statement.
SEMIANNUAL = RateConvention(day_count="nl_365", compounding="compounded", periods_per_year=2)
#: The tenors the table states, as its header names them.
TENORS = (
    "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "8Y", "9Y", "10Y", "15Y", "20Y", "25Y", "30Y", "40Y",
)  # fmt: skip


@dataclass(frozen=True)
class Record:
    """A referential record, by the code proposed for it at `mof`."""

    code: str
    instrument_type: str
    description: str

    @property
    def identifier(self) -> tuple[str, str, str]:
        return ("symbol", self.code, SOURCE)


JGB_RECORD = Record(
    "JGB Interest Rate",
    RATE_CURVE,
    "Japanese Government Bonds' interest rates on a constant maturity basis (Ministry of Finance)",
)
RECORDS = (JGB_RECORD,)
