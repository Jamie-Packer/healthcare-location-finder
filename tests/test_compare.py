import csv
from pathlib import Path

import duckdb

from ingest.compare import write_comparison


def _location(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = ", ".join(
        f"('{location_id}', '{name}', '{parent}', '{code}', 'CQC', '{code}')"
        for location_id, name, parent, code in rows
    )
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from (values {values})
            as t(location_id, name, parent_code, nhs_code, regulator, regulator_id)
        ) to '{path.as_posix()}' (format parquet)
        """
    )
    connection.close()


def _entities(path: Path, rows: list[tuple]) -> None:
    values = ", ".join(f"('{entity_id}', '{name}')" for entity_id, name in rows)
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from (values {values}) as t(entity_id, name)
        ) to '{path.as_posix()}' (format parquet)
        """
    )
    connection.close()


def _links(path: Path, rows: list[tuple]) -> None:
    values = ", ".join(f"('{entity_id}', '{location_id}')" for entity_id, location_id in rows)
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from (values {values}) as t(entity_id, location_id)
        ) to '{path.as_posix()}' (format parquet)
        """
    )
    connection.close()


def _pair(root: Path, name: str, location_rows, entity_rows, link_rows) -> Path:
    directory = root / name
    directory.mkdir()
    _location(directory / "location.parquet", location_rows)
    _entities(directory / "search_entity.parquet", entity_rows)
    _links(directory / "entity_site.parquet", link_rows)
    return directory


def test_rename_keeps_identity_and_removal_is_reported(tmp_path):
    previous = _pair(
        tmp_path,
        "previous",
        [("a", "Old Name", "RXX", "RX1"), ("b", "Closing", "RXX", "RX2")],
        [("site:a", "Old Name"), ("site:b", "Closing"), ("provider:RXX", "Trust")],
        [("site:a", "a"), ("site:b", "b"), ("provider:RXX", "a"), ("provider:RXX", "b")],
    )
    current = _pair(
        tmp_path,
        "current",
        [("a", "New Name", "RXX", "RX1")],
        [("site:a", "New Name"), ("provider:RXX", "Trust")],
        [("site:a", "a"), ("provider:RXX", "a")],
    )
    summary = write_comparison(current, previous, tmp_path / "diff")
    assert summary["performed"] is True
    changes = {(item["record_type"], item["change"]): item["rows"] for item in summary["changes"]}
    assert changes[("site", "renamed")] == 1
    assert changes[("site", "removed")] == 1
    assert ("site", "added") not in changes
    text = (tmp_path / "diff" / "identity_changes.csv").read_text(encoding="utf-8")
    assert "transition" not in text


def test_ambiguous_identifier_is_not_resolved(tmp_path):
    previous = _pair(
        tmp_path,
        "previous",
        [("a", "One", "RXX", "SHARED")],
        [("site:a", "One")],
        [("site:a", "a")],
    )
    current = _pair(
        tmp_path,
        "current",
        [("b", "Left", "RXX", "SHARED"), ("c", "Right", "RXX", "SHARED")],
        [("site:b", "Left"), ("site:c", "Right")],
        [("site:b", "b"), ("site:c", "c")],
    )
    summary = write_comparison(current, previous, tmp_path / "diff")
    assert summary["identity"]["transitions"] == 0
    assert summary["identity"]["unresolved"] >= 2
    with (tmp_path / "diff" / "identity_changes.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    current_sites = {row["location_id"] for row in rows if row["location_id"]}
    assert {"b", "c"} <= current_sites
    assert all(row["change"] == "unresolved" for row in rows)
    assert all(not (row["previous_location_id"] and row["location_id"]) for row in rows)


def test_missing_previous_release_is_recorded(tmp_path):
    current = _pair(
        tmp_path,
        "current",
        [("a", "Only", "RXX", "RX1")],
        [("site:a", "Only")],
        [("site:a", "a")],
    )
    summary = write_comparison(current, None, tmp_path / "diff")
    assert summary == {
        "performed": False,
        "reason": "no previous release",
        "previous_build_id": None,
    }


def test_identifier_transition_follows_the_source_code(tmp_path):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    for directory, location_id in ((previous, "old-id"), (current, "new-id")):
        connection = duckdb.connect()
        connection.execute(
            f"""
            copy (
                select
                    '{location_id}' as location_id,
                    'Ward' as name,
                    'RXX' as parent_code,
                    'NH1' as nhs_code,
                    'CQC' as regulator,
                    '1-110' as regulator_id
            ) to '{(directory / "location.parquet").as_posix()}' (format parquet)
            """
        )
        connection.execute(
            f"""
            copy (
                select * from (values
                    ('site:{location_id}', 'cqc_location', '1-110', 'primary', 'cqc'),
                    ('site:{location_id}', 'ods', 'NH1', '{'additional' if location_id == 'old-id' else 'primary'}', 'ods')
                ) as t(entity_id, identifier_system, identifier_value, identifier_role, source)
            ) to '{(directory / "entity_identifier.parquet").as_posix()}' (format parquet)
            """
        )
        connection.close()
        _entities(directory / "search_entity.parquet", [(f"site:{location_id}", "Ward")])
        _links(directory / "entity_site.parquet", [(f"site:{location_id}", location_id)])
    summary = write_comparison(current, previous, tmp_path / "diff")
    assert summary["identity"]["transitions"] >= 1
    assert summary["identity"]["unresolved"] == 0
    text = (tmp_path / "diff" / "identity_changes.csv").read_text(encoding="utf-8")
    assert "old-id" in text and "new-id" in text and "1-110" in text
    changes = (tmp_path / "diff" / "entity_changes.csv").read_text(encoding="utf-8")
    assert "old-id" not in changes
    assert "new-id" not in changes


def test_a_rekeyed_rename_stays_a_rename(tmp_path):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    previous.mkdir()
    current.mkdir()
    connection = duckdb.connect()
    for directory, location_id, name in (
        (previous, "old-id", "Old Ward"),
        (current, "new-id", "New Ward"),
    ):
        connection.execute(
            f"""
            copy (
                select
                    '{location_id}' as location_id,
                    '{name}' as name,
                    'RXX' as parent_code,
                    'NH1' as nhs_code,
                    'CQC' as regulator,
                    '1-110' as regulator_id
            ) to '{(directory / "location.parquet").as_posix()}' (format parquet)
            """
        )
        _entities(directory / "search_entity.parquet", [(f"site:{location_id}", name), ("provider:RXX", "Trust")])
        _links(
            directory / "entity_site.parquet",
            [(f"site:{location_id}", location_id), ("provider:RXX", location_id)],
        )
    connection.close()
    summary = write_comparison(current, previous, tmp_path / "diff")
    changes = {(item["record_type"], item["change"]): item["rows"] for item in summary["changes"]}
    assert changes[("site", "renamed")] == 1
    assert changes[("entity", "renamed")] == 1
    assert ("site", "added") not in changes
    assert ("site", "removed") not in changes
    assert ("membership", "added") not in changes
    assert ("membership", "removed") not in changes
    with (tmp_path / "diff" / "entity_changes.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    renamed = next(row for row in rows if row["record_type"] == "site")
    assert renamed["previous_value"] == "Old Ward"
    assert renamed["current_value"] == "New Ward"
    assert renamed["record_id"] == "new-id"
