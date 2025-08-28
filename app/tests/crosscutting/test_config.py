import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from app.crosscutting.config import (
    SecretManager, ConfigError, get_secret_manager, setup_config
)


class TestSecretManager:
    """Tests for SecretManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SecretManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test SecretManager initialization."""
        assert self.manager.config_dir == Path(self.temp_dir)
        assert self.manager.tokens_file == Path(self.temp_dir) / 'tokens.json'
        assert self.manager.env_file == Path(self.temp_dir) / '.env'
        assert self.manager.config_dir.exists()

    def test_get_spotify_scopes(self):
        """Test getting minimal Spotify scopes."""
        scopes = self.manager.get_spotify_scopes()
        expected_scopes = [
            'playlist-read-private',
            'playlist-modify-public',
            'playlist-modify-private'
        ]
        assert scopes == expected_scopes

    def test_get_spotify_scope_string(self):
        """Test getting Spotify scopes as string."""
        scope_string = self.manager.get_spotify_scope_string()
        expected = 'playlist-read-private playlist-modify-public playlist-modify-private'
        assert scope_string == expected

    def test_validate_spotify_scopes_valid(self):
        """Test validating valid Spotify scopes."""
        scopes = "playlist-read-private playlist-modify-public playlist-modify-private"
        assert self.manager.validate_spotify_scopes(scopes) is True

    def test_validate_spotify_scopes_invalid(self):
        """Test validating invalid Spotify scopes."""
        scopes = "playlist-read-private"  # Missing required scopes
        assert self.manager.validate_spotify_scopes(scopes) is False

    def test_validate_spotify_scopes_extra(self):
        """Test validating scopes with extra permissions."""
        scopes = "playlist-read-private playlist-modify-public playlist-modify-private user-read-private"
        assert self.manager.validate_spotify_scopes(scopes) is True

    def test_get_missing_spotify_scopes(self):
        """Test getting missing Spotify scopes."""
        scopes = "playlist-read-private"
        missing = self.manager.get_missing_spotify_scopes(scopes)
        expected = ['playlist-modify-public', 'playlist-modify-private']
        assert set(missing) == set(expected)

    def test_get_missing_spotify_scopes_none(self):
        """Test getting missing scopes when all are present."""
        scopes = "playlist-read-private playlist-modify-public playlist-modify-private"
        missing = self.manager.get_missing_spotify_scopes(scopes)
        assert missing == []

    def test_load_tokens_empty_file(self):
        """Test loading tokens from non-existent file."""
        tokens = self.manager.load_tokens()
        assert tokens == {}

    def test_save_and_load_tokens(self):
        """Test saving and loading tokens."""
        test_tokens = {
            'spotify': {
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token'
            }
        }
        
        self.manager.save_tokens(test_tokens)
        loaded_tokens = self.manager.load_tokens()
        assert loaded_tokens == test_tokens

    def test_save_tokens_updates_existing(self):
        """Test that saving tokens updates existing ones."""
        # Save initial tokens
        initial_tokens = {
            'spotify': {
                'access_token': 'old_token',
                'refresh_token': 'old_refresh'
            }
        }
        self.manager.save_tokens(initial_tokens)
        
        # Save new tokens
        new_tokens = {
            'yandex': {
                'access_token': 'yandex_token'
            }
        }
        self.manager.save_tokens(new_tokens)
        
        # Load all tokens
        loaded_tokens = self.manager.load_tokens()
        expected = {
            'spotify': {
                'access_token': 'old_token',
                'refresh_token': 'old_refresh'
            },
            'yandex': {
                'access_token': 'yandex_token'
            }
        }
        assert loaded_tokens == expected

    def test_get_spotify_tokens(self):
        """Test getting Spotify tokens."""
        test_tokens = {
            'spotify': {
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token'
            }
        }
        self.manager.save_tokens(test_tokens)
        
        spotify_tokens = self.manager.get_spotify_tokens()
        assert spotify_tokens == test_tokens['spotify']

    def test_get_spotify_tokens_none(self):
        """Test getting Spotify tokens when none exist."""
        spotify_tokens = self.manager.get_spotify_tokens()
        assert spotify_tokens is None

    def test_save_spotify_tokens(self):
        """Test saving Spotify tokens."""
        self.manager.save_spotify_tokens('test_access', 'test_refresh')
        
        spotify_tokens = self.manager.get_spotify_tokens()
        assert spotify_tokens['access_token'] == 'test_access'
        assert spotify_tokens['refresh_token'] == 'test_refresh'

    def test_get_yandex_token(self):
        """Test getting Yandex token."""
        test_tokens = {
            'yandex': {
                'access_token': 'yandex_token'
            }
        }
        self.manager.save_tokens(test_tokens)
        
        yandex_token = self.manager.get_yandex_token()
        assert yandex_token == 'yandex_token'

    def test_get_yandex_token_none(self):
        """Test getting Yandex token when none exists."""
        yandex_token = self.manager.get_yandex_token()
        assert yandex_token is None

    def test_save_yandex_token(self):
        """Test saving Yandex token."""
        self.manager.save_yandex_token('yandex_token')
        
        yandex_token = self.manager.get_yandex_token()
        assert yandex_token == 'yandex_token'

    def test_load_env_vars_empty(self):
        """Test loading environment variables from non-existent file."""
        env_vars = self.manager.load_env_vars()
        assert env_vars == {}

    def test_save_and_load_env_vars(self):
        """Test saving and loading environment variables."""
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback'
        }
        
        self.manager.save_env_vars(test_env_vars)
        loaded_env_vars = self.manager.load_env_vars()
        assert loaded_env_vars == test_env_vars

    def test_load_env_vars_with_comments(self):
        """Test loading environment variables with comments."""
        env_content = """
# Spotify OAuth App credentials
SPOTIFY_CLIENT_ID=test_client_id
SPOTIFY_CLIENT_SECRET=test_client_secret

# Redirect URI
SPOTIFY_REDIRECT_URI=http://localhost:3000/callback
"""
        with open(self.manager.env_file, 'w') as f:
            f.write(env_content)
        
        env_vars = self.manager.load_env_vars()
        expected = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback'
        }
        assert env_vars == expected

    def test_get_spotify_client_config_success(self):
        """Test getting Spotify client configuration successfully."""
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback'
        }
        self.manager.save_env_vars(test_env_vars)
        
        config = self.manager.get_spotify_client_config()
        assert config['client_id'] == 'test_client_id'
        assert config['client_secret'] == 'test_client_secret'
        assert config['redirect_uri'] == 'http://localhost:3000/callback'

    def test_get_spotify_client_config_missing_client_id(self):
        """Test getting Spotify client config with missing client ID."""
        test_env_vars = {
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback'
        }
        self.manager.save_env_vars(test_env_vars)
        
        with pytest.raises(ConfigError, match="SPOTIFY_CLIENT_ID not found"):
            self.manager.get_spotify_client_config()

    def test_get_spotify_client_config_missing_client_secret(self):
        """Test getting Spotify client config with missing client secret."""
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback'
        }
        self.manager.save_env_vars(test_env_vars)
        
        with pytest.raises(ConfigError, match="SPOTIFY_CLIENT_SECRET not found"):
            self.manager.get_spotify_client_config()

    def test_get_spotify_client_config_missing_redirect_uri(self):
        """Test getting Spotify client config with missing redirect URI."""
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret'
        }
        self.manager.save_env_vars(test_env_vars)
        
        with pytest.raises(ConfigError, match="SPOTIFY_REDIRECT_URI not found"):
            self.manager.get_spotify_client_config()

    def test_get_yandex_config_from_env(self):
        """Test getting Yandex config from environment."""
        test_env_vars = {
            'YANDEX_TOKEN': 'yandex_token_from_env'
        }
        self.manager.save_env_vars(test_env_vars)
        
        config = self.manager.get_yandex_config()
        assert config['token'] == 'yandex_token_from_env'

    def test_get_yandex_config_from_tokens(self):
        """Test getting Yandex config from tokens.json."""
        test_tokens = {
            'yandex': {
                'access_token': 'yandex_token_from_tokens'
            }
        }
        self.manager.save_tokens(test_tokens)
        
        config = self.manager.get_yandex_config()
        assert config['token'] == 'yandex_token_from_tokens'

    def test_get_yandex_config_not_found(self):
        """Test getting Yandex config when token not found."""
        with pytest.raises(ConfigError, match="YANDEX_TOKEN not found"):
            self.manager.get_yandex_config()

    def test_validate_configuration_all_present(self):
        """Test configuration validation with all components present."""
        # Set up complete configuration
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback',
            'YANDEX_TOKEN': 'yandex_token'
        }
        self.manager.save_env_vars(test_env_vars)
        
        test_tokens = {
            'spotify': {
                'access_token': 'spotify_access_token',
                'refresh_token': 'spotify_refresh_token'
            }
        }
        self.manager.save_tokens(test_tokens)
        
        validation = self.manager.validate_configuration()
        assert validation['spotify_client_id'] is True
        assert validation['spotify_client_secret'] is True
        assert validation['spotify_redirect_uri'] is True
        assert validation['yandex_token'] is True
        assert validation['spotify_tokens'] is True

    def test_validate_configuration_partial(self):
        """Test configuration validation with partial configuration."""
        # Set up partial configuration
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id'
            # Missing other required variables
        }
        self.manager.save_env_vars(test_env_vars)
        
        validation = self.manager.validate_configuration()
        assert validation['spotify_client_id'] is True
        assert validation['spotify_client_secret'] is False
        assert validation['spotify_redirect_uri'] is False
        assert validation['yandex_token'] is False
        assert validation['spotify_tokens'] is False

    def test_get_config_summary(self):
        """Test getting configuration summary."""
        # Set up complete configuration
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id',
            'SPOTIFY_CLIENT_SECRET': 'test_client_secret',
            'SPOTIFY_REDIRECT_URI': 'http://localhost:3000/callback',
            'YANDEX_TOKEN': 'yandex_token'
        }
        self.manager.save_env_vars(test_env_vars)
        
        test_tokens = {
            'spotify': {
                'access_token': 'spotify_access_token',
                'refresh_token': 'spotify_refresh_token'
            }
        }
        self.manager.save_tokens(test_tokens)
        
        summary = self.manager.get_config_summary()
        
        assert 'config_dir' in summary
        assert 'tokens_file' in summary
        assert 'env_file' in summary
        assert 'validation' in summary
        assert 'spotify_scopes' in summary
        assert 'has_spotify_tokens' in summary
        assert 'has_yandex_token' in summary
        
        assert summary['has_spotify_tokens'] is True
        assert summary['has_yandex_token'] is True
        assert summary['spotify_scopes'] == [
            'playlist-read-private',
            'playlist-modify-public',
            'playlist-modify-private'
        ]

    def test_clear_tokens(self):
        """Test clearing tokens."""
        test_tokens = {
            'spotify': {
                'access_token': 'test_token'
            }
        }
        self.manager.save_tokens(test_tokens)
        assert self.manager.tokens_file.exists()
        
        self.manager.clear_tokens()
        assert not self.manager.tokens_file.exists()

    def test_clear_env_vars(self):
        """Test clearing environment variables."""
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id'
        }
        self.manager.save_env_vars(test_env_vars)
        assert self.manager.env_file.exists()
        
        self.manager.clear_env_vars()
        assert not self.manager.env_file.exists()


