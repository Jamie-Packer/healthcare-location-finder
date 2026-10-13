import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.data import LocationData, currency_markdown, edition_label

ROOT = Path(__file__).resolve().parents[1]


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
    os.environ["LOCATIONS_MART_DIR"] = str(fixture_mart)
    app = AppTest.from_file(str(ROOT / "app" / "search.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert any("two characters" in str(item.value) for item in app.info)
    app.text_input[0].set_value("Kent").run()
    assert not app.exception
    labels = [str(option) for option in app.selectbox[0].options]
    assert any("Kent" in label for label in labels)
    assert any(button.label == "Prepare download" for button in app.button)


def test_sample_files_are_present():
    sample = ROOT / "data" / "sample"
    for name in ("location.parquet", "search_entity.parquet", "entity_site.parquet", "manifest.json"):
        assert (sample / name).exists()
        assert (sample / name).stat().st_size > 0
