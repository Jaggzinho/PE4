from pathlib import Path

from backend.app.launcher import _ensure_secret
from backend.app.static_spa import default_static_dir


def test_default_static_dir_is_repository_dist():
    repository = Path(__file__).resolve().parents[1]
    assert default_static_dir() == repository / "dist"


def test_generated_runtime_secret_is_persistent_and_strong(tmp_path):
    path = tmp_path / ".secret"
    first = _ensure_secret(path)
    second = _ensure_secret(path)

    assert first == second
    assert len(first) >= 32
    assert path.read_text(encoding="utf-8").strip() == first
