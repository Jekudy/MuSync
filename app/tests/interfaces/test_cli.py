import pytest
import argparse
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import sys

from app.interfaces.cli import CLI


class TestCLI:
    """Tests for CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = CLI()

    def test_create_parser(self):
        """Test argument parser creation."""
        parser = self.cli._create_parser()

        assert isinstance(parser, argparse.ArgumentParser)

        # Test transfer command
        args = parser.parse_args(['transfer', '--source', 'yandex', '--target', 'spotify', '--dry-run'])
        assert args.command == 'transfer'
        assert args.source == 'yandex'
        assert args.target == 'spotify'
        assert args.dry_run is True

        # Test list command
        args = parser.parse_args(['list', '--provider', 'yandex'])
        assert args.command == 'list'
        assert args.provider == 'yandex'

    @patch.dict(os.environ, {
        'YANDEX_ACCESS_TOKEN': 'test_yandex_token',
        'SPOTIFY_ACCESS_TOKEN': 'test_spotify_access_token',
        'SPOTIFY_REFRESH_TOKEN': 'test_spotify_refresh_token'
    })
    def test_get_env_token(self):
        """Test getting tokens from environment."""
        assert self.cli._get_env_token('yandex') == 'test_yandex_token'
        assert self.cli._get_env_token('spotify') == 'test_spotify_access_token'
        assert self.cli._get_env_token('spotify', 'refresh') == 'test_spotify_refresh_token'

        # Test non-existent token
        assert self.cli._get_env_token('nonexistent') is None

    @patch.dict(os.environ, {'YANDEX_ACCESS_TOKEN': 'test_token'})
    @patch('app.interfaces.cli.YandexMusicProvider')
    def test_create_source_provider_yandex(self, mock_provider_class):
        """Test creating Yandex source provider."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        provider = self.cli._create_source_provider('yandex')

        assert provider == mock_provider
        mock_provider_class.assert_called_once_with('test_token')

    @patch.dict(os.environ, {
        'SPOTIFY_ACCESS_TOKEN': 'test_access',
        'SPOTIFY_REFRESH_TOKEN': 'test_refresh'
    })
    @patch('app.interfaces.cli.SpotifyProvider')
    def test_create_target_provider_spotify(self, mock_provider_class):
        """Test creating Spotify target provider."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        provider = self.cli._create_target_provider('spotify')

        assert provider == mock_provider
        mock_provider_class.assert_called_once_with('test_access', 'test_refresh')

    def test_create_source_provider_invalid(self):
        """Test creating invalid source provider."""
        with pytest.raises(ValueError, match="Unsupported source provider"):
            self.cli._create_source_provider('invalid')

    def test_create_target_provider_invalid(self):
        """Test creating invalid target provider."""
        with pytest.raises(ValueError, match="Unsupported target provider"):
            self.cli._create_target_provider('invalid')

    @patch.dict(os.environ, {})
    def test_create_source_provider_missing_token(self):
        """Test creating source provider without token."""
        with pytest.raises(ValueError, match="YANDEX_ACCESS_TOKEN environment variable is required"):
            self.cli._create_source_provider('yandex')

    @patch.dict(os.environ, {'YANDEX_ACCESS_TOKEN': 'test_token'})
    def test_create_target_provider_missing_tokens(self):
        """Test creating target provider without tokens."""
        with pytest.raises(ValueError, match="SPOTIFY_ACCESS_TOKEN and SPOTIFY_REFRESH_TOKEN environment variables are required"):
            self.cli._create_target_provider('spotify')

    def test_create_job_id(self):
        """Test job ID creation."""
        job_id = self.cli._create_job_id()

        assert job_id.startswith('musync_')
        assert len(job_id) > len('musync_')  # Should have timestamp

    @patch('app.interfaces.cli.logging')
    def test_setup_logging(self, mock_logging):
        """Test logging setup."""
        self.cli._setup_logging('DEBUG')

        mock_logging.basicConfig.assert_called_once()
        call_args = mock_logging.basicConfig.call_args[1]

        assert call_args['level'] == mock_logging.DEBUG
        assert 'format' in call_args
        assert 'handlers' in call_args

    @patch('app.interfaces.cli.sys')
    @patch('app.interfaces.cli.logging')
    def test_transfer_playlists_dry_run(self, mock_logging, mock_sys):
        """Test transfer playlists in dry-run mode."""
        # Mock arguments
        args = Mock()
        args.source = 'yandex'
        args.target = 'spotify'
        args.dry_run = True
        args.job_id = 'test_job'
        args.playlists = None
        args.report_path = 'test_reports/'
        args.checkpoint_path = 'test_checkpoints/'

        # Mock providers
        with patch.object(self.cli, '_create_source_provider') as mock_source, \
             patch.object(self.cli, '_create_target_provider') as mock_target, \
             patch.object(self.cli, '_generate_final_report') as mock_report, \
             patch('app.interfaces.cli.YandexMusicProvider') as mock_yandex_class, \
             patch('app.interfaces.cli.SpotifyProvider') as mock_spotify_class:

            mock_source_provider = Mock()
            mock_target_provider = Mock()
            mock_pipeline = Mock()

            mock_yandex_class.return_value = mock_source_provider
            mock_spotify_class.return_value = mock_target_provider
            mock_source.return_value = mock_source_provider
            mock_target.return_value = mock_target_provider

            # Mock playlist
            mock_playlist = Mock()
            mock_playlist.id = 'test_playlist'
            mock_playlist.name = 'Test Playlist'
            mock_playlist.is_owned = True

            mock_source_provider.list_owned_playlists.return_value = [mock_playlist]

            # Mock transfer result
            mock_result = Mock()
            mock_result.playlist_id = 'target_playlist'
            mock_result.playlist_name = 'Test Playlist'
            mock_result.total_tracks = 10
            mock_result.matched_tracks = 8
            mock_result.added_tracks = 0
            mock_result.duration_ms = 1000

            # Import and mock TransferPipeline
            with patch('app.interfaces.cli.TransferPipeline', return_value=mock_pipeline) as mock_pipeline_class:
                mock_pipeline.transfer_playlist.return_value = mock_result

                # Execute
                self.cli._transfer_playlists(args)

                # Verify pipeline creation
                mock_pipeline_class.assert_called_once()

                # Verify transfer call with dry_run=True
                mock_pipeline.transfer_playlist.assert_called_once_with(
                    source_playlist=mock_playlist,
                    job_id='test_job',
                    dry_run=True
                )

                # Verify final report generation
                mock_report.assert_called_once()

    @patch('app.interfaces.cli.sys')
    @patch('app.interfaces.cli.logging')
    def test_transfer_playlists_no_dry_run(self, mock_logging, mock_sys):
        """Test transfer playlists in normal mode."""
        # Mock arguments
        args = Mock()
        args.source = 'yandex'
        args.target = 'spotify'
        args.dry_run = False
        args.job_id = 'test_job'
        args.playlists = None
        args.report_path = 'test_reports/'
        args.checkpoint_path = 'test_checkpoints/'

        # Mock providers
        with patch.object(self.cli, '_create_source_provider') as mock_source, \
             patch.object(self.cli, '_create_target_provider') as mock_target, \
             patch.object(self.cli, '_generate_final_report') as mock_report, \
             patch('app.interfaces.cli.YandexMusicProvider') as mock_yandex_class, \
             patch('app.interfaces.cli.SpotifyProvider') as mock_spotify_class:

            mock_source_provider = Mock()
            mock_target_provider = Mock()
            mock_pipeline = Mock()

            mock_yandex_class.return_value = mock_source_provider
            mock_spotify_class.return_value = mock_target_provider
            mock_source.return_value = mock_source_provider
            mock_target.return_value = mock_target_provider

            # Mock playlist
            mock_playlist = Mock()
            mock_playlist.id = 'test_playlist'
            mock_playlist.name = 'Test Playlist'
            mock_playlist.is_owned = True

            mock_source_provider.list_owned_playlists.return_value = [mock_playlist]

            # Mock transfer result
            mock_result = Mock()
            mock_result.playlist_id = 'target_playlist'
            mock_result.playlist_name = 'Test Playlist'
            mock_result.total_tracks = 10
            mock_result.matched_tracks = 8
            mock_result.added_tracks = 8
            mock_result.duration_ms = 1000

            # Import and mock TransferPipeline
            with patch('app.interfaces.cli.TransferPipeline', return_value=mock_pipeline) as mock_pipeline_class:
                mock_pipeline.transfer_playlist.return_value = mock_result

                # Execute
                self.cli._transfer_playlists(args)

                # Verify transfer call with dry_run=False
                mock_pipeline.transfer_playlist.assert_called_once_with(
                    source_playlist=mock_playlist,
                    job_id='test_job',
                    dry_run=False
                )

    @patch('app.interfaces.cli.sys')
    @patch('app.interfaces.cli.logging')
    def test_transfer_playlists_no_playlists(self, mock_logging, mock_sys):
        """Test transfer when no playlists are found."""
        args = Mock()
        args.source = 'yandex'
        args.target = 'spotify'
        args.dry_run = False
        args.job_id = 'test_job'
        args.playlists = None
        args.report_path = 'test_reports/'
        args.checkpoint_path = 'test_checkpoints/'

        with patch.object(self.cli, '_create_source_provider') as mock_source, \
             patch.object(self.cli, '_create_target_provider') as mock_target, \
             patch('app.interfaces.cli.YandexMusicProvider') as mock_yandex_class, \
             patch('app.interfaces.cli.SpotifyProvider') as mock_spotify_class:

            mock_source_provider = Mock()
            mock_target_provider = Mock()

            mock_yandex_class.return_value = mock_source_provider
            mock_spotify_class.return_value = mock_target_provider
            mock_source.return_value = mock_source_provider
            mock_target.return_value = mock_target_provider

            # No owned playlists
            mock_source_provider.list_owned_playlists.return_value = []

            # Execute
            self.cli._transfer_playlists(args)

            # Should not crash, just log warning
            mock_logging.getLogger.return_value.warning.assert_called_with("No playlists to transfer")

    @patch('app.interfaces.cli.sys')
    @patch('app.interfaces.cli.logging')
    def test_transfer_playlists_error_handling(self, mock_logging, mock_sys):
        """Test error handling during playlist transfer."""
        args = Mock()
        args.source = 'yandex'
        args.target = 'spotify'
        args.dry_run = False
        args.job_id = 'test_job'
        args.playlists = None
        args.report_path = 'test_reports/'
        args.checkpoint_path = 'test_checkpoints/'

        with patch.object(self.cli, '_create_source_provider') as mock_source, \
             patch.object(self.cli, '_create_target_provider') as mock_target, \
             patch.object(self.cli, '_generate_final_report') as mock_report, \
             patch('app.interfaces.cli.YandexMusicProvider') as mock_yandex_class, \
             patch('app.interfaces.cli.SpotifyProvider') as mock_spotify_class:

            mock_source_provider = Mock()
            mock_target_provider = Mock()
            mock_pipeline = Mock()

            mock_yandex_class.return_value = mock_source_provider
            mock_spotify_class.return_value = mock_target_provider
            mock_source.return_value = mock_source_provider
            mock_target.return_value = mock_target_provider

            # Mock playlist
            mock_playlist = Mock()
            mock_playlist.id = 'test_playlist'
            mock_playlist.name = 'Test Playlist'
            mock_playlist.is_owned = True

            mock_source_provider.list_owned_playlists.return_value = [mock_playlist]

            # Mock pipeline to raise exception
            with patch('app.interfaces.cli.TransferPipeline', return_value=mock_pipeline) as mock_pipeline_class:
                mock_pipeline.transfer_playlist.side_effect = Exception("Transfer failed")

                # Execute
                self.cli._transfer_playlists(args)

                # Should continue and log error
                mock_logging.getLogger.return_value.error.assert_called()

    def test_list_playlists_yandex(self):
        """Test listing Yandex playlists."""
        args = Mock()
        args.provider = 'yandex'

        with patch.object(self.cli, '_create_source_provider') as mock_create, \
             patch('builtins.print') as mock_print:

            mock_provider = Mock()
            mock_playlist = Mock()
            mock_playlist.id = 'playlist_1'
            mock_playlist.name = 'Test Playlist'
            mock_playlist.is_owned = True

            mock_provider.list_owned_playlists.return_value = [mock_playlist]
            mock_create.return_value = mock_provider

            self.cli._list_playlists(args)

            mock_print.assert_called()
            # Verify ownership indicator
            print_calls = [call[0][0] for call in mock_print.call_args_list if '[OWNED]' in str(call)]
            assert len(print_calls) > 0

    def test_list_playlists_spotify(self):
        """Test listing Spotify playlists."""
        args = Mock()
        args.provider = 'spotify'

        with patch.object(self.cli, '_create_target_provider') as mock_create, \
             patch('builtins.print') as mock_print:

            mock_provider = Mock()
            mock_playlist = Mock()
            mock_playlist.id = 'playlist_1'
            mock_playlist.name = 'Spotify Playlist'
            mock_playlist.is_owned = False

            mock_provider.list_owned_playlists.return_value = [mock_playlist]
            mock_create.return_value = mock_provider

            self.cli._list_playlists(args)

            mock_print.assert_called()
            # Verify no ownership indicator for not owned
            print_calls = [call[0][0] for call in mock_print.call_args_list if '[NOT OWNED]' in str(call)]
            assert len(print_calls) > 0

    def test_generate_final_report(self):
        """Test final report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock results
            mock_result1 = Mock()
            mock_result1.playlist_id = 'playlist_1'
            mock_result1.playlist_name = 'Playlist 1'
            mock_result1.total_tracks = 10
            mock_result1.matched_tracks = 8
            mock_result1.added_tracks = 8
            mock_result1.not_found_tracks = 2
            mock_result1.ambiguous_tracks = 0
            mock_result1.failed_tracks = 0
            mock_result1.duration_ms = 1000
            mock_result1.errors = []

            mock_result2 = Mock()
            mock_result2.playlist_id = 'playlist_2'
            mock_result2.playlist_name = 'Playlist 2'
            mock_result2.total_tracks = 5
            mock_result2.matched_tracks = 4
            mock_result2.added_tracks = 4
            mock_result2.not_found_tracks = 1
            mock_result2.ambiguous_tracks = 0
            mock_result2.failed_tracks = 0
            mock_result2.duration_ms = 500
            mock_result2.errors = []

            results = [mock_result1, mock_result2]
            job_id = 'test_job_123'

            # Generate report
            self.cli._generate_final_report(results, job_id, temp_dir, False)

            # Verify report file was created
            report_file = os.path.join(temp_dir, f"transfer_report_{job_id}.json")
            assert os.path.exists(report_file)

            # Verify report content
            import json
            with open(report_file, 'r') as f:
                report_data = json.load(f)

            assert report_data['job_id'] == job_id
            assert report_data['dry_run'] is False
            assert report_data['total_playlists'] == 2
            assert report_data['total_tracks'] == 15
            assert report_data['matched_tracks'] == 12
            assert report_data['added_tracks'] == 12
            assert report_data['not_found_tracks'] == 3
            assert 'timestamp' in report_data
            assert len(report_data['results']) == 2

    @patch('app.interfaces.cli.sys')
    def test_run_without_command(self, mock_sys):
        """Test running CLI without command."""
        with patch.object(self.cli.parser, 'parse_args') as mock_parse, \
             patch.object(self.cli.parser, 'print_help') as mock_help, \
             patch.object(self.cli, '_setup_logging'):

            mock_args = Mock()
            mock_args.command = None
            mock_args.log_level = 'INFO'
            mock_parse.return_value = mock_args

            self.cli.run()

            # The method calls print_help twice: once in the first if block and once in the else block
            assert mock_help.call_count == 2
            mock_sys.exit.assert_called_with(1)

    @patch('app.interfaces.cli.sys')
    def test_run_transfer_command(self, mock_sys):
        """Test running transfer command."""
        with patch.object(self.cli.parser, 'parse_args') as mock_parse, \
             patch.object(self.cli, '_transfer_playlists') as mock_transfer, \
             patch.object(self.cli, '_setup_logging'):

            mock_args = Mock()
            mock_args.command = 'transfer'
            mock_args.log_level = 'INFO'
            mock_parse.return_value = mock_args

            self.cli.run()

            mock_transfer.assert_called_once_with(mock_args)

    @patch('app.interfaces.cli.sys')
    def test_run_list_command(self, mock_sys):
        """Test running list command."""
        with patch.object(self.cli.parser, 'parse_args') as mock_parse, \
             patch.object(self.cli, '_list_playlists') as mock_list, \
             patch.object(self.cli, '_setup_logging'):

            mock_args = Mock()
            mock_args.command = 'list'
            mock_args.log_level = 'INFO'
            mock_parse.return_value = mock_args

            self.cli.run()

            mock_list.assert_called_once_with(mock_args)

    @patch('app.interfaces.cli.sys')
    def test_run_invalid_command(self, mock_sys):
        """Test running invalid command."""
        with patch.object(self.cli.parser, 'parse_args') as mock_parse, \
             patch.object(self.cli.parser, 'print_help') as mock_help, \
             patch.object(self.cli, '_setup_logging'):

            mock_args = Mock()
            mock_args.command = 'invalid'
            mock_args.log_level = 'INFO'
            mock_parse.return_value = mock_args

            self.cli.run()

            mock_help.assert_called_once()
            mock_sys.exit.assert_called_with(1)