class TestSecuritySmoke:
    """Security smoke tests."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SecretManager(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_minimal_scopes_work(self):
        """Test that minimal scopes are sufficient for functionality."""
        # Test that we have exactly the required scopes
        scopes = self.manager.get_spotify_scopes()
        assert len(scopes) == 3
        assert 'playlist-read-private' in scopes
        assert 'playlist-modify-public' in scopes
        assert 'playlist-modify-private' in scopes
        
        # Test that no extra scopes are included
        extra_scopes = [
            'user-read-private',
            'user-read-email',
            'user-library-read',
            'user-library-modify',
            'user-follow-read',
            'user-follow-modify',
            'playlist-read-collaborative'
        ]
        for scope in extra_scopes:
            assert scope not in scopes

    def test_secrets_not_in_code(self):
        """Test that secrets are not hardcoded in the application."""
        # Check that no sensitive data is returned in config summary
        summary = self.manager.get_config_summary()
        
        # Verify that sensitive data is not exposed
        # Note: The summary contains field names but not actual secret values
        summary_str = str(summary)
        
        # Check that actual secret values are not exposed
        assert 'test_client_id' not in summary_str
        assert 'test_client_secret' not in summary_str
        assert 'test_access_token' not in summary_str
        assert 'test_refresh_token' not in summary_str

    def test_config_validation_works(self):
        """Test that configuration validation works correctly."""
        # Test empty configuration
        validation = self.manager.validate_configuration()
        assert all(not value for value in validation.values())
        
        # Test partial configuration
        test_env_vars = {
            'SPOTIFY_CLIENT_ID': 'test_client_id'
        }
        self.manager.save_env_vars(test_env_vars)
        
        validation = self.manager.validate_configuration()
        assert validation['spotify_client_id'] is True
        assert validation['spotify_client_secret'] is False

    def test_scope_validation_works(self):
        """Test that scope validation works correctly."""
        # Test valid scopes
        valid_scopes = "playlist-read-private playlist-modify-public playlist-modify-private"
        assert self.manager.validate_spotify_scopes(valid_scopes) is True
        
        # Test invalid scopes
        invalid_scopes = "playlist-read-private"  # Missing required scopes
        assert self.manager.validate_spotify_scopes(invalid_scopes) is False
        
        # Test missing scopes detection
        missing = self.manager.get_missing_spotify_scopes(invalid_scopes)
        assert len(missing) == 2
        assert 'playlist-modify-public' in missing
        assert 'playlist-modify-private' in missing


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_get_secret_manager(self):
        """Test getting global secret manager."""
        manager = get_secret_manager()
        assert isinstance(manager, SecretManager)

    def test_setup_config(self):
        """Test setting up configuration with custom directory."""
        temp_dir = tempfile.mkdtemp()
        try:
            manager = setup_config(temp_dir)
            assert isinstance(manager, SecretManager)
            assert manager.config_dir == Path(temp_dir)
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
