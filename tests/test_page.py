"""The two pages under Manage, and their read tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.suites import Recorder
from meridian.testing import PageClient

from japan_mof import page as page_module
from japan_mof.page import CONNECTION, DATASETS_PAGE, figures, hold, pages

from conftest import INSTANCE, JGB, feed, resolving, want


@pytest.fixture
def client(tmp_path: Path) -> PageClient:
    plugin = resolving(Recorder(INSTANCE))
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    asked = want("w-1", [JGB], day="2026-10-01")
    plugin.answer("ObservationsWanted", lambda _: asked.message)
    asyncio.run(plugin.hear(work))
    hold(work)
    return PageClient(pages)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert served == {
        (CONNECTION, "admin"): 200,
        (CONNECTION, "write"): 403,
        (CONNECTION, "read"): 403,
        (DATASETS_PAGE, "admin"): 200,
        (DATASETS_PAGE, "write"): 403,
        (DATASETS_PAGE, "read"): 403,
    }
    client.assert_no_account_data("2.916", "4.128", "1.671")


def test_connection_and_its_sources(client: PageClient) -> None:
    text = client.get(CONNECTION, "admin").text
    assert "No key needed" in text and "Does not stream" in text and "Sample data" in text
    sources = client.get(CONNECTION, "admin", tab="sources").text
    assert sources.count("<tr data-source=") == 2
    assert "Wed 18 Nov 2026" in sources and "Fri 30 Oct 2026" in sources


def test_datasets_and_records(client: PageClient) -> None:
    text = client.get(DATASETS_PAGE, "admin").text
    assert "japan-mof:mof_curves" in text
    records = client.get(DATASETS_PAGE, "admin", tab="records").text
    assert 'data-code="JGB Interest Rate"' in records and "Source: Ministry of Finance" in records
    assert "semiannual compounding" in records
    assert client.get(DATASETS_PAGE, "admin", q="JGB").text.count("<tr data-code=") == 1
    assert "No record matches" in client.get(DATASETS_PAGE, "admin", q="SONIA").text


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    data = client.call_tool("read_connection").data
    assert data["mode"] == "Sample data" and [s["kind"] for s in data["sources"]] == [
        "current", "history",
    ]  # fmt: skip
    assert {s["dataset"] for s in data["sources"]} == {"japan-mof:mof_curves"}
    read = client.call_tool("read_datasets").data
    (held,) = read["records"]
    assert held["code"] == "JGB Interest Rate" and held["instrument_id"] == JGB
    assert held["latest_day"] == "2026-11-18" and "Ministry of Finance" in read["attribution"]


def test_before_the_first_check_not_reached_and_not_held(tmp_path: Path) -> None:
    page_module._held.clear()
    assert "Checking the Ministry" in PageClient(pages).get(CONNECTION, "admin").text
    work = feed(tmp_path)
    work.status.sources["current"].error = "https://www.mof.go.jp/english: URLError"
    hold(work)
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert 'state="error"' in text and "Not answering" in text
    sources = PageClient(pages).get(CONNECTION, "admin", tab="sources").text
    assert sources.count("<td>Pulled when wanted") == 1
    missing = feed(tmp_path / "m", resolving(Recorder(INSTANCE), held=False))
    asyncio.run(missing.check())
    hold(missing)
    assert "1 record not held" in PageClient(pages).get(CONNECTION, "admin").text


def test_the_figures_are_the_data_roles(client: PageClient) -> None:
    work = page_module._held["feed"]
    said = figures(work.status, work)
    assert [f.label for f in said][:3] == ["Connection", "Entitled at the vendor", "Stream"]
