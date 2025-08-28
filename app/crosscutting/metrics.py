import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, NamedTuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading


@dataclass
class BatchMetrics:
    """Metrics for a single batch processing."""
    batch_id: str
    playlist_id: str
    track_count: int
    success_count: int
    error_count: int
    not_found_count: int
    retry_count: int
    rate_limit_wait_ms: int
    duration_ms: int
    start_time: datetime
    end_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for this batch."""
        if self.track_count == 0:
            return 0.0
        return self.success_count / self.track_count
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate for this batch."""
        if self.track_count == 0:
            return 0.0
        return self.error_count / self.track_count
    
    @property
    def not_found_rate(self) -> float:
        """Calculate not found rate for this batch."""
        if self.track_count == 0:
            return 0.0
        return self.not_found_count / self.track_count


@dataclass
class JobMetrics:
    """Aggregated metrics for entire job."""
    job_id: str
    snapshot_hash: str
    source_provider: str
    target_provider: str
    total_playlists: int
    total_tracks: int
    total_batches: int
    total_success_count: int
    total_error_count: int
    total_not_found_count: int
    total_retry_count: int
    total_rate_limit_wait_ms: int
    total_duration_ms: int
    start_time: datetime
    end_time: Optional[datetime] = None
    batches: List[BatchMetrics] = None
    
    def __post_init__(self):
        if self.batches is None:
            self.batches = []
    
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate for the job."""
        if self.total_tracks == 0:
            return 0.0
        return self.total_success_count / self.total_tracks
    
    @property
    def overall_error_rate(self) -> float:
        """Calculate overall error rate for the job."""
        if self.total_tracks == 0:
            return 0.0
        return self.total_error_count / self.total_tracks
    
    @property
    def overall_not_found_rate(self) -> float:
        """Calculate overall not found rate for the job."""
        if self.total_tracks == 0:
            return 0.0
        return self.total_not_found_count / self.total_tracks
    
    @property
    def average_batch_duration_ms(self) -> float:
        """Calculate average batch duration."""
        if self.total_batches == 0:
            return 0.0
        return self.total_duration_ms / self.total_batches
    
    @property
    def average_retry_count(self) -> float:
        """Calculate average retry count per batch."""
        if self.total_batches == 0:
            return 0.0
        return self.total_retry_count / self.total_batches


class MetricsCollector:
    """Collects and manages metrics for the transfer pipeline."""
    
    def __init__(self, job_id: str, snapshot_hash: str, 
                 source_provider: str, target_provider: str):
        """Initialize metrics collector."""
        self.job_id = job_id
        self.snapshot_hash = snapshot_hash
        self.source_provider = source_provider
        self.target_provider = target_provider
        
        self.job_metrics = JobMetrics(
            job_id=job_id,
            snapshot_hash=snapshot_hash,
            source_provider=source_provider,
            target_provider=target_provider,
            total_playlists=0,
            total_tracks=0,
            total_batches=0,
            total_success_count=0,
            total_error_count=0,
            total_not_found_count=0,
            total_retry_count=0,
            total_rate_limit_wait_ms=0,
            total_duration_ms=0,
            start_time=datetime.now()
        )
        
        self._lock = threading.Lock()
        self._current_batch: Optional[BatchMetrics] = None
    
    def start_job(self) -> None:
        """Mark job start."""
        with self._lock:
            self.job_metrics.start_time = datetime.now()
    
    def end_job(self) -> None:
        """Mark job end."""
        with self._lock:
            self.job_metrics.end_time = datetime.now()
            if self.job_metrics.start_time:
                self.job_metrics.total_duration_ms = int(
                    (self.job_metrics.end_time - self.job_metrics.start_time).total_seconds() * 1000
                )
    
    def start_playlist(self, playlist_id: str, track_count: int) -> None:
        """Mark playlist processing start."""
        with self._lock:
            self.job_metrics.total_playlists += 1
            self.job_metrics.total_tracks += track_count
    
    def start_batch(self, batch_id: str, playlist_id: str, track_count: int) -> None:
        """Mark batch processing start."""
        with self._lock:
            self._current_batch = BatchMetrics(
                batch_id=batch_id,
                playlist_id=playlist_id,
                track_count=track_count,
                success_count=0,
                error_count=0,
                not_found_count=0,
                retry_count=0,
                rate_limit_wait_ms=0,
                duration_ms=0,
                start_time=datetime.now()
            )
    
    def end_batch(self) -> None:
        """Mark batch processing end."""
        with self._lock:
            if self._current_batch:
                self._current_batch.end_time = datetime.now()
                if self._current_batch.start_time:
                    self._current_batch.duration_ms = int(
                        (self._current_batch.end_time - self._current_batch.start_time).total_seconds() * 1000
                    )
                
                # Add batch to job metrics
                self.job_metrics.batches.append(self._current_batch)
                self.job_metrics.total_batches += 1
                self.job_metrics.total_success_count += self._current_batch.success_count
                self.job_metrics.total_error_count += self._current_batch.error_count
                self.job_metrics.total_not_found_count += self._current_batch.not_found_count
                self.job_metrics.total_retry_count += self._current_batch.retry_count
                self.job_metrics.total_rate_limit_wait_ms += self._current_batch.rate_limit_wait_ms
                self.job_metrics.total_duration_ms += self._current_batch.duration_ms
                
                self._current_batch = None
    
    def record_track_success(self) -> None:
        """Record successful track processing."""
        with self._lock:
            if self._current_batch:
                self._current_batch.success_count += 1
    
    def record_track_error(self) -> None:
        """Record track processing error."""
        with self._lock:
            if self._current_batch:
                self._current_batch.error_count += 1
    
    def record_track_not_found(self) -> None:
        """Record track not found."""
        with self._lock:
            if self._current_batch:
                self._current_batch.not_found_count += 1
    
    def record_retry(self) -> None:
        """Record a retry attempt."""
        with self._lock:
            if self._current_batch:
                self._current_batch.retry_count += 1
    
    def record_rate_limit_wait(self, wait_ms: int) -> None:
        """Record rate limit wait time."""
        with self._lock:
            if self._current_batch:
                self._current_batch.rate_limit_wait_ms += wait_ms
    
    @contextmanager
    def batch_context(self, batch_id: str, playlist_id: str, track_count: int):
        """Context manager for batch processing."""
        self.start_batch(batch_id, playlist_id, track_count)
        try:
            yield self
        finally:
            self.end_batch()
    
    def get_job_metrics(self) -> JobMetrics:
        """Get current job metrics."""
        with self._lock:
            return self.job_metrics
    
    def get_batch_metrics(self) -> Optional[BatchMetrics]:
        """Get current batch metrics."""
        with self._lock:
            return self._current_batch
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        with self._lock:
            job_dict = asdict(self.job_metrics)
            # Convert datetime objects to ISO format
            if job_dict['start_time']:
                job_dict['start_time'] = job_dict['start_time'].isoformat()
            if job_dict['end_time']:
                job_dict['end_time'] = job_dict['end_time'].isoformat()
            
            # Convert batch datetime objects
            for batch in job_dict['batches']:
                if batch['start_time']:
                    batch['start_time'] = batch['start_time'].isoformat()
                if batch['end_time']:
                    batch['end_time'] = batch['end_time'].isoformat()
            
            return job_dict
    
    def save_to_file(self, file_path: str) -> None:
        """Save metrics to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def print_summary(self) -> None:
        """Print metrics summary to stdout."""
        metrics = self.get_job_metrics()
        
        print(f"\n=== Metrics Summary for Job {self.job_id} ===")
        print(f"Source Provider: {self.source_provider}")
        print(f"Target Provider: {self.target_provider}")
        print(f"Total Playlists: {metrics.total_playlists}")
        print(f"Total Tracks: {metrics.total_tracks}")
        print(f"Total Batches: {metrics.total_batches}")
        print(f"Overall Success Rate: {metrics.overall_success_rate:.2%}")
        print(f"Overall Error Rate: {metrics.overall_error_rate:.2%}")
        print(f"Overall Not Found Rate: {metrics.overall_not_found_rate:.2%}")
        print(f"Total Duration: {metrics.total_duration_ms}ms")
        print(f"Average Batch Duration: {metrics.average_batch_duration_ms:.0f}ms")
        print(f"Total Retries: {metrics.total_retry_count}")
        print(f"Average Retries per Batch: {metrics.average_retry_count:.1f}")
        print(f"Total Rate Limit Wait: {metrics.total_rate_limit_wait_ms}ms")
        
        if metrics.batches:
            print(f"\n=== Batch Details ===")
            for i, batch in enumerate(metrics.batches, 1):
                print(f"Batch {i} ({batch.batch_id}):")
                print(f"  Playlist: {batch.playlist_id}")
                print(f"  Tracks: {batch.track_count}")
                print(f"  Success: {batch.success_count} ({batch.success_rate:.2%})")
                print(f"  Errors: {batch.error_count} ({batch.error_rate:.2%})")
                print(f"  Not Found: {batch.not_found_count} ({batch.not_found_rate:.2%})")
                print(f"  Retries: {batch.retry_count}")
                print(f"  Duration: {batch.duration_ms}ms")
                print(f"  Rate Limit Wait: {batch.rate_limit_wait_ms}ms")


