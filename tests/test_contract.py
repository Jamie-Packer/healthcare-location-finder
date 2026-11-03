from pathlib import Path

from ingest.contract import attribution_markdown, dictionary_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_dictionary_matches_the_contract():
    saved = (ROOT / "docs" / "data_dictionary.md").read_text(encoding="utf-8")
    assert saved == dictionary_markdown()


def test_attribution_names_the_sources():
    text = attribution_markdown(2026)
    assert "Open Government Licence" in text
    assert "Care Quality Commission" in text
    assert "2026" in text
