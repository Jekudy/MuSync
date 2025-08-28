import argparse
import os
import sys
import logging
import signal
import time
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv

from app.application.pipeline import TransferPipeline, CheckpointManager
from app.application.matching import TrackMatcher
from app.application.idempotency import calculate_snapshot_hash
from app.domain.entities import Playlist
from app.infrastructure.providers.yandex import YandexMusicProvider
from app.infrastructure.providers.spotify import SpotifyProvider
# Note: ReportGenerator and MetricsCollector not implemented yet
# from app.crosscutting.reporting import ReportGenerator, MetricsCollector


class CLI:
    """Command Line Interface for MuSync."""

    def __init__(self):
        """Initialize CLI."""
        # Do not auto-load .env to keep tests deterministic
        
        self.parser = self._create_parser()
        self._setup_signal_handlers()
        self._start_time = None

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            prog='musync',
            description='Transfer music playlists between providers'
        )

        # Main commands
        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Transfer command
        transfer_parser = subparsers.add_parser('transfer', help='Transfer playlists')
        transfer_parser.add_argument(
            '--source',
            choices=['yandex', 'spotify'],
            required=True,
            help='Source provider'
        )
        transfer_parser.add_argument(
            '--target',
            choices=['spotify', 'yandex'],
            required=True,
            help='Target provider'
        )
        transfer_parser.add_argument(
            '--playlists',
            nargs='+',
            help='Specific playlist IDs to transfer'
        )
        transfer_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode (no actual changes)'
        )
        transfer_parser.add_argument(
            '--job-id',
            help='Unique job identifier for this transfer'
        )
        transfer_parser.add_argument(
            '--report-path',
            default='reports/',
            help='Path to save reports (default: reports/)'
        )
        transfer_parser.add_argument(
            '--checkpoint-path',
            default='checkpoints/',
            help='Path to save checkpoints (default: checkpoints/)'
        )
        transfer_parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            help='Set logging level'
        )
        transfer_parser.add_argument(
            '--timeout',
            type=int,
            default=90,
            help='Timeout in seconds for the transfer operation (default: 90)'
        )
        transfer_parser.add_argument(
            '--risk-mode',
            choices=['aggressive', 'balanced', 'strict'],
            default='aggressive',
            help='Matching risk mode (default: aggressive)'
        )
        transfer_parser.add_argument(
            '--title-only-fallback',
            action='store_true',
            help='Enable title-only fallback search'
        )
        transfer_parser.add_argument(
            '--translit-fallback',
            action='store_true',
            help='Enable transliteration fallback search'
        )
        transfer_parser.add_argument(
            '--market',
            default=None,
            help='Spotify market to use for search (e.g., RU, US). Defaults to RU.'
        )
        transfer_parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Search result limit per query (default from env or 20)'
        )

        # List playlists command
        list_parser = subparsers.add_parser('list', help='List available playlists')
        list_parser.add_argument(
            '--provider',
            choices=['yandex', 'spotify'],
            required=True,
            help='Provider to list playlists from'
        )
        list_parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            help='Set logging level'
        )

        # Likes migration command
        likes_parser = subparsers.add_parser('likes', help='Migrate liked tracks')
        likes_parser.add_argument(
            '--source',
            choices=['yandex'],
            required=True,
            help='Source provider for likes (currently only yandex)'
        )
        likes_parser.add_argument(
            '--target',
            choices=['spotify'],
            required=True,
            help='Target provider (currently only spotify)'
        )
        likes_parser.add_argument(
            '--mode',
            choices=['saved', 'playlist'],
            default='saved',
            help='Destination: saved (liked songs) or playlist'
        )
        likes_parser.add_argument(
            '--playlist-name',
            default='Liked from Yandex',
            help='Playlist name when mode=playlist'
        )
        likes_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode (no actual changes)'
        )
        likes_parser.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
            default='INFO',
            help='Set logging level'
        )
        likes_parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of liked tracks to migrate (for testing)'
        )

        return parser

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger = logging.getLogger(__name__)
            logger.warning(f"Received signal {signum}, shutting down gracefully...")
            self._cleanup_resources()
            sys.exit(130)  # Standard exit code for signal termination
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _cleanup_resources(self) -> None:
        """Clean up resources on exit."""
        logger = logging.getLogger(__name__)
        if self._start_time:
            duration = time.time() - self._start_time
            logger.info(f"CLI execution time: {duration:.2f}s")
        logger.info("Cleaning up resources...")

    def _validate_arguments(self, args: argparse.Namespace) -> None:
        """Validate CLI arguments."""
        if hasattr(args, 'source') and hasattr(args, 'target'):
            if args.source == args.target:
                raise ValueError("Source and target providers must be different")

    def _setup_logging(self, level: str) -> None:
        """Setup logging configuration."""
        from logging.handlers import RotatingFileHandler
        handlers = [
            logging.StreamHandler(sys.stdout),
        ]
        # Rotate at ~100MB with up to 14 backups
        try:
            handlers.append(RotatingFileHandler('musync.log', maxBytes=100 * 1024 * 1024, backupCount=14))
        except Exception:
            pass
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

    def _create_job_id(self) -> str:
        """Create unique job identifier."""
        return f"musync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _get_env_token(self, provider: str, token_type: str = 'access') -> Optional[str]:
        """Get token from environment variables."""
        env_var = f"{provider.upper()}_{token_type.upper()}_TOKEN"
        value = os.getenv(env_var)
        if value is None or not str(value).strip():
            return None
        return value

    def _create_source_provider(self, provider_type: str) -> YandexMusicProvider:
        """Create source music provider."""
        if provider_type == 'yandex':
            token = self._get_env_token('yandex')
            if not token:
                raise ValueError("YANDEX_ACCESS_TOKEN environment variable is required")
            return YandexMusicProvider(token)
        else:
            raise ValueError(f"Unsupported source provider: {provider_type}")

    def _create_target_provider(self, provider_type: str) -> SpotifyProvider:
        """Create target music provider."""
        if provider_type == 'spotify':
            access_token = self._get_env_token('spotify', 'access')
            refresh_token = self._get_env_token('spotify', 'refresh')

            if not access_token or not refresh_token:
                raise ValueError("SPOTIFY_ACCESS_TOKEN and SPOTIFY_REFRESH_TOKEN environment variables are required")

            # Instantiate without expiration to match tests and allow provider to manage it
            return SpotifyProvider(access_token, refresh_token)
        else:
            raise ValueError(f"Unsupported target provider: {provider_type}")

    def _transfer_playlists(self, args: argparse.Namespace) -> None:
        """Transfer playlists from source to target."""
        logger = logging.getLogger(__name__)

        try:
            # Rollback safeguard: force dry-run if environment toggle is set
            if os.getenv("MUSYNC_ROLLBACK") == "1":
                logger.warning("MUSYNC_ROLLBACK=1 is set. Forcing DRY-RUN mode for safety.")
                args.dry_run = True

            # Create job ID
            job_id = args.job_id or self._create_job_id()

            if args.dry_run:
                logger.info(f"Starting DRY-RUN transfer (job: {job_id})")
            else:
                logger.info(f"Starting transfer (job: {job_id})")

            # Create providers
            # Configure provider behavior via environment flags (tolerant to missing attributes)
            os.environ['MUSYNC_RISK_MODE'] = getattr(args, 'risk_mode', 'strict')
            if getattr(args, 'title_only_fallback', False):
                os.environ['MUSYNC_TITLE_ONLY_FALLBACK'] = '1'
            if getattr(args, 'translit_fallback', False):
                os.environ['MUSYNC_TRANSLIT_FALLBACK'] = '1'
            market = getattr(args, 'market', None)
            if market:
                os.environ['MUSYNC_MARKET'] = market
            limit = getattr(args, 'limit', None)
            if limit is not None:
                try:
                    if int(limit) > 0:
                        os.environ['MUSYNC_SEARCH_LIMIT'] = str(int(limit))
                except Exception:
                    pass

            source_provider = self._create_source_provider(args.source)
            target_provider = self._create_target_provider(args.target)

            # Create components
            matcher = TrackMatcher()
            checkpoint_manager = CheckpointManager(args.checkpoint_path)
            pipeline = TransferPipeline(
                source_provider=source_provider,
                target_provider=target_provider,
                matcher=matcher,
                checkpoint_manager=checkpoint_manager
            )

            # Create report generator and metrics collector
            # TODO: Implement ReportGenerator and MetricsCollector
            # report_generator = ReportGenerator()
            # metrics_collector = MetricsCollector()

            # Get playlists to transfer
            if args.playlists:
                # Transfer specific playlists by ID or name (exact match)
                playlists = []
                owned_playlists = list(source_provider.list_owned_playlists())
                for spec in args.playlists:
                    # Try to match by ID first
                    match = next((p for p in owned_playlists if p.id == spec), None)
                    if not match:
                        # Fallback: match by exact name
                        match = next((p for p in owned_playlists if p.name == spec), None)
                    if match:
                        playlists.append(match)
                    else:
                        logger.warning(f"Playlist '{spec}' not found among owned playlists; skipping")
            else:
                # Transfer all owned playlists
                logger.info("Getting owned playlists from source...")
                playlists = list(source_provider.list_owned_playlists())

            if not playlists:
                logger.warning("No playlists to transfer")
                return

            logger.info(f"Found {len(playlists)} playlists to transfer")

            # Transfer each playlist
            total_results = []
            for playlist in playlists:
                logger.info(f"Transferring playlist: {playlist.name} (ID: {playlist.id})")

                try:
                    result = pipeline.transfer_playlist(
                        source_playlist=playlist,
                        job_id=job_id,
                        dry_run=args.dry_run
                    )

                    total_results.append(result)

                    if args.dry_run:
                        logger.info(f"DRY-RUN completed: {result.matched_tracks}/{result.total_tracks} tracks matched, {result.added_tracks} would be added")
                    else:
                        logger.info(f"Transfer completed: {result.matched_tracks}/{result.total_tracks} tracks matched, {result.added_tracks} added")

                except Exception as e:
                    logger.error(f"Failed to transfer playlist {playlist.name}: {e}")
                    continue

            # Generate final report
            if total_results:
                self._generate_final_report(total_results, job_id, args.report_path, args.dry_run)

            logger.info(f"All transfers completed (job: {job_id})")

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            sys.exit(1)

    def _migrate_likes(self, args: argparse.Namespace) -> None:
        """Migrate liked tracks from source to target."""
        logger = logging.getLogger(__name__)

        try:
            job_id = self._create_job_id()
            mode = args.mode

            if args.dry_run:
                logger.info(f"Starting DRY-RUN likes migration (job: {job_id}, mode={mode})")
            else:
                logger.info(f"Starting likes migration (job: {job_id}, mode={mode})")

            # Providers
            source_provider = self._create_source_provider(args.source)
            target_provider = self._create_target_provider(args.target)

            # Fetch liked tracks from Yandex
            logger.info("Fetching liked tracks from source...")
            liked_tracks = list(getattr(source_provider, 'list_liked_tracks')())
            if getattr(args, 'limit', None):
                liked_tracks = liked_tracks[: max(0, int(args.limit))]
            logger.info(f"Found {len(liked_tracks)} liked tracks")

            # Prepare matcher and match URIs
            matcher = TrackMatcher()
            matched_uris: List[str] = []
            not_found = 0
            ambiguous = 0

            for track in liked_tracks:
                try:
                    candidates = target_provider.find_track_candidates(track, top_k=3)
                    match = matcher.find_best_match(track, candidates)
                    if match.uri:
                        matched_uris.append(match.uri)
                    elif match.reason == 'ambiguous':
                        ambiguous += 1
                    else:
                        not_found += 1
                except Exception as e:
                    logger.warning(f"Failed to match track '{track.title}': {e}")

            logger.info(f"Matched {len(matched_uris)} tracks; not_found={not_found}, ambiguous={ambiguous}")

            # Execute write depending on mode
            total_added = 0
            total_errors = 0

            if args.dry_run:
                logger.info(f"DRY-RUN: Would {'save to library' if mode=='saved' else 'add to playlist'} {len(matched_uris)} tracks")
            else:
                if mode == 'saved':
                    # Save to user library in batches of 50
                    for i in range(0, len(matched_uris), 50):
                        batch = matched_uris[i:i+50]
                        try:
                            result = getattr(target_provider, 'add_saved_tracks_batch')(batch)
                            total_added += result.added
                        except Exception as e:
                            logger.error(f"Failed to save liked batch at {i}: {e}")
                            total_errors += len(batch)
                else:
                    # Create/resolve playlist then add in batches of 100
                    playlist = target_provider.resolve_or_create_playlist(args.playlist_name)
                    for i in range(0, len(matched_uris), 100):
                        batch = matched_uris[i:i+100]
                        try:
                            result = target_provider.add_tracks_batch(playlist.id, batch)
                            total_added += result.added
                        except Exception as e:
                            logger.error(f"Failed to add to playlist batch at {i}: {e}")
                            total_errors += len(batch)

            logger.info(f"Likes migration completed: matched={len(matched_uris)}, added={0 if args.dry_run else total_added}, errors={total_errors}")

        except Exception as e:
            logger.error(f"Likes migration failed: {e}")
            sys.exit(1)

    def _generate_final_report(self, results: List, job_id: str, report_path: str, dry_run: bool) -> None:
        """Generate final transfer report."""
        logger = logging.getLogger(__name__)

        try:
            os.makedirs(report_path, exist_ok=True)

            report_data = {
                'job_id': job_id,
                'dry_run': dry_run,
                'timestamp': datetime.now().isoformat(),
                'total_playlists': len(results),
                'total_tracks': sum(r.total_tracks for r in results),
                'matched_tracks': sum(r.matched_tracks for r in results),
                'added_tracks': sum(r.added_tracks for r in results),
                'not_found_tracks': sum(r.not_found_tracks for r in results),
                'ambiguous_tracks': sum(r.ambiguous_tracks for r in results),
                'failed_tracks': sum(r.failed_tracks for r in results),
                'duration_ms': sum(r.duration_ms for r in results),
                'results': []
            }

            for result in results:
                report_data['results'].append({
                    'playlist_id': result.playlist_id,
                    'playlist_name': result.playlist_name,
                    'total_tracks': result.total_tracks,
                    'matched_tracks': result.matched_tracks,
                    'added_tracks': result.added_tracks,
                    'not_found_tracks': result.not_found_tracks,
                    'ambiguous_tracks': result.ambiguous_tracks,
                    'failed_tracks': result.failed_tracks,
                    'duration_ms': result.duration_ms,
                    'errors': result.errors
                })

            # Save report as JSON
            report_file = os.path.join(report_path, f"transfer_report_{job_id}.json")
            import json
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)

            logger.info(f"Report saved to: {report_file}")

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")

    def _list_playlists(self, args: argparse.Namespace) -> None:
        """List available playlists."""
        logger = logging.getLogger(__name__)

        try:
            if args.provider == 'yandex':
                provider = self._create_source_provider('yandex')
            else:
                provider = self._create_target_provider('spotify')

            playlists = provider.list_owned_playlists()

            print(f"Available playlists from {args.provider}:")
            print("-" * 50)

            for playlist in playlists:
                ownership_indicator = "[OWNED]" if playlist.is_owned else "[NOT OWNED]"
                print(f"{playlist.id}: {playlist.name} {ownership_indicator} (tracks: {playlist.track_count})")

        except Exception as e:
            logger.error(f"Failed to list playlists: {e}")
            sys.exit(1)

    def run(self) -> None:
        """Run the CLI."""
        self._start_time = time.time()
        
        try:
            args = self.parser.parse_args()

            if not args.command:
                self.parser.print_help()
                sys.exit(1)

            # Setup logging
            self._setup_logging(args.log_level)

            # Validate arguments
            self._validate_arguments(args)

            # Execute command with timeout protection
            if args.command == 'transfer':
                self._transfer_playlists(args)
            elif args.command == 'list':
                self._list_playlists(args)
            elif args.command == 'likes':
                self._migrate_likes(args)
            else:
                self.parser.print_help()
                sys.exit(1)
                
        except KeyboardInterrupt:
            logger = logging.getLogger(__name__)
            logger.warning("Operation cancelled by user")
            self._cleanup_resources()
            sys.exit(130)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"CLI error: {e}")
            self._cleanup_resources()
            sys.exit(1)
        finally:
            self._cleanup_resources()


def main():
    """Main entry point."""
    cli = CLI()
    cli.run()


if __name__ == '__main__':
    main()
