import csv
import os
import shutil
from pathlib import Path

import duckdb

from ingest.build import dbt_build
from ingest.compare import write_comparison

ROOT = Path(__file__).resolve().parents[1]


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="\n", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _id_for(mart: Path, regulator_id: str) -> str:
    connection = duckdb.connect()
    try:
        return connection.execute(
        f"""
        select location_id
        from read_parquet('{(mart / "location.parquet").as_posix()}')
        where regulator_id = '{regulator_id}'
        """
        ).fetchone()[0]
    finally:
        connection.close()


def test_ids_survive_a_rewrite_and_a_code_change_is_a_transition(tmp_path):
    saved = {name: os.environ.get(name) for name in ("LOCATIONS_DUCKDB", "MART_DIR", "LOCATIONS_MART_DIR")}
    raw = tmp_path / "raw"
    shutil.copytree(ROOT / "dbt" / "fixtures", raw)
    first = tmp_path / "first"
    second = tmp_path / "second"
    third = tmp_path / "third"
    try:
        dbt_build(True, raw, first, tmp_path / "first.duckdb")
        before = _id_for(first, "1-101")
        locations = raw / "cqc" / "locations.csv"
        fields, rows = _rows(locations)
        for row in rows:
            if row["cqc_location_id"] == "1-101":
                row["name"] = "Renamed Nursing Home"
                row["address_1"] = "New Road"
        _write(locations, fields, list(reversed(rows)))
        dbt_build(True, raw, second, tmp_path / "second.duckdb")
        assert _id_for(second, "1-101") == before

        fields, rows = _rows(locations)
        for row in rows:
            if row["cqc_location_id"] == "1-101":
                row["ods_code"] = "NH1"
        _write(locations, fields, rows)
        dbt_build(True, raw, third, tmp_path / "third.duckdb")
        after = _id_for(third, "1-101")
        assert after != before
        summary = write_comparison(third, second, tmp_path / "diff")
        assert summary["identity"]["transitions"] >= 1
        assert summary["identity"]["unresolved"] == 0
        text = (tmp_path / "diff" / "identity_changes.csv").read_text(encoding="utf-8")
        assert "1-101" in text
        assert before in text and after in text
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
