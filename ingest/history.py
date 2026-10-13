"""Keep dbt snapshot rows across ephemeral build machines."""

from __future__ import annotations

from pathlib import Path

import duckdb

SNAPSHOT = "snap_location"
REQUIRED = {
    "location_id",
    "name",
    "parent_name",
    "dbt_scd_id",
    "dbt_updated_at",
    "dbt_valid_from",
    "dbt_valid_to",
}
ADDED = {"postcode": "VARCHAR", "ods_code": "VARCHAR"}


def restore_history(database: Path, history: Path) -> bool:
    """Load a previous snapshot export. Returns false when there is nothing to load."""
    if not history.exists() or history.stat().st_size == 0:
        print("no previous location history", flush=True)
        return False
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(database.as_posix())
    try:
        columns = {
            row[0]
            for row in connection.sql(
                f"describe select * from read_parquet('{history.as_posix()}')"
            ).fetchall()
        }
        if not REQUIRED <= columns:
            print("previous location history does not match this snapshot; starting again", flush=True)
            return False
        connection.execute(
            f"create or replace table {SNAPSHOT} as select * from read_parquet('{history.as_posix()}')"
        )
        present = {row[0] for row in connection.execute(f"describe {SNAPSHOT}").fetchall()}
        for name, kind in ADDED.items():
            if name not in present:
                connection.execute(f"alter table {SNAPSHOT} add column {name} {kind}")
    finally:
        connection.close()
    print(f"restored {history.name}", flush=True)
    return True


def export_history(database: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Match dbt's read-write connection. A read-only connect in the same
    # process is rejected while that connection is still open.
    connection = duckdb.connect(database.as_posix())
    try:
        tables = {row[0] for row in connection.execute("show tables").fetchall()}
        if SNAPSHOT not in tables:
            raise RuntimeError(f"{SNAPSHOT} was not created")
        connection.execute(
            f"copy (select * from {SNAPSHOT}) to '{dest.as_posix()}' (format parquet)"
        )
    finally:
        connection.close()
    print(f"wrote {dest.name}", flush=True)
