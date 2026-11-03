import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb
import pytest

from ingest.bundle import publish_bundle, verify_zip
from ingest.contract import BUNDLE_ZIP, SCHEMA_VERSION
from ingest.validate import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "build_id": "20260101T000000Z-test",
        "built_at": "2026-01-01T00:00:00+00:00",
        "commit": "test",
        "repository": "example/locations",
        "data_scope": "current",
        "build_status": "fixture",
        "sources": [],
        "row_counts": {},
        "validation": {"conflicts": 0},
    }


def _publish(fixture_mart: Path, tmp_path: Path, monkeypatch, previous: Path | None = None) -> Path:
    mart = tmp_path / "mart"
    shutil.copytree(fixture_mart, mart)
    monkeypatch.setattr("ingest.bundle.STAGING", tmp_path / "staging")
    monkeypatch.setattr("ingest.bundle.BUILD", tmp_path / "build")
    publish_bundle(mart, _manifest(), previous)
    return mart


def test_bundle_round_trip_and_shared_alias(fixture_mart, tmp_path, monkeypatch):
    mart = _publish(fixture_mart, tmp_path, monkeypatch)
    archive = mart / BUNDLE_ZIP
    verify_zip(archive, mart)
    connection = duckdb.connect()
    tricky = connection.execute(
        f"""
        select count(*) from read_csv(
            '{(tmp_path / "staging" / "location.csv").as_posix()}',
            header = true,
            all_varchar = true
        )
        where name = 'Example Shared Name'
        """
    ).fetchone()[0]
    connection.close()
    assert tricky == 2
    connection = duckdb.connect()
    aliases = connection.execute(
        f"""
        select count(distinct entity_id)
        from read_csv(
            '{(tmp_path / "staging" / "entity_alias.csv").as_posix()}',
            header = true,
            all_varchar = true
        )
        where alias_text = 'Example Shared Name' and is_preferred = 'true'
        """
    ).fetchone()[0]
    connection.close()
    assert aliases == 2
    manifest = json.loads((tmp_path / "staging" / "manifest.json").read_text(encoding="utf-8"))
    filenames = [item["filename"] for item in manifest["outputs"]]
    assert filenames.count("location.csv") == 1
    assert all(not name.endswith(".parquet") for name in filenames)
    location = next(item for item in manifest["outputs"] if item["filename"] == "location.csv")
    assert location["columns"][0] == {"name": "location_id", "type": "text", "nullable": False}
    assert manifest["row_counts"]["location"] == location["rows"]
    assert manifest["parquet"]
    assert all(item["filename"].endswith(".parquet") for item in manifest["parquet"])
    assert manifest["contract_sha256"]
    assert isinstance(manifest["worktree_dirty"], bool)
    assert manifest["dictionary"] == "data_dictionary.md"


