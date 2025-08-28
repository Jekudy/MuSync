import json
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Flask, request, jsonify, redirect, url_for
import requests

from app.infrastructure.providers.spotify import SpotifyProvider


class HTTPServer:
    """HTTP server for MuSync with health checks and OAuth callbacks."""

    def __init__(self, host: str = 'localhost', port: int = 3000, debug: bool = False):
        """Initialize HTTP server."""
        self.host = host
        self.port = port
        self.debug = debug
        self.app = Flask(__name__)
        self.logger = logging.getLogger(__name__)
        
        # Version info
        self.version = "0.1.0"
        self.commit = os.getenv('GIT_COMMIT', 'unknown')
        
        # Spotify OAuth config (read from env each request to align with tests)
        self.spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:3000/callback')
        
        # Tokens file path
        self.tokens_file = os.getenv('TOKENS_FILE', 'tokens.json')
        
        self._setup_routes()
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup logging for HTTP server."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _setup_routes(self) -> None:
        """Setup Flask routes."""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'version': self.version,
                'commit': self.commit,
                'timestamp': datetime.now().isoformat()
            }), 200

        @self.app.route('/callback', methods=['GET'])
        def oauth_callback():
            """OAuth callback endpoint for Spotify."""
            try:
                # Get authorization code from query parameters
                code = request.args.get('code')
                error = request.args.get('error')
                
                if error:
                    self.logger.error(f"OAuth error: {error}")
                    return jsonify({
                        'error': 'OAuth authorization failed',
                        'details': error
                    }), 400
                
                if not code:
                    return jsonify({
                        'error': 'Missing authorization code'
                    }), 400
                
                self.logger.info(f"Received OAuth code: {code[:10]}...")
                
                # Exchange code for tokens
                tokens = self._exchange_code_for_tokens(code)
                
                if not tokens:
                    return jsonify({
                        'error': 'Failed to exchange code for tokens'
                    }), 500
                
                # Save tokens
                self._save_tokens(tokens)
                
                self.logger.info("OAuth tokens saved successfully")
                
                return jsonify({
                    'status': 'success',
                    'message': 'OAuth tokens saved successfully',
                    'timestamp': datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                self.logger.error(f"OAuth callback error: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'details': str(e)
                }), 500

        @self.app.route('/auth/spotify', methods=['GET'])
        def spotify_auth():
            """Initiate Spotify OAuth flow."""
            try:
                spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
                if not spotify_client_id:
                    return jsonify({
                        'error': 'Spotify client ID not configured'
                    }), 500
                
                # Build authorization URL
                auth_url = (
                    'https://accounts.spotify.com/authorize'
                    f'?client_id={spotify_client_id}'
                    '&response_type=code'
                    f'&redirect_uri={self.spotify_redirect_uri}'
                    '&scope=playlist-read-private,playlist-modify-public,playlist-modify-private,user-library-read,user-library-modify'
                    '&show_dialog=true'
                )
                
                return jsonify({
                    'auth_url': auth_url,
                    'redirect_uri': self.spotify_redirect_uri
                }), 200
                
            except Exception as e:
                self.logger.error(f"Spotify auth error: {e}")
                return jsonify({
                    'error': 'Internal server error',
                    'details': str(e)
                }), 500

        @self.app.route('/', methods=['GET'])
        def root():
            """Root endpoint with basic info."""
            return jsonify({
                'service': 'MuSync HTTP Interface',
                'version': self.version,
                'endpoints': {
                    'health': '/health',
                    'spotify_auth': '/auth/spotify',
                    'oauth_callback': '/callback'
                }
            }), 200

    def _exchange_code_for_tokens(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access and refresh tokens."""
        try:
            spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
            spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            if not spotify_client_id or not spotify_client_secret:
                self.logger.error("Spotify client credentials not configured")
                return None
            
            # Exchange code for tokens
            token_url = 'https://accounts.spotify.com/api/token'
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.spotify_redirect_uri,
                'client_id': spotify_client_id,
                'client_secret': spotify_client_secret
            }
            
            response = requests.post(token_url, data=data)
            
            if response.status_code != 200:
                self.logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
            
            tokens = response.json()
            
            # Extract relevant tokens
            return {
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token'),
                'expires_in': tokens.get('expires_in'),
                'token_type': tokens.get('token_type', 'Bearer'),
                'scope': tokens.get('scope'),
                'expires_at': datetime.now().timestamp() + tokens.get('expires_in', 3600)
            }
            
        except Exception as e:
            self.logger.error(f"Token exchange error: {e}")
            return None

    def _save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save tokens to file."""
        try:
            # Load existing tokens if file exists
            existing_tokens = {}
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    existing_tokens = json.load(f)
            
            # Update Spotify tokens
            existing_tokens['spotify'] = {
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expires_in': tokens['expires_in'],
                'token_type': tokens['token_type'],
                'scope': tokens['scope'],
                'expires_at': tokens['expires_at'],
                'updated_at': datetime.now().isoformat()
            }
            
            # Save to file
            with open(self.tokens_file, 'w') as f:
                json.dump(existing_tokens, f, indent=2)
            
            self.logger.info(f"Tokens saved to {self.tokens_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save tokens: {e}")
            raise

    def run(self) -> None:
        """Run the HTTP server."""
        self.logger.info(f"Starting MuSync HTTP server on {self.host}:{self.port}")
        self.app.run(
            host=self.host,
            port=self.port,
            debug=self.debug
        )


def create_app() -> Flask:
    """Create Flask app for testing."""
    server = HTTPServer()
    return server.app


if __name__ == '__main__':
    server = HTTPServer()
    server.run()
