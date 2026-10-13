"""Download, validate, build, and describe a publishable location refresh.

A failed check leaves the previous release in place. The workflow publishes
only when this command writes action "publish".
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from ingest.build import database_path, dbt_build
from ingest.download import RAW, apply_download, http_session, prepare_cqc, prepare_nspl
from ingest.history import export_history, restore_history
from ingest.sources import (
    CQC_ACTIVE,
    CQC_DEACTIVATED,
    NSPL_KEY,
    RemoteFile,
    discover_sources,
    identity_unchanged,
)
from ingest.validate import ValidationError, validate_marts, validate_raw, write_json

ROOT = Path(__file__).resolve().parents[1]
MART = ROOT / "data" / "mart"
BUILD = ROOT / "data" / "build"
STATUS = BUILD / "refresh-status.json"
REPORT = BUILD / "validation-report.json"
PREVIOUS = BUILD / "previous"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def repository() -> str:
    if os.environ.get("LOCATIONS_DATA_REPO"):
        return os.environ["LOCATIONS_DATA_REPO"]
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    payload = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
    return payload["repo"]


def release_tag() -> str:
    payload = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
    return payload["tag"]


def _asset_url(name: str) -> str:
    return f"https://github.com/{repository()}/releases/download/{release_tag()}/{name}"


def _download_asset(session: requests.Session, name: str, dest: Path) -> bool:
    response = session.get(_asset_url(name), timeout=(30, 600), allow_redirects=True)
    if response.status_code == 404:
        dest.unlink(missing_ok=True)
        return False
    response.raise_for_status()
    if "text/html" in response.headers.get("Content-Type", ""):
        dest.unlink(missing_ok=True)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return True


def previous_manifest(session: requests.Session) -> dict | None:
    dest = PREVIOUS / "manifest.json"
    if not _download_asset(session, "manifest.json", dest):
        print("no previous release", flush=True)
        return None
    return json.loads(dest.read_text(encoding="utf-8"))


def _previous_source(manifest: dict | None, key: str) -> dict | None:
    if not manifest:
        return None
    for item in manifest.get("sources", []):
        if item.get("key") == key:
            return item
    return None


def _source_record(item: RemoteFile) -> dict:
    return {
        "key": item.key,
        "url": item.url,
        "publisher_date": item.publisher_date,
        "edition": item.edition,
        "modified": item.modified,
        "last_modified": item.last_modified,
        "etag": item.etag,
        "sha256": item.sha256,
        "bytes": item.size,
    }


def _ods_changed(found: dict[str, RemoteFile], previous: dict | None) -> bool:
    for key, item in found.items():
        if not key.startswith("ods/"):
            continue
        old = _previous_source(previous, key)
        if old is None or old.get("sha256") != item.sha256:
            return True
    return False


def _dated_changed(found: dict[str, RemoteFile], previous: dict | None) -> bool:
    for key in (CQC_ACTIVE, CQC_DEACTIVATED, NSPL_KEY):
        if not identity_unchanged(found[key], _previous_source(previous, key)):
            return True
    return False


def _manifest(found: dict[str, RemoteFile], raw_counts: dict, row_counts: dict) -> dict:
    return {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "nspl_edition": found[NSPL_KEY].edition,
        "sources": [_source_record(item) for item in found.values()],
        "raw_counts": raw_counts,
        "row_counts": row_counts,
    }


def _finish(action: str, reason: str, report: dict) -> None:
    write_json(STATUS, {"action": action, "reason": reason})
    write_json(REPORT, report)
    print(f"{action}: {reason}", flush=True)


def run(force: bool) -> None:
    session = http_session()
    previous = previous_manifest(session)
    found = discover_sources(session)
    dated_changed = _dated_changed(found, previous)
    if previous and not dated_changed and not force:
        for key, item in found.items():
            if key.startswith("ods/"):
                apply_download(session, item, refresh=True)
        if not _ods_changed(found, previous):
            _finish(
                "skip",
                "sources unchanged",
                {"ok": True, "action": "skip", "reason": "sources unchanged"},
            )
            return
    for item in found.values():
        apply_download(session, item, refresh=True)
    prepare_cqc(refresh=True)
    prepare_nspl(refresh=True)
    try:
        raw_counts = validate_raw(RAW)
    except ValidationError as exc:
        _finish("fail", "raw checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc

    history = PREVIOUS / "location_history.parquet"
    _download_asset(session, "location_history.parquet", history)
    database = database_path(fixtures=False)
    for path in (database, Path(str(database) + ".wal")):
        path.unlink(missing_ok=True)
    restore_history(database, history)
    try:
        dbt_build(fixtures=False)
    except SystemExit as exc:
        _finish("fail", "dbt build failed", {"ok": False, "failures": [str(exc)]})
        raise
    export_history(database, MART / "location_history.parquet")
    try:
        row_counts = validate_marts(MART, previous, force)
    except ValidationError as exc:
        _finish("fail", "mart checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc
    manifest = _manifest(found, raw_counts, row_counts)
    write_json(MART / "manifest.json", manifest)
    _finish(
        "publish",
        "marts passed checks",
        {"ok": True, "action": "publish", "row_counts": row_counts, "failures": []},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh and validate location data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when sources are unchanged, and allow a large row-count change",
    )
    args = parser.parse_args()
    try:
        run(force=args.force or _enabled("FORCE_REFRESH"))
    except ValidationError as exc:
        _finish("fail", "checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc
    except SystemExit:
        raise
    except Exception as exc:
        _finish("fail", "refresh failed", {"ok": False, "failures": [str(exc)]})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
