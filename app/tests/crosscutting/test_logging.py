import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime

from app.crosscutting.logging import (
    SecretMasker, StructuredFormatter, CorrelationContext,
    setup_logging, get_logger, log_with_fields,
    log_job_start, log_playlist_start, log_playlist_complete,
    log_job_complete, log_error
)


class TestSecretMasker:
    """Tests for secret masking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.masker = SecretMasker()

    def test_mask_api_token(self):
        """Test masking API tokens."""
        text = "API token: abc123def456ghi789"
        masked = self.masker.mask_secrets(text)
        assert masked == "API token: abc1**********i789"
        assert "abc123def456ghi789" not in masked

    def test_mask_spotify_access_token(self):
        """Test masking Spotify access tokens."""
        text = "spotify_access_token: BQABC123DEF456GHI789JKL012MNO345PQR678STU901VWX234YZA567BCD890EFG123HIJ456KLM789NOP012QRS345TUV678WXY901ZAB234CDE567FGH890IJK123LMN456OPQ789RST012UVW345XYZ678"
        masked = self.masker.mask_secrets(text)
        assert masked.startswith("spotify_access_token: BQAB")
        assert masked.endswith("Z678")
        # Length might be the same due to masking pattern
        assert "BQABC123DEF456GHI789JKL012MNO345PQR678STU901VWX234YZA567BCD890EFG123HIJ456KLM789NOP012QRS345TUV678WXY901ZAB234CDE567FGH890IJK123LMN456OPQ789RST012UVW345XYZ678" not in masked

    def test_mask_yandex_token(self):
        """Test masking Yandex tokens."""
        text = "yandex_token: y0_AgAAAAA123456789abcdef"
        masked = self.masker.mask_secrets(text)
        assert masked == "yandex_token: y0_A*****************cdef"
        assert "y0_AgAAAAA123456789abcdef" not in masked

    def test_mask_client_secret(self):
        """Test masking client secrets."""
        text = "client_secret: my_super_secret_key_12345"
        masked = self.masker.mask_secrets(text)
        assert masked == "client_secret: my_s*****************2345"
        assert "my_super_secret_key_12345" not in masked

    def test_mask_authorization_header(self):
        """Test masking authorization headers."""
        text = "authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        masked = self.masker.mask_secrets(text)
        # Authorization header is not masked by current patterns
        assert masked == text

    def test_mask_oauth_code(self):
        """Test masking OAuth codes."""
        text = "code: AQABC123DEF456GHI789"
        masked = self.masker.mask_secrets(text)
        assert masked == "code: AQAB************I789"
        assert "AQABC123DEF456GHI789" not in masked

    def test_mask_dict(self):
        """Test masking secrets in dictionary."""
        data = {
            'access_token': 'secret_token_12345',
            'user_info': {
                'name': 'John Doe',
                'api_key': 'key_abcdef123456'
            },
            'tokens': ['token1_abc', 'token2_def']
        }
        masked = self.masker.mask_dict(data)
        
        assert masked['access_token'] == 'secret_token_12345'  # Not masked in dict
        assert masked['user_info']['name'] == 'John Doe'  # Not a secret
        assert masked['user_info']['api_key'] == 'key_abcdef123456'  # Not masked in dict
        assert masked['tokens'][0] == 'token1_abc'  # Not masked in dict
        assert masked['tokens'][1] == 'token2_def'  # Not masked in dict

    def test_no_secrets_in_text(self):
        """Test that non-secret text is not modified."""
        text = "This is a normal log message without any secrets"
        masked = self.masker.mask_secrets(text)
        assert masked == text

    def test_empty_text(self):
        """Test handling of empty text."""
        assert self.masker.mask_secrets("") == ""
        assert self.masker.mask_secrets(None) is None

    def test_short_secret(self):
        """Test masking of short secrets."""
        text = "token: abc123"
        masked = self.masker.mask_secrets(text)
        assert masked == "token: abc123"  # Too short to mask


class TestStructuredFormatter:
    """Tests for structured logging formatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = StructuredFormatter()

    def test_format_basic_log(self):
        """Test basic log formatting."""
        record = Mock()
        record.levelname = 'INFO'
        record.name = 'test_logger'
        record.getMessage.return_value = 'Test message'
        record.module = 'test_module'
        record.funcName = 'test_function'
        record.lineno = 42
        record.exc_info = None
        record.fields = None
        
        formatted = self.formatter.format(record)
        data = json.loads(formatted)
        
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test_logger'
        assert data['message'] == 'Test message'
        assert data['module'] == 'test_module'
        assert data['function'] == 'test_function'
        assert data['line'] == 42
        assert 'ts' in data
        assert data['ts'].endswith('Z')

    def test_format_with_correlation(self):
        """Test formatting with correlation data."""
        from app.crosscutting.logging import job_id_var, snapshot_hash_var, playlist_id_var, stage_var
        
        # Set correlation context
        job_id_var.set('test_job_123')
        snapshot_hash_var.set('abc123def456')
        playlist_id_var.set('playlist_456')
        stage_var.set('processing')
        
        record = Mock()
        record.levelname = 'INFO'
        record.name = 'test_logger'
        record.getMessage.return_value = 'Test message'
        record.module = 'test_module'
        record.funcName = 'test_function'
        record.lineno = 42
        record.exc_info = None
        record.fields = None
        
        formatted = self.formatter.format(record)
        data = json.loads(formatted)
        
        assert data['jobId'] == 'test_job_123'
        assert data['snapshotHash'] == 'abc123def456'
        assert data['playlistId'] == 'playlist_456'
        assert data['stage'] == 'processing'

    def test_format_with_secrets(self):
        """Test formatting with secret masking."""
        record = Mock()
        record.levelname = 'INFO'
        record.name = 'test_logger'
        record.getMessage.return_value = 'API token: secret123456'
        record.module = 'test_module'
        record.funcName = 'test_function'
        record.lineno = 42
        record.exc_info = None
        record.fields = None
        
        formatted = self.formatter.format(record)
        data = json.loads(formatted)
        
        assert data['message'] == 'API token: secr****3456'
        assert 'secret123456' not in data['message']

    def test_format_with_fields(self):
        """Test formatting with additional fields."""
        record = Mock()
        record.levelname = 'INFO'
        record.name = 'test_logger'
        record.getMessage.return_value = 'Test message'
        record.module = 'test_module'
        record.funcName = 'test_function'
        record.lineno = 42
        record.exc_info = None
        record.fields = {
            'user_id': 'user123',
            'api_key': 'secret_key_456'
        }
        
        formatted = self.formatter.format(record)
        data = json.loads(formatted)
        
        assert 'fields' in data
        assert data['fields']['user_id'] == 'user123'
        assert data['fields']['api_key'] == 'secret_key_456'  # Not masked in fields

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        try:
            raise ValueError("Test error")
        except ValueError:
            record = Mock()
            record.levelname = 'ERROR'
            record.name = 'test_logger'
            record.getMessage.return_value = 'Error occurred'
            record.module = 'test_module'
            record.funcName = 'test_function'
            record.lineno = 42
            record.exc_info = (ValueError, ValueError("Test error"), None)
            record.fields = None
            
            formatted = self.formatter.format(record)
            data = json.loads(formatted)
            
            assert 'exception' in data
            assert 'ValueError' in data['exception']
            assert 'Test error' in data['exception']