def test_csv_round_trip_keeps_punctuation(tmp_path):
    from ingest.bundle import _export_csv
    from ingest.contract import LOCATION

    parquet = tmp_path / "location.parquet"
    text = "Ward, \"North\"\nCafé O'Brien & Co"
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select
                'abc' as location_id,
                ? as name,
                null as parent_name,
                null as parent_code,
                null as address,
                null as postcode,
                null as postcode_compact,
                null as town,
                null as local_authority_name,
                null as local_authority_code,
                null as county_name,
                null as county_code,
                null as region_name,
                null as region_code,
                null as health_area_name,
                null as health_area_code,
                null as health_area_ods_code,
                null as health_area_type,
                'England' as country_name,
                null as nhs_code,
                null as regulator,
                null as regulator_id,
                'other' as service_type,
                'cqc' as source,
                null::date as valid_from,
                null::date as valid_to,
                null as nhs_code_system,
                null as regulator_id_system,
                'cqc' as location_id_basis,
                null as health_area_source,
                'WARD' as match_string
        ) to '{parquet.as_posix()}' (format parquet)
        """,
        [text],
    )
    dest = tmp_path / "location.csv"
    _export_csv(connection, LOCATION, parquet, dest)
    connection.close()
    raw = dest.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    connection = duckdb.connect()
    found = connection.execute(
        f"""
        select name from read_csv(
            '{dest.as_posix()}',
            header = true,
            all_varchar = true,
            quote = '"',
            escape = '"'
        )
        """
    ).fetchone()[0]
    connection.close()
    assert found == text


def _rewrite(archive: Path, name: str, payload: bytes, refresh_checksum: bool = False) -> None:
    with zipfile.ZipFile(archive, "r") as source:
        files = {item: source.read(item) for item in source.namelist()}
    files[name] = payload
    if refresh_checksum:
        manifest = json.loads(files["manifest.json"])
        for item in manifest.get("outputs") or []:
            if item.get("filename") == name:
                item["sha256"] = hashlib.sha256(payload).hexdigest()
                item["bytes"] = len(payload)
        files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for item, content in files.items():
            target.writestr(item, content)


def test_unsupported_schema_is_rejected(fixture_mart, tmp_path, monkeypatch):
    mart = _publish(fixture_mart, tmp_path, monkeypatch)
    archive = mart / BUNDLE_ZIP
    with zipfile.ZipFile(archive) as source:
        manifest = json.loads(source.read("manifest.json"))
    manifest["schema_version"] = "9.0.0"
    _rewrite(archive, "manifest.json", (json.dumps(manifest) + "\n").encode("utf-8"))
    with pytest.raises(ValidationError) as caught:
        verify_zip(archive, mart)
    assert "unsupported schema version 9.0.0" in str(caught.value)


def test_corrupt_checksum_is_rejected(fixture_mart, tmp_path, monkeypatch):
    mart = _publish(fixture_mart, tmp_path, monkeypatch)
    archive = mart / BUNDLE_ZIP
    with zipfile.ZipFile(archive) as source:
        payload = bytearray(source.read("location.csv"))
    payload[-2] = payload[-2] ^ 1
    _rewrite(archive, "location.csv", bytes(payload))
    with pytest.raises(ValidationError) as caught:
        verify_zip(archive)
    assert "checksum" in str(caught.value)


def test_a_bad_date_is_rejected(fixture_mart, tmp_path, monkeypatch):
    mart = _publish(fixture_mart, tmp_path, monkeypatch)
    archive = mart / BUNDLE_ZIP
    with zipfile.ZipFile(archive) as source:
        payload = source.read("location.csv")
    assert b"2015-01-01" in payload
    payload = payload.replace(b"2015-01-01", b"2015-99-99", 1)
    _rewrite(archive, "location.csv", payload, refresh_checksum=True)
    with pytest.raises(ValidationError) as caught:
        verify_zip(archive)
    assert "valid_from" in str(caught.value)


def test_dangling_membership_is_rejected(fixture_mart, tmp_path, monkeypatch):
    broken = tmp_path / "broken-mart"
    shutil.copytree(fixture_mart, broken)
    link = (broken / "entity_site.parquet").as_posix()
    dest = broken / "entity_site-next.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from read_parquet('{link}')
            union all by name
            select
                'provider:MISSING' as entity_id,
                'missing-location' as location_id,
                'provider' as membership_type,
                'cqc' as membership_source
        )         to '{dest.as_posix()}' (format parquet)
        """
    )
    connection.close()
    dest.replace(broken / "entity_site.parquet")
    monkeypatch.setattr("ingest.bundle.STAGING", tmp_path / "staging")
    monkeypatch.setattr("ingest.bundle.BUILD", tmp_path / "build")
    with pytest.raises(ValidationError) as caught:
        publish_bundle(broken, _manifest(), None)
    assert "dangling" in str(caught.value)


def test_failed_verify_keeps_the_accepted_zip(fixture_mart, tmp_path, monkeypatch):
    mart = _publish(fixture_mart, tmp_path, monkeypatch)
    accepted = (mart / BUNDLE_ZIP).read_bytes()

    def _reject(*_args, **_kwargs):
        raise ValidationError(["staged export failed"])

    monkeypatch.setattr("ingest.bundle.verify_zip", _reject)
    with pytest.raises(ValidationError):
        publish_bundle(mart, _manifest(), None)
    assert (mart / BUNDLE_ZIP).read_bytes() == accepted


def test_duplicate_location_key_is_rejected(fixture_mart, tmp_path, monkeypatch):
    broken = tmp_path / "duplicate-mart"
    shutil.copytree(fixture_mart, broken)
    location = (broken / "location.parquet").as_posix()
    dest = broken / "location-next.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from read_parquet('{location}')
            union all
            select * from (select * from read_parquet('{location}') limit 1)
        )         to '{dest.as_posix()}' (format parquet)
        """
    )
    connection.close()
    dest.replace(broken / "location.parquet")
    monkeypatch.setattr("ingest.bundle.STAGING", tmp_path / "staging-2")
    monkeypatch.setattr("ingest.bundle.BUILD", tmp_path / "build-2")
    with pytest.raises(ValidationError) as caught:
        publish_bundle(broken, _manifest(), None)
    assert "duplicate" in str(caught.value)
