import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.interfaces.http import HTTPServer, create_app


class TestHTTPServer:
    """Tests for HTTP server functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.tokens_file = os.path.join(self.temp_dir, 'test_tokens.json')
        
        # Reset environment for each test
        self.original_env = os.environ.copy()
        
        # Create server with test configuration
        self.server = HTTPServer(
            host='localhost',
            port=3001,  # Different port for testing
            debug=False
        )
        self.server.tokens_file = self.tokens_file
        self.app = self.server.app
        self.client = self.app.test_client()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        if os.path.exists(self.tokens_file):
            os.remove(self.tokens_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['status'] == 'healthy'
        assert data['version'] == '0.1.0'
        assert 'timestamp' in data
        assert 'commit' in data

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get('/')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['service'] == 'MuSync HTTP Interface'
        assert data['version'] == '0.1.0'
        assert 'endpoints' in data
        assert 'health' in data['endpoints']
        assert 'spotify_auth' in data['endpoints']
        assert 'oauth_callback' in data['endpoints']

    def test_spotify_auth_endpoint_success(self):
        """Test Spotify auth endpoint with valid configuration."""
        # Set environment variables directly
        os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id'
        
        # Recreate server to pick up new environment variables
        self.server = HTTPServer(host='localhost', port=3001, debug=False)
        self.server.tokens_file = self.tokens_file
        self.app = self.server.app
        self.client = self.app.test_client()
        
        response = self.client.get('/auth/spotify')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'auth_url' in data
        assert 'redirect_uri' in data
        assert 'test_client_id' in data['auth_url']
        assert 'accounts.spotify.com/authorize' in data['auth_url']

    def test_spotify_auth_endpoint_no_client_id(self):
        """Test Spotify auth endpoint without client ID."""
        # Clear environment variables
        if 'SPOTIFY_CLIENT_ID' in os.environ:
            del os.environ['SPOTIFY_CLIENT_ID']
        
        response = self.client.get('/auth/spotify')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert 'error' in data
        assert 'not configured' in data['error']

    def test_oauth_callback_missing_code(self):
        """Test OAuth callback without authorization code."""
        response = self.client.get('/callback')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert 'error' in data
        assert 'Missing authorization code' in data['error']

    def test_oauth_callback_with_error(self):
        """Test OAuth callback with OAuth error."""
        response = self.client.get('/callback?error=access_denied')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert 'error' in data
        assert 'OAuth authorization failed' in data['error']
        assert data['details'] == 'access_denied'

    @patch('app.interfaces.http.requests.post')
    def test_oauth_callback_success(self, mock_post):
        """Test successful OAuth callback."""
        # Set environment variables
        os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id'
        os.environ['SPOTIFY_CLIENT_SECRET'] = 'test_client_secret'
        
        # Recreate server to pick up new environment variables
        self.server = HTTPServer(host='localhost', port=3001, debug=False)
        self.server.tokens_file = self.tokens_file
        self.app = self.server.app
        self.client = self.app.test_client()
        
        # Mock successful token exchange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'playlist-read-private playlist-modify-public'
        }
        mock_post.return_value = mock_response
        
        response = self.client.get('/callback?code=test_auth_code')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['status'] == 'success'
        assert 'OAuth tokens saved successfully' in data['message']
        
        # Verify tokens were saved
        assert os.path.exists(self.tokens_file)
        with open(self.tokens_file, 'r') as f:
            tokens_data = json.load(f)
        
        assert 'spotify' in tokens_data
        assert tokens_data['spotify']['access_token'] == 'test_access_token'
        assert tokens_data['spotify']['refresh_token'] == 'test_refresh_token'

    @patch('app.interfaces.http.requests.post')
    def test_oauth_callback_token_exchange_failure(self, mock_post):
        """Test OAuth callback with token exchange failure."""
        # Set environment variables
        os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id'
        os.environ['SPOTIFY_CLIENT_SECRET'] = 'test_client_secret'
        
        # Mock failed token exchange
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid authorization code'
        mock_post.return_value = mock_response
        
        response = self.client.get('/callback?code=invalid_code')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert 'error' in data
        assert 'Failed to exchange code for tokens' in data['error']

    def test_oauth_callback_no_credentials(self):
        """Test OAuth callback without client credentials."""
        # Clear environment variables
        if 'SPOTIFY_CLIENT_ID' in os.environ:
            del os.environ['SPOTIFY_CLIENT_ID']
        if 'SPOTIFY_CLIENT_SECRET' in os.environ:
            del os.environ['SPOTIFY_CLIENT_SECRET']
        
        response = self.client.get('/callback?code=test_code')
        
        assert response.status_code == 500
        data = json.loads(response.data)
        
        assert 'error' in data
        assert 'Failed to exchange code for tokens' in data['error']

    def test_save_tokens_new_file(self):
        """Test saving tokens to new file."""
        tokens = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'test_scope',
            'expires_at': datetime.now().timestamp() + 3600
        }
        
        self.server._save_tokens(tokens)
        
        assert os.path.exists(self.tokens_file)
        with open(self.tokens_file, 'r') as f:
            data = json.load(f)
        
        assert 'spotify' in data
        assert data['spotify']['access_token'] == 'new_access_token'
        assert data['spotify']['refresh_token'] == 'new_refresh_token'
        assert 'updated_at' in data['spotify']

    def test_save_tokens_existing_file(self):
        """Test saving tokens to existing file."""
        # Create existing tokens file
        existing_tokens = {
            'yandex': {
                'access_token': 'yandex_token'
            }
        }
        with open(self.tokens_file, 'w') as f:
            json.dump(existing_tokens, f)
        
        # Save new Spotify tokens
        tokens = {
            'access_token': 'spotify_access_token',
            'refresh_token': 'spotify_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'test_scope',
            'expires_at': datetime.now().timestamp() + 3600
        }
        
        self.server._save_tokens(tokens)
        
        # Verify both tokens are preserved
        with open(self.tokens_file, 'r') as f:
            data = json.load(f)
        
        assert 'yandex' in data
        assert 'spotify' in data
        assert data['yandex']['access_token'] == 'yandex_token'
        assert data['spotify']['access_token'] == 'spotify_access_token'

    @patch('app.interfaces.http.requests.post')
    def test_exchange_code_for_tokens_success(self, mock_post):
        """Test successful code exchange for tokens."""
        # Set environment variables
        os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id'
        os.environ['SPOTIFY_CLIENT_SECRET'] = 'test_client_secret'
        
        # Recreate server to pick up new environment variables
        self.server = HTTPServer(host='localhost', port=3001, debug=False)
        self.server.tokens_file = self.tokens_file
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'token_type': 'Bearer',
            'scope': 'test_scope'
        }
        mock_post.return_value = mock_response
        
        tokens = self.server._exchange_code_for_tokens('test_code')
        
        assert tokens is not None
        assert tokens['access_token'] == 'test_access_token'
        assert tokens['refresh_token'] == 'test_refresh_token'
        assert tokens['expires_in'] == 3600
        assert tokens['token_type'] == 'Bearer'
        assert 'expires_at' in tokens

    def test_exchange_code_for_tokens_no_credentials(self):
        """Test code exchange without credentials."""
        # Clear environment variables
        if 'SPOTIFY_CLIENT_ID' in os.environ:
            del os.environ['SPOTIFY_CLIENT_ID']
        if 'SPOTIFY_CLIENT_SECRET' in os.environ:
            del os.environ['SPOTIFY_CLIENT_SECRET']
        
        tokens = self.server._exchange_code_for_tokens('test_code')
        
        assert tokens is None

    @patch('app.interfaces.http.requests.post')
    def test_exchange_code_for_tokens_failure(self, mock_post):
        """Test code exchange with API failure."""
        # Set environment variables
        os.environ['SPOTIFY_CLIENT_ID'] = 'test_client_id'
        os.environ['SPOTIFY_CLIENT_SECRET'] = 'test_client_secret'
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid code'
        mock_post.return_value = mock_response
        
        tokens = self.server._exchange_code_for_tokens('invalid_code')
        
        assert tokens is None

    def test_create_app(self):
        """Test create_app function."""
        app = create_app()
        
        assert app is not None
        assert hasattr(app, 'route')
        
        # Test that the app has our routes
        with app.test_client() as client:
            response = client.get('/health')
            assert response.status_code == 200
