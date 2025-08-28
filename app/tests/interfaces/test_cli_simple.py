import pytest
from unittest.mock import Mock, patch
from app.interfaces.cli import CLI


class TestCLISimple:
    """Simplified tests for CLI functionality focusing on core features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = CLI()

    def test_create_parser(self):
        """Test argument parser creation."""
        parser = self.cli._create_parser()

        assert parser is not None

        # Test transfer command with dry-run
        args = parser.parse_args(['transfer', '--source', 'yandex', '--target', 'spotify', '--dry-run'])
        assert args.command == 'transfer'
        assert args.source == 'yandex'
        assert args.target == 'spotify'
        assert args.dry_run is True

    def test_dry_run_flag_parsing(self):
        """Test that dry-run flag is properly parsed."""
        args = self.cli.parser.parse_args(['transfer', '--source', 'yandex', '--target', 'spotify', '--dry-run'])
        assert args.dry_run is True

    def test_job_id_creation(self):
        """Test job ID creation."""
        job_id = self.cli._create_job_id()
        assert job_id.startswith('musync_')
        assert len(job_id) > len('musync_')

    @patch.dict('os.environ', {'YANDEX_ACCESS_TOKEN': 'test_token'})
    @patch('app.interfaces.cli.YandexMusicProvider')
    def test_create_source_provider_yandex(self, mock_provider_class):
        """Test creating Yandex source provider."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        provider = self.cli._create_source_provider('yandex')
        assert provider == mock_provider

    @patch.dict('os.environ', {
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

    def test_invalid_source_provider(self):
        """Test creating invalid source provider."""
        with pytest.raises(ValueError, match="Unsupported source provider"):
            self.cli._create_source_provider('invalid')

    def test_invalid_target_provider(self):
        """Test creating invalid target provider."""
        with pytest.raises(ValueError, match="Unsupported target provider"):
            self.cli._create_target_provider('invalid')
