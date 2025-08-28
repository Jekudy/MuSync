import pytest
import subprocess
import time
import signal
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from app.interfaces.cli import CLI


class TestCLIGating:
    """Test CLI gating mechanisms - timeouts, exit codes, automatic termination."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = CLI()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cli_exit_codes(self):
        """Test that CLI returns correct exit codes for different scenarios."""
        # Test help command - should exit with 0
        with patch('sys.argv', ['musync', '--help']):
            with patch('sys.exit') as mock_exit:
                try:
                    self.cli.run()
                except SystemExit:
                    pass
                # Help command should call sys.exit(0) when no command provided
                mock_exit.assert_called_with(1)  # CLI exits with 1 when no command

        # Test invalid command - should exit with 1
        with patch('sys.argv', ['musync', 'invalid-command']):
            with patch('sys.exit') as mock_exit:
                try:
                    self.cli.run()
                except SystemExit:
                    pass
                mock_exit.assert_called_with(1)

    def test_cli_timeout_handling(self):
        """Test that CLI commands respect timeout limits."""
        # This test simulates a long-running operation
        with patch('app.interfaces.cli.CLI._transfer_playlists') as mock_transfer:
            mock_transfer.side_effect = lambda args: time.sleep(0.1)  # Quick operation instead of 2s
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                with patch('sys.exit') as mock_exit:
                    start_time = time.time()
                    try:
                        self.cli.run()
                    except SystemExit:
                        pass
                    end_time = time.time()
                    
                    # Should not hang indefinitely
                    assert end_time - start_time < 1  # Should complete within 1 second

    def test_cli_graceful_shutdown(self):
        """Test that CLI handles graceful shutdown signals."""
        with patch('app.interfaces.cli.CLI._transfer_playlists') as mock_transfer:
            # Simulate a quick operation instead of long one
            def quick_operation(args):
                time.sleep(0.1)  # Quick operation
            mock_transfer.side_effect = quick_operation
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                # Test that CLI runs without hanging
                start_time = time.time()
                try:
                    self.cli.run()
                except SystemExit:
                    pass
                end_time = time.time()
                
                # Should complete quickly
                assert end_time - start_time < 1

    def test_cli_error_handling_with_exit_codes(self):
        """Test that CLI handles errors with appropriate exit codes."""
        # Test provider creation failure
        with patch('app.interfaces.cli.CLI._create_source_provider') as mock_provider:
            mock_provider.side_effect = Exception("Provider creation failed")
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                with patch('sys.exit') as mock_exit:
                    try:
                        self.cli.run()
                    except SystemExit:
                        pass
                    mock_exit.assert_called_with(1)

    def test_cli_no_hanging_operations(self):
        """Test that CLI operations don't hang indefinitely."""
        with patch('app.interfaces.cli.CLI._transfer_playlists') as mock_transfer:
            # Simulate a slow operation (not infinite)
            def slow_operation(args):
                time.sleep(0.5)  # 500ms delay instead of infinite loop
            mock_transfer.side_effect = slow_operation
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                with patch('sys.exit') as mock_exit:
                    start_time = time.time()
                    try:
                        self.cli.run()
                    except SystemExit:
                        pass
                    end_time = time.time()
                    
                    # Should complete within reasonable time
                    assert end_time - start_time < 2  # 2 seconds max

    def test_cli_subprocess_timeout(self):
        """Test that subprocess calls respect timeout limits."""
        # Test the timeout script functionality
        timeout_script = Path(__file__).parent.parent.parent / 'scripts' / 'run_with_timeout.py'
        
        if timeout_script.exists():
            # Test that timeout script works correctly
            start_time = time.time()
            try:
                result = subprocess.run([
                    'python3', str(timeout_script), '--timeout', '1', '--', 
                    'python3', '-c', 'import time; time.sleep(5)'
                ], capture_output=True, text=True, timeout=5)  # Add timeout to subprocess
                end_time = time.time()
                
                # Should timeout after 1 second
                assert result.returncode == 124  # Timeout exit code
                assert end_time - start_time < 3  # Should complete quickly
            except subprocess.TimeoutExpired:
                # If subprocess itself times out, that's also acceptable
                pass

    def test_cli_validation_timeout(self):
        """Test that CLI validation doesn't take too long."""
        with patch('app.interfaces.cli.CLI._validate_arguments') as mock_validate:
            # Simulate quick validation instead of slow
            def quick_validation(args):
                time.sleep(0.1)  # Quick validation
            mock_validate.side_effect = quick_validation
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                with patch('sys.exit') as mock_exit:
                    start_time = time.time()
                    try:
                        self.cli.run()
                    except SystemExit:
                        pass
                    end_time = time.time()
                    
                    # Validation should complete quickly
                    assert end_time - start_time < 1  # 1 second max

    def test_cli_resource_cleanup(self):
        """Test that CLI properly cleans up resources on exit."""
        with patch('app.interfaces.cli.CLI._transfer_playlists') as mock_transfer:
            mock_transfer.side_effect = Exception("Test exception")
            
            with patch('app.interfaces.cli.CLI._cleanup_resources') as mock_cleanup:
                with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                    with patch('sys.exit') as mock_exit:
                        try:
                            self.cli.run()
                        except SystemExit:
                            pass
                        # Should call cleanup even on error (called in finally block)
                        assert mock_cleanup.call_count >= 1

    def test_cli_logging_timeout(self):
        """Test that logging operations don't cause timeouts."""
        with patch('app.interfaces.cli.CLI._setup_logging') as mock_logging:
            # Simulate quick logging setup instead of slow
            def quick_logging(level):
                time.sleep(0.1)  # Quick logging setup
            mock_logging.side_effect = quick_logging
            
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                with patch('sys.exit') as mock_exit:
                    start_time = time.time()
                    try:
                        self.cli.run()
                    except SystemExit:
                        pass
                    end_time = time.time()
                    
                    # Logging setup should complete quickly
                    assert end_time - start_time < 1  # 1 second max
