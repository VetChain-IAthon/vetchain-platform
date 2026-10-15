"""La descarga de modelos del build: sin token no falla; con token instala solo artefactos de la raíz del tarball."""
import io
import tarfile

from scripts import fetch_forecast_models as fetch


def _tarball(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_without_token_skips_and_succeeds(monkeypatch, tmp_path):
    monkeypatch.delenv("FORECAST_MODELS_TOKEN", raising=False)
    monkeypatch.setenv("FORECAST_MODELS_DIR", str(tmp_path / "forecast"))
    assert fetch.main() == 0
    assert not (tmp_path / "forecast").exists()


def test_installs_only_root_artifacts(monkeypatch, tmp_path):
    payload = _tarball({
        "repo-abc/extratrees_A_1m.joblib": b"model",
        "repo-abc/extratrees_A_1m.json": b"{}",
        "repo-abc/README.md": b"readme",
        "repo-abc/sub/extra.joblib": b"nested",
    })

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        assert request.get_header("Authorization") == "Bearer secreto"
        return Response(payload)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("FORECAST_MODELS_TOKEN", "secreto")
    monkeypatch.setenv("FORECAST_MODELS_DIR", str(tmp_path / "forecast"))
    assert fetch.main() == 0
    assert sorted(p.name for p in (tmp_path / "forecast").iterdir()) == ["extratrees_A_1m.joblib", "extratrees_A_1m.json"]
