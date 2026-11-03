"""Build the location marts with dbt."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dbt_build(
    fixtures: bool = False,
    raw_root: Path | None = None,
    mart_dir: Path | None = None,
    database: Path | None = None,
) -> Path:
    """Run dbt build for the full raw files, or the tiny fixture project."""
    from dbt.cli.main import dbtRunner

    raw = raw_root or (ROOT / "dbt" / "fixtures" if fixtures else ROOT / "data" / "raw")
    database = database or (
        ROOT / "data" / "build" / ("fixtures.duckdb" if fixtures else "locations.duckdb")
    )
    mart = mart_dir or (
        ROOT / "data" / "build" / "fixture-mart" if fixtures else ROOT / "data" / "mart"
    )
    database.parent.mkdir(parents=True, exist_ok=True)
    mart.mkdir(parents=True, exist_ok=True)
    os.environ["LOCATIONS_DUCKDB"] = database.as_posix()
    os.environ["MART_DIR"] = mart.as_posix()
    common = [
        "--project-dir",
        str(ROOT / "dbt"),
        "--profiles-dir",
        str(ROOT / "dbt"),
        "--vars",
        json.dumps(
            {
                "raw_root": raw.as_posix(),
                "postcodes_format": "csv" if fixtures else "parquet",
                "fixtures": fixtures,
            }
        ),
    ]
    runner = dbtRunner()
    # Seeds are small. Refreshing them picks up a new column without touching the snapshot.
    for command in (["seed", "--full-refresh"], ["build"]):
        result = runner.invoke([*command, *common])
        if not result.success:
            detail = result.exception or "dbt build failed"
            raise SystemExit(detail)
    return mart


def database_path(fixtures: bool = False) -> Path:
    name = "fixtures.duckdb" if fixtures else "locations.duckdb"
    return ROOT / "data" / "build" / name


def main() -> None:
    parser = argparse.ArgumentParser(description="Build location models")
    parser.add_argument("--fixtures", action="store_true", help="Build the tiny fixture project")
    args = parser.parse_args()
    dbt_build(fixtures=args.fixtures)


if __name__ == "__main__":
    main()
    sys.exit(0)
