import os
import threading
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs

import requests

from spotify_oauth_server import SpotifyOAuthHandler, get_spotify_auth_url
from exchange_spotify_token import exchange_code_for_token, save_token_to_env


def test_get_spotify_auth_url_includes_scopes_and_redirect(monkeypatch):
    monkeypatch.setenv('SPOTIFY_CLIENT_ID', 'client-id-123')
    monkeypatch.setenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8080/callback')

    url = get_spotify_auth_url()
    assert url is not None

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert params['client_id'] == ['client-id-123']
    assert params['response_type'] == ['code']
    assert params['redirect_uri'] == ['http://127.0.0.1:8080/callback']

    scopes = params['scope'][0].split(' ')
    # Minimal required scopes for likes + playlist creation
    for s in [
        'user-read-private',
        'user-library-read',
        'user-library-modify',
        'playlist-read-private',
        'playlist-modify-private',
        'playlist-modify-public',
    ]:
        assert s in scopes


def _serve_one_request(server: HTTPServer):
    try:
        server.handle_request()
    finally:
        try:
            server.server_close()
        except Exception:
            pass


def test_callback_handler_writes_code_and_returns_200(tmp_path, monkeypatch):
    # Ensure .spotify_code is written into temp dir
    monkeypatch.chdir(tmp_path)

    server = HTTPServer(('127.0.0.1', 0), SpotifyOAuthHandler)
    port = server.server_address[1]

    t = threading.Thread(target=_serve_one_request, args=(server,))
    t.daemon = True
    t.start()

    resp = requests.get(
        f'http://127.0.0.1:{port}/callback', params={'code': 'TESTCODE123'}
    )
    assert resp.status_code == 200

    t.join(timeout=2)

    code_path = tmp_path / '.spotify_code'
    assert code_path.exists()
    assert code_path.read_text().strip() == 'TESTCODE123'


def test_callback_handler_without_code_returns_400(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    server = HTTPServer(('127.0.0.1', 0), SpotifyOAuthHandler)
    port = server.server_address[1]

    t = threading.Thread(target=_serve_one_request, args=(server,))
    t.daemon = True
    t.start()

    resp = requests.get(f'http://127.0.0.1:{port}/callback')
    assert resp.status_code == 400

    t.join(timeout=2)

    assert not (tmp_path / '.spotify_code').exists()


class _Resp:
    def __init__(self, status_code=200, json_data=None, text=''):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def test_exchange_code_for_token_success(monkeypatch):
    monkeypatch.setenv('SPOTIFY_CLIENT_ID', 'cid')
    monkeypatch.setenv('SPOTIFY_CLIENT_SECRET', 'sec')
    monkeypatch.setenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8080/callback')

    def fake_post(url, data=None, headers=None):
        assert data['grant_type'] == 'authorization_code'
        assert data['code'] == 'abc'
        return _Resp(
            200,
            json_data={
                'access_token': 'AT',
                'refresh_token': 'RT',
                'token_type': 'Bearer',
                'expires_in': 3600,
            },
        )

    monkeypatch.setattr('requests.post', fake_post)

    td = exchange_code_for_token('abc')
    assert td is not None
    assert td['access_token'] == 'AT'
    assert td['refresh_token'] == 'RT'


def test_save_token_to_env_writes_tokens(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    token_data = {
        'access_token': 'AT123',
        'refresh_token': 'RT456',
        'token_type': 'Bearer',
        'expires_in': 3600,
    }

    # Pre-existing .env with unrelated content
    (tmp_path / '.env').write_text('FOO=bar\n')
    save_token_to_env(token_data)

    content = (tmp_path / '.env').read_text()
    assert 'SPOTIFY_ACCESS_TOKEN=AT123' in content
    assert 'SPOTIFY_REFRESH_TOKEN=RT456' in content



