from ingest import refresh
from ingest.registry import SPECS
from ingest.sources import RemoteFile


def _remote(spec) -> RemoteFile:
    return RemoteFile(key=spec.key, url=f"https://example.invalid/{spec.key}", sha256="same")


def _previous() -> dict:
    return {
        "sources": [
            {"key": spec.key, "url": f"https://example.invalid/{spec.key}", "sha256": "same"}
            for spec in SPECS
        ]
    }


def _patch(monkeypatch, landed_hash: str) -> None:
    monkeypatch.setattr(refresh, "discover_spec", lambda session, spec: _remote(spec))
    monkeypatch.setattr(refresh, "identity_unchanged", lambda current, previous: previous is not None)
    monkeypatch.setattr(refresh, "measure_source", lambda raw, spec: 1)
    monkeypatch.setattr(
        refresh,
        "land_spec",
        lambda session, spec, refresh: RemoteFile(key=spec.key, url="", sha256=landed_hash),
    )


def test_unchanged_sources_skip_the_rebuild(monkeypatch):
    _patch(monkeypatch, "same")
    assert refresh._unchanged(None, _previous(), force=False)


def test_a_changed_source_rebuilds(monkeypatch):
    _patch(monkeypatch, "different")
    prelanded = {}
    assert not refresh._unchanged(None, _previous(), force=False, prelanded=prelanded)
    assert prelanded
    assert not refresh._unchanged(None, _previous(), force=True)


def test_can_skip_requires_normal_status_and_matching_code_fingerprint():
    from ingest.contract import SCHEMA_VERSION, contract_sha256

    good = {
        "schema_version": SCHEMA_VERSION,
        "contract_sha256": contract_sha256(),
        "code_fingerprint": refresh.code_fingerprint(),
        "build_status": "normal",
    }
    assert refresh._can_skip_for_previous(good)
    assert not refresh._can_skip_for_previous({**good, "build_status": "degraded"})
    assert not refresh._can_skip_for_previous({**good, "code_fingerprint": "old-hash"})
    assert not refresh._can_skip_for_previous({**good, "code_fingerprint": None})


def test_write_cache_excludes_missing_placeholders(tmp_path, monkeypatch):
    import zipfile

    raw = tmp_path / "raw"
    monkeypatch.setattr(refresh, "RAW", raw)
    present = raw / "ods" / "etr.csv"
    present.parent.mkdir(parents=True)
    present.write_text("row\n", encoding="utf-8")
    placeholder = raw / "phs" / "hospitals.csv"
    placeholder.parent.mkdir(parents=True)
    placeholder.write_text("hospital_code,name\n", encoding="utf-8")

    dest = tmp_path / "source-cache.zip"
    refresh._write_cache(dest, included_keys={"ods/etr.csv"})
    with zipfile.ZipFile(dest) as archive:
        names = set(archive.namelist())
    assert "ods/etr.csv" in names
    assert "phs/hospitals.csv" not in names


def test_resolve_previous_falls_back_to_latest_immutable_release(tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(refresh, "PREVIOUS", tmp_path / "previous")
    monkeypatch.setattr(
        refresh,
        "_latest_immutable_tag",
        lambda session: "data-20261116T123638Z-c15bffe",
    )

    def _fake_download(session, name, dest, tag=None):
        if tag == "data-latest":
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"build_id": "20261116T123638Z-c15bffe"}), encoding="utf-8")
        return True

    monkeypatch.setattr(refresh, "_download_asset", _fake_download)
    manifest, tag = refresh.resolve_previous(None)
    assert tag == "data-20261116T123638Z-c15bffe"
    assert manifest["build_id"] == "20261116T123638Z-c15bffe"