class MetricsAggregator:
    """Aggregates metrics from multiple jobs."""
    
    def __init__(self):
        """Initialize metrics aggregator."""
        self.jobs: List[JobMetrics] = []
    
    def add_job_metrics(self, job_metrics: JobMetrics) -> None:
        """Add job metrics to aggregator."""
        self.jobs.append(job_metrics)
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all jobs."""
        if not self.jobs:
            return {}
        
        total_jobs = len(self.jobs)
        total_playlists = sum(job.total_playlists for job in self.jobs)
        total_tracks = sum(job.total_tracks for job in self.jobs)
        total_success = sum(job.total_success_count for job in self.jobs)
        total_errors = sum(job.total_error_count for job in self.jobs)
        total_not_found = sum(job.total_not_found_count for job in self.jobs)
        total_retries = sum(job.total_retry_count for job in self.jobs)
        total_duration = sum(job.total_duration_ms for job in self.jobs)
        total_rate_limit_wait = sum(job.total_rate_limit_wait_ms for job in self.jobs)
        
        return {
            'summary': {
                'total_jobs': total_jobs,
                'total_playlists': total_playlists,
                'total_tracks': total_tracks,
                'overall_success_rate': total_success / total_tracks if total_tracks > 0 else 0.0,
                'overall_error_rate': total_errors / total_tracks if total_tracks > 0 else 0.0,
                'overall_not_found_rate': total_not_found / total_tracks if total_tracks > 0 else 0.0,
                'total_retries': total_retries,
                'total_duration_ms': total_duration,
                'total_rate_limit_wait_ms': total_rate_limit_wait,
                'average_duration_per_job_ms': total_duration / total_jobs if total_jobs > 0 else 0.0,
                'average_tracks_per_job': total_tracks / total_jobs if total_jobs > 0 else 0.0,
            },
            'jobs': [asdict(job) for job in self.jobs]
        }
    
    def save_aggregated_metrics(self, file_path: str) -> None:
        """Save aggregated metrics to JSON file."""
        aggregated = self.get_aggregated_metrics()
        
        # Convert datetime objects to ISO format
        for job in aggregated['jobs']:
            if job['start_time']:
                job['start_time'] = job['start_time'].isoformat()
            if job['end_time']:
                job['end_time'] = job['end_time'].isoformat()
            
            for batch in job['batches']:
                if batch['start_time']:
                    batch['start_time'] = batch['start_time'].isoformat()
                if batch['end_time']:
                    batch['end_time'] = batch['end_time'].isoformat()
        
        with open(file_path, 'w') as f:
            json.dump(aggregated, f, indent=2, ensure_ascii=False)
