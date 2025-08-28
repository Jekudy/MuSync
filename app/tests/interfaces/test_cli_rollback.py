import os
import pytest
from unittest.mock import patch

from app.interfaces.cli import CLI


class TestCLIRollback:
    def test_env_rollback_forces_dry_run(self):
        cli = CLI()
        with patch.dict(os.environ, {"MUSYNC_ROLLBACK": "1", "YANDEX_ACCESS_TOKEN": "x", "SPOTIFY_ACCESS_TOKEN": "a", "SPOTIFY_REFRESH_TOKEN": "b"}, clear=False):
            with patch('sys.argv', ['musync', 'transfer', '--source', 'yandex', '--target', 'spotify']):
                # stub providers to avoid real calls
                with patch('app.interfaces.cli.CLI._create_source_provider') as src_mock, \
                     patch('app.interfaces.cli.CLI._create_target_provider') as tgt_mock, \
                     patch('app.interfaces.cli.TransferPipeline') as pipe_mock, \
                     patch('sys.exit') as mock_exit:
                    class DummySource:
                        def list_owned_playlists(self):
                            return [type('P', (), {'id': 'p1', 'name': 'n1', 'is_owned': True})()]
                    src_mock.return_value = DummySource()
                    tgt_mock.return_value = object()
                    pipeline_instance = pipe_mock.return_value
                    pipeline_instance.transfer_playlist.return_value = type('R', (), {
                        'playlist_id': 'sp_x', 'playlist_name': 'x', 'total_tracks': 0,
                        'matched_tracks': 0, 'not_found_tracks': 0, 'ambiguous_tracks': 0,
                        'added_tracks': 0, 'duplicate_tracks': 0, 'failed_tracks': 0,
                        'errors': [], 'duration_ms': 0
                    })()
                    # run
                    try:
                        cli.run()
                    except SystemExit:
                        pass
                    # ensure dry_run=True was passed
                    assert any(kw.get('dry_run') is True for (_, kw) in pipeline_instance.transfer_playlist.call_args_list)
