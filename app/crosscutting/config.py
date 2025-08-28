import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigError(Exception):
    """Configuration error."""
    pass


class SecretManager:
    """Manages application secrets and configuration."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize secret manager."""
        self.config_dir = Path(config_dir) if config_dir else Path.home() / '.musync'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.tokens_file = self.config_dir / 'tokens.json'
        self.env_file = self.config_dir / '.env'
    
    def get_spotify_scopes(self) -> list:
        """Get minimal required Spotify scopes."""
        return [
            'playlist-read-private',      # Read private playlists
            'playlist-modify-public',     # Create/modify public playlists
            'playlist-modify-private',    # Create/modify private playlists
        ]
    
    def get_spotify_scope_string(self) -> str:
        """Get Spotify scopes as space-separated string."""
        return ' '.join(self.get_spotify_scopes())
    
    def validate_spotify_scopes(self, scopes: str) -> bool:
        """Validate that provided scopes include all required ones."""
        provided_scopes = set(scopes.split())
        required_scopes = set(self.get_spotify_scopes())
        
        return required_scopes.issubset(provided_scopes)
    
    def get_missing_spotify_scopes(self, scopes: str) -> list:
        """Get list of missing required Spotify scopes."""
        provided_scopes = set(scopes.split())
        required_scopes = set(self.get_spotify_scopes())
        
        return list(required_scopes - provided_scopes)
    
    def load_tokens(self) -> Dict[str, Any]:
        """Load tokens from tokens.json file."""
        if not self.tokens_file.exists():
            return {}
        
        try:
            with open(self.tokens_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ConfigError(f"Failed to load tokens from {self.tokens_file}: {e}")
    
    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save tokens to tokens.json file."""
        try:
            # Load existing tokens
            existing_tokens = self.load_tokens()
            
            # Update with new tokens
            existing_tokens.update(tokens)
            
            # Save back to file
            with open(self.tokens_file, 'w') as f:
                json.dump(existing_tokens, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise ConfigError(f"Failed to save tokens to {self.tokens_file}: {e}")
    
    def get_spotify_tokens(self) -> Optional[Dict[str, str]]:
        """Get Spotify tokens from tokens.json."""
        tokens = self.load_tokens()
        return tokens.get('spotify')
    
    def save_spotify_tokens(self, access_token: str, refresh_token: str) -> None:
        """Save Spotify tokens."""
        self.save_tokens({
            'spotify': {
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        })
    
    def get_yandex_token(self) -> Optional[str]:
        """Get Yandex Music token from tokens.json."""
        tokens = self.load_tokens()
        yandex_tokens = tokens.get('yandex', {})
        return yandex_tokens.get('access_token')
    
    def save_yandex_token(self, token: str) -> None:
        """Save Yandex Music token."""
        self.save_tokens({
            'yandex': {
                'access_token': token
            }
        })
    
    def load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from .env file."""
        env_vars = {}
        
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            except IOError as e:
                raise ConfigError(f"Failed to load .env file {self.env_file}: {e}")
        
        return env_vars
    
    def save_env_vars(self, env_vars: Dict[str, str]) -> None:
        """Save environment variables to .env file."""
        try:
            with open(self.env_file, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except IOError as e:
            raise ConfigError(f"Failed to save .env file {self.env_file}: {e}")
    
    def get_spotify_client_config(self) -> Dict[str, str]:
        """Get Spotify client configuration from environment."""
        env_vars = self.load_env_vars()
        
        client_id = env_vars.get('SPOTIFY_CLIENT_ID')
        client_secret = env_vars.get('SPOTIFY_CLIENT_SECRET')
        redirect_uri = env_vars.get('SPOTIFY_REDIRECT_URI')
        
        if not client_id:
            raise ConfigError("SPOTIFY_CLIENT_ID not found in environment")
        if not client_secret:
            raise ConfigError("SPOTIFY_CLIENT_SECRET not found in environment")
        if not redirect_uri:
            raise ConfigError("SPOTIFY_REDIRECT_URI not found in environment")
        
        return {
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri
        }
    
    def get_yandex_config(self) -> Dict[str, str]:
        """Get Yandex Music configuration from environment."""
        env_vars = self.load_env_vars()
        
        token = env_vars.get('YANDEX_TOKEN')
        if not token:
            # Try to get from tokens.json as fallback
            token = self.get_yandex_token()
        
        if not token:
            raise ConfigError("YANDEX_TOKEN not found in environment or tokens.json")
        
        return {
            'token': token
        }
    
    def validate_configuration(self) -> Dict[str, bool]:
        """Validate that all required configuration is present."""
        validation = {
            'spotify_client_id': False,
            'spotify_client_secret': False,
            'spotify_redirect_uri': False,
            'yandex_token': False,
            'spotify_tokens': False,
        }
        
        # Check Spotify client config
        env_vars = self.load_env_vars()
        validation['spotify_client_id'] = bool(env_vars.get('SPOTIFY_CLIENT_ID'))
        validation['spotify_client_secret'] = bool(env_vars.get('SPOTIFY_CLIENT_SECRET'))
        validation['spotify_redirect_uri'] = bool(env_vars.get('SPOTIFY_REDIRECT_URI'))
        
        # Check Yandex config
        validation['yandex_token'] = bool(env_vars.get('YANDEX_TOKEN') or self.get_yandex_token())
        
        # Check Spotify tokens
        spotify_tokens = self.get_spotify_tokens()
        validation['spotify_tokens'] = bool(spotify_tokens and spotify_tokens.get('access_token'))
        
        return validation
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary (without sensitive data)."""
        validation = self.validate_configuration()
        
        return {
            'config_dir': str(self.config_dir),
            'tokens_file': str(self.tokens_file),
            'env_file': str(self.env_file),
            'validation': validation,
            'spotify_scopes': self.get_spotify_scopes(),
            'has_spotify_tokens': validation['spotify_tokens'],
            'has_yandex_token': validation['yandex_token'],
        }
    
    def clear_tokens(self) -> None:
        """Clear all stored tokens."""
        if self.tokens_file.exists():
            self.tokens_file.unlink()
    
    def clear_env_vars(self) -> None:
        """Clear .env file."""
        if self.env_file.exists():
            self.env_file.unlink()


# Global instance
secret_manager = SecretManager()


def get_secret_manager() -> SecretManager:
    """Get global secret manager instance."""
    return secret_manager


def setup_config(config_dir: Optional[str] = None) -> SecretManager:
    """Setup configuration with custom directory."""
    global secret_manager
    secret_manager = SecretManager(config_dir)
    return secret_manager
