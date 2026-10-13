import os
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import data as app_data
from app.data import LocationData, currency_markdown, edition_label

ROOT = Path(__file__).resolve().parents[1]


def _search_app(fixture_mart) -> AppTest:
    os.environ["LOCATIONS_MART_DIR"] = str(fixture_mart)
    app = AppTest.from_file(str(ROOT / "app" / "search.py"), default_timeout=30)
    app.run()
    assert not app.exception
    return app


def _counts(app: AppTest) -> int:
    for element in app.main:
        match = re.search(r"([\d,]+) current sites", str(getattr(element, "value", "")))
        if match:
            return int(match.group(1).replace(",", ""))
    raise AssertionError("no site count on the page")


def test_edition_label():
    assert edition_label("NSPL_AUG_2026") == "August 2026"


def test_currency_uses_the_manifest_dates(tmp_path):
    text = currency_markdown(
        LocationData(
            directory=tmp_path,
            source="release",
            manifest={
                "built_at": "2026-10-13T04:00:00+00:00",
                "nspl_edition": "NSPL_AUG_2026",
                "sources": [
                    {"key": "cqc/active_locations.ods", "publisher_date": "2026-10-01"},
                ],
            },
        )
    )
    assert "13 October 2026" in text
    assert "1 October 2026" in text
    assert "August 2026" in text
    assert "Monday at 04:00 UTC" in text


def test_search_finds_kent(fixture_mart):
    app = _search_app(fixture_mart)
    assert any("two characters" in str(item.value) for item in app.caption)
    app.text_input[0].set_value("Kent").run()
    assert not app.exception
    labels = [str(option) for option in app.selectbox[0].options]
    assert any("Kent" in label for label in labels)
    assert any(button.label == "Prepare download" for button in app.button)


def test_how_to_use_is_on_the_search_page(fixture_mart):
    app = _search_app(fixture_mart)
    assert [item.label for item in app.expander] == ["How to use"]
    assert app.expander[0].proto.expanded is True
    app.text_input[0].set_value("Kent").run()
    assert app.expander[0].proto.expanded is False


def test_service_filter_accepts_several_types(fixture_mart):
    app = _search_app(fixture_mart)
    app.text_input[0].set_value("TN24 0LZ").run()
    assert not app.exception
    everything = _counts(app)
    assert everything >= 2

    app.pills[0].set_value(["hospital"]).run()
    hospitals = _counts(app)
    app.pills[0].set_value(["gp"]).run()
    gps = _counts(app)
    app.pills[0].set_value(["hospital", "gp"]).run()
    assert not app.exception
    assert _counts(app) == hospitals + gps
    assert hospitals < everything

    app.pills[0].set_value([]).run()
    assert _counts(app) == everything


def test_changing_the_service_clears_the_prepared_download(fixture_mart):
    app = _search_app(fixture_mart)
    app.text_input[0].set_value("TN24 0LZ").run()
    next(button for button in app.button if button.label == "Prepare download").click().run()
    assert app.session_state["export_csv"]
    app.pills[0].set_value(["hospital"]).run()
    assert "export_csv" not in app.session_state


def test_help_page_keeps_its_sections(fixture_mart):
    os.environ["LOCATIONS_MART_DIR"] = str(fixture_mart)
    app = AppTest.from_file(str(ROOT / "app" / "help.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert [header.value for header in app.header] == [
        "How to use it",
        "What you can and cannot find",
        "How current the data is",
        "Sources and licence",
        "Columns",
    ]


def test_sample_files_are_present():
    sample = ROOT / "data" / "sample"
    for name in ("location.parquet", "search_entity.parquet", "entity_site.parquet", "manifest.json"):
        assert (sample / name).exists()
        assert (sample / name).stat().st_size > 0


@pytest.fixture
def no_local_mart(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCATIONS_MART_DIR", raising=False)
    monkeypatch.setattr(app_data, "LOCAL", tmp_path / "missing")
    app_data._cached_release.clear()
    yield
    app_data._cached_release.clear()


def test_failed_download_falls_back_to_the_sample_and_retries(monkeypatch, no_local_mart):
    calls = []

    def failing():
        calls.append(1)
        return None

    monkeypatch.setattr(app_data, "_download_release", failing)
    assert app_data.ensure_data().source == "sample"
    assert app_data.ensure_data().source == "sample"
    assert len(calls) == 2


def test_successful_download_is_cached(monkeypatch, no_local_mart):
    calls = []

    def working():
        calls.append(1)
        return ROOT / "data" / "sample"

    monkeypatch.setattr(app_data, "_download_release", working)
    assert app_data.ensure_data().source == "release"
    assert app_data.ensure_data().source == "release"
    assert len(calls) == 1


def test_download_rejects_a_release_with_a_tiny_parquet(monkeypatch, tmp_path):
    class Response:
        status_code = 200
        headers = {"Content-Type": "application/octet-stream"}
        content = b"tiny"

        def raise_for_status(self):
            return None

    monkeypatch.setenv("LOCATIONS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(app_data.requests.Session, "get", lambda self, *args, **kwargs: Response())
    assert app_data._download_release() is None
    assert not (tmp_path / "cache").exists()
    assert not (tmp_path / "cache.partial").exists()
