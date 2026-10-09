import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Kein Test schreibt in das echte %APPDATA%."""
    monkeypatch.setenv("DESKTOP_PETS_HOME", str(tmp_path / "home"))
    yield


@pytest.fixture(autouse=True)
def _no_real_keyring(monkeypatch):
    """Kein Test liest oder schreibt den echten Anmeldeinformationsspeicher."""
    from desktop_pets.features.ai import keys

    monkeypatch.setattr(keys, "USE_KEYRING", False)
    yield
