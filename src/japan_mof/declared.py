"""What this version declares beside its role, `data` (W8.1, W4.1; the
catalogue from contract v18), built from code and used twice: `__main__`
registers with it, and `meridian plugin upload` reads it from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue: one dataset** (the product owner, items 128, 130 and 140,
2026-11-19: Tier 1, the JGB constant-maturity curve as par yields with
semiannual compounding; its key proposed, the product owner's to approve):

- **`mof_curves`**: the JGB interest rates on a constant maturity basis,
  `par_yield` rates at each tenor on the curve's record, daily, from the
  Ministry's interest rate CSVs; pushed as the Ministry publishes them and
  any past day pulled when the lake wants it.

**Kept.** The Ministry's site content is under the Public Data License
(Version 1.0), which allows commercial use with a source citation, and
leaves numerical data and simple tables outside its terms; nothing in
ruling 132 names the Ministry. So the dataset is pushed and its answers
kept, as plugin-ecb's rates are. The rates are calculated from the Japan
Securities Dealers Association's prices, whose own terms the Ministry's
pages do not state: the terms say so, for the deployment admin.

`vendor` the Ministry of Finance, no aggregator; `cadence` a day; its day
Tokyo's (the Ministry's business day), ending at midnight; no calendar (the
platform holds none for the yen yet); no venue; `history` 0, as each series
states; its terms and pricing (contract 30, ruling 1032) the Ministry's, in
plain words, and no licence declared -- a deployment's licence, set on the
Data sources page, is the one enforced; a gap asked again (`gap_recovery`
`backfill`, W10.14).

**Storage:** the Ministry's answers (raw.py), archivable, ten years by
default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration
from meridian.declaration import RecordKind

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

MOF_CURVES = "mof_curves"
KEYS = (MOF_CURVES,)
VENDOR = "Ministry of Finance, Japan"
RATE = "meridian.v1.Rate"
CADENCE = 86_400
DAY_TIME_ZONE = "Asia/Tokyo"
DAY_END_MINUTE = 0

#: The Ministry's terms, in plain words (contract 30, ruling 1032), from its
#: notice on copyright (https://www.mof.go.jp/english/about_mof/notice/index.html)
#: and its interest rates' Q&A
#: (https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm),
#: read on 2026-11-19.
TERMS = {
    MOF_CURVES: (
        "The Ministry of Finance's website: free, no key or account. The copyright of its "
        "content belongs to the Ministry unless otherwise provided, and the Public Data "
        "License (Version 1.0) applies: use, commercial use included, with a source citation, "
        "and a statement where the content is edited; numerical data and simple tables are "
        "outside its terms. The interest rates are calculated by the Ministry from the Japan "
        "Securities Dealers Association's Reference Statistical Prices for OTC Bond "
        "Transactions; the Ministry's pages do not state the Association's own terms. The "
        "values are recorded as the Ministry writes them, unedited."
    ),
}


def _dataset(key: str, data_types: list[str], modes: list[str]) -> DatasetDeclaration:
    return DatasetDeclaration(
        key=key,
        vendor=VENDOR,
        data_types=data_types,
        modes=modes,
        cadence=CADENCE,
        history=0,
        terms_and_pricing=TERMS[key],
        gap_recovery="backfill",
        day_time_zone=DAY_TIME_ZONE,
        day_end_minute=DAY_END_MINUTE,
    )


CATALOGUE = [_dataset(MOF_CURVES, [RATE], ["push", "pull"])]

RESPONSES_KIND = RecordKind(RESPONSES, "Raw responses", window_days=DEFAULT_WINDOW_DAYS)
