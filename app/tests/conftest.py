import os
import sys
import pytest


def _ensure_project_root_on_sys_path() -> None:
    here = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(here, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_on_sys_path()


@pytest.fixture(autouse=True)
def _clear_spotify_tokens_env():
    """Ensure SPOTIFY access/refresh tokens do not leak across tests.
    Some tests may load a .env that sets these variables; clear before each test
    and restore afterwards so tests explicitly setting them remain deterministic.
    """
    keys = ['SPOTIFY_ACCESS_TOKEN', 'SPOTIFY_REFRESH_TOKEN', 'YANDEX_ACCESS_TOKEN']
    backup = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    try:
        yield
    finally:
        for k, v in backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