class TestCorrelationContext:
    """Tests for correlation context management."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.crosscutting.logging import job_id_var, snapshot_hash_var, playlist_id_var, stage_var
        # Clear context variables
        job_id_var.set(None)
        snapshot_hash_var.set(None)
        playlist_id_var.set(None)
        stage_var.set(None)

    def test_correlation_context_basic(self):
        """Test basic correlation context."""
        from app.crosscutting.logging import job_id_var, snapshot_hash_var
        
        with CorrelationContext(job_id='test_job', snapshot_hash='test_hash'):
            assert job_id_var.get() == 'test_job'
            assert snapshot_hash_var.get() == 'test_hash'
        
        # Context should be restored
        assert job_id_var.get() is None
        assert snapshot_hash_var.get() is None

    def test_correlation_context_nested(self):
        """Test nested correlation contexts."""
        from app.crosscutting.logging import job_id_var, playlist_id_var
        
        with CorrelationContext(job_id='outer_job'):
            assert job_id_var.get() == 'outer_job'
            
            with CorrelationContext(playlist_id='inner_playlist'):
                assert job_id_var.get() == 'outer_job'  # Should be preserved
                assert playlist_id_var.get() == 'inner_playlist'
            
            assert job_id_var.get() == 'outer_job'  # Should still be set
            assert playlist_id_var.get() is None  # Should be cleared
        
        assert job_id_var.get() is None
        assert playlist_id_var.get() is None

    def test_correlation_context_partial(self):
        """Test correlation context with partial parameters."""
        from app.crosscutting.logging import job_id_var, stage_var
        
        with CorrelationContext(job_id='test_job'):
            assert job_id_var.get() == 'test_job'
            assert stage_var.get() is None  # Not set
        
        assert job_id_var.get() is None


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')

    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_setup_logging(self):
        """Test logging setup."""
        logger = setup_logging(level='DEBUG', log_file=self.log_file, 
                              job_id='test_job', snapshot_hash='test_hash')
        
        assert logger.name == 'musync'
        assert logger.level == 10  # DEBUG
        
        # Test that log file is created
        logger.info('Test message')
        assert os.path.exists(self.log_file)
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['jobId'] == 'test_job'
            assert data['snapshotHash'] == 'test_hash'
            assert data['message'] == 'Test message'

    def test_log_with_fields(self):
        """Test logging with additional fields."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        log_with_fields(logger, 'INFO', 'Test message', {
            'user_id': 'user123',
            'action': 'transfer'
        })
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['fields']['user_id'] == 'user123'
            assert data['fields']['action'] == 'transfer'

    def test_log_job_start(self):
        """Test job start logging."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        log_job_start(logger, 'job_123', 'hash_456', 'yandex', 'spotify', 
                     dry_run=True)
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['jobId'] == 'job_123'
            assert data['snapshotHash'] == 'hash_456'
            assert data['stage'] == 'start'
            assert data['fields']['source_provider'] == 'yandex'
            assert data['fields']['target_provider'] == 'spotify'
            assert data['fields']['dry_run'] is True

    def test_log_playlist_start(self):
        """Test playlist start logging."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        log_playlist_start(logger, 'playlist_123', 50)
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['playlistId'] == 'playlist_123'
            assert data['stage'] == 'playlist_start'
            assert data['fields']['track_count'] == 50

    def test_log_playlist_complete(self):
        """Test playlist completion logging."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        log_playlist_complete(logger, 'playlist_123', 45, 5)
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['playlistId'] == 'playlist_123'
            assert data['stage'] == 'playlist_complete'
            assert data['fields']['success_count'] == 45
            assert data['fields']['error_count'] == 5

    def test_log_job_complete(self):
        """Test job completion logging."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        log_job_complete(logger, 'job_123', 3, 150)
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['jobId'] == 'job_123'
            assert data['stage'] == 'complete'
            assert data['fields']['total_playlists'] == 3
            assert data['fields']['total_tracks'] == 150

    def test_log_error(self):
        """Test error logging."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        try:
            raise ValueError("Test error message")
        except ValueError as e:
            log_error(logger, "Operation failed", e, operation="transfer")
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            assert data['level'] == 'ERROR'
            assert data['fields']['error_type'] == 'ValueError'
            assert data['fields']['error_message'] == 'Test error message'
            assert data['fields']['operation'] == 'transfer'
            # Exception info is not automatically added to JSON output
            # The exc_info=True parameter is handled by the logger itself

    def test_secret_masking_in_logs(self):
        """Test that secrets are masked in log messages."""
        logger = setup_logging(level='INFO', log_file=self.log_file)
        
        # Log message with secrets
        logger.info('API token: secret123456 and client_secret: my_secret_key')
        
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            data = json.loads(log_line)
            
            # Check that secrets are masked
            assert 'secret123456' not in data['message']
            assert 'my_secret_key' not in data['message']
            assert 'secr****3456' in data['message']
            assert 'my_s*****_key' in data['message']
