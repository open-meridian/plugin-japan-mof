"""The catalogue, from code, as the deployment approves it."""

from __future__ import annotations

from japan_mof.declaration import DECLARATION


def test_one_dataset_of_rates_pushed_and_pulled() -> None:
    assert [d.key for d in DECLARATION.catalogue] == ["mof_curves"]
    (curves,) = DECLARATION.catalogue
    assert list(curves.data_types) == ["meridian.v1.Rate"] and len(curves.modes) == 2
    assert curves.day_time_zone == "Asia/Tokyo" and curves.vendor == "Ministry of Finance, Japan"
    assert curves.gap_recovery == "backfill" and not curves.calendar_id
    said = curves.terms_and_pricing
    assert "Public Data License (Version 1.0)" in said and "source citation" in said
    assert "Japan Securities Dealers Association" in said and "served, not kept" not in said
    assert len(said) <= 2000


def test_the_answers_are_kept_in_storage() -> None:
    assert DECLARATION.storage is not None
    assert [k.name for k in DECLARATION.storage.kinds] == ["responses"]
