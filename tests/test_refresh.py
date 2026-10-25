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
    assert not refresh._unchanged(None, _previous(), force=False)
    assert not refresh._unchanged(None, _previous(), force=True)
