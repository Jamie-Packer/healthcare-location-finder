"""Build the location marts with dbt."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT = Path(sys.executable).with_name("dbt.exe")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build location models")
    parser.add_argument("--fixtures", action="store_true", help="Build the tiny fixture project")
    args = parser.parse_args()
    raw = ROOT / "dbt" / "fixtures" if args.fixtures else ROOT / "data" / "raw"
    database = ROOT / "data" / "build" / ("fixtures.duckdb" if args.fixtures else "locations.duckdb")
    mart = ROOT / "data" / "build" / "fixture-mart" if args.fixtures else ROOT / "data" / "mart"
    database.parent.mkdir(parents=True, exist_ok=True)
    mart.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LOCATIONS_DUCKDB"] = database.as_posix()
    env["MART_DIR"] = mart.as_posix()
    subprocess.run(
        [
            str(DBT),
            "build",
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
            "--vars",
            (
                '{"raw_root": "'
                + raw.as_posix()
                + '", "postcodes_format": "'
                + ("csv" if args.fixtures else "parquet")
                + '"}'
            ),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
