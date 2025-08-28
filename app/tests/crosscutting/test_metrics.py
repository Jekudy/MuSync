import pytest
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

from app.crosscutting.metrics import (
    BatchMetrics, JobMetrics, MetricsCollector, MetricsAggregator
)


class TestBatchMetrics:
    """Tests for BatchMetrics class."""

    def test_batch_metrics_creation(self):
        """Test creating batch metrics."""
        start_time = datetime.now()
        batch = BatchMetrics(
            batch_id="batch_1",
            playlist_id="playlist_123",
            track_count=10,
            success_count=8,
            error_count=1,
            not_found_count=1,
            retry_count=2,
            rate_limit_wait_ms=500,
            duration_ms=1000,
            start_time=start_time
        )
        
        assert batch.batch_id == "batch_1"
        assert batch.playlist_id == "playlist_123"
        assert batch.track_count == 10
        assert batch.success_count == 8
        assert batch.error_count == 1
        assert batch.not_found_count == 1
        assert batch.retry_count == 2
        assert batch.rate_limit_wait_ms == 500
        assert batch.duration_ms == 1000
        assert batch.start_time == start_time

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        batch = BatchMetrics(
            batch_id="batch_1",
            playlist_id="playlist_123",
            track_count=10,
            success_count=8,
            error_count=1,
            not_found_count=1,
            retry_count=0,
            rate_limit_wait_ms=0,
            duration_ms=0,
            start_time=datetime.now()
        )
        
        assert batch.success_rate == 0.8  # 8/10 = 0.8

    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        batch = BatchMetrics(
            batch_id="batch_1",
            playlist_id="playlist_123",
            track_count=10,
            success_count=8,
            error_count=1,
            not_found_count=1,
            retry_count=0,
            rate_limit_wait_ms=0,
            duration_ms=0,
            start_time=datetime.now()
        )
        
        assert batch.error_rate == 0.1  # 1/10 = 0.1

    def test_not_found_rate_calculation(self):
        """Test not found rate calculation."""
        batch = BatchMetrics(
            batch_id="batch_1",
            playlist_id="playlist_123",
            track_count=10,
            success_count=8,
            error_count=1,
            not_found_count=1,
            retry_count=0,
            rate_limit_wait_ms=0,
            duration_ms=0,
            start_time=datetime.now()
        )
        
        assert batch.not_found_rate == 0.1  # 1/10 = 0.1

    def test_zero_track_count_rates(self):
        """Test rate calculations with zero track count."""
        batch = BatchMetrics(
            batch_id="batch_1",
            playlist_id="playlist_123",
            track_count=0,
            success_count=0,
            error_count=0,
            not_found_count=0,
            retry_count=0,
            rate_limit_wait_ms=0,
            duration_ms=0,
            start_time=datetime.now()
        )
        
        assert batch.success_rate == 0.0
        assert batch.error_rate == 0.0
        assert batch.not_found_rate == 0.0


class TestJobMetrics:
    """Tests for JobMetrics class."""

    def test_job_metrics_creation(self):
        """Test creating job metrics."""
        start_time = datetime.now()
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=start_time
        )
        
        assert job.job_id == "job_123"
        assert job.snapshot_hash == "hash_456"
        assert job.source_provider == "yandex"
        assert job.target_provider == "spotify"
        assert job.total_playlists == 2
        assert job.total_tracks == 20
        assert job.total_batches == 3
        assert job.total_success_count == 18
        assert job.total_error_count == 1
        assert job.total_not_found_count == 1
        assert job.total_retry_count == 5
        assert job.total_rate_limit_wait_ms == 1000
        assert job.total_duration_ms == 5000
        assert job.start_time == start_time

    def test_overall_success_rate_calculation(self):
        """Test overall success rate calculation."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        assert job.overall_success_rate == 0.9  # 18/20 = 0.9

    def test_overall_error_rate_calculation(self):
        """Test overall error rate calculation."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        assert job.overall_error_rate == 0.05  # 1/20 = 0.05

    def test_overall_not_found_rate_calculation(self):
        """Test overall not found rate calculation."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        assert job.overall_not_found_rate == 0.05  # 1/20 = 0.05

    def test_average_batch_duration_calculation(self):
        """Test average batch duration calculation."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=6000,
            start_time=datetime.now()
        )
        
        assert job.average_batch_duration_ms == 2000.0  # 6000/3 = 2000

    def test_average_retry_count_calculation(self):
        """Test average retry count calculation."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=6,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        assert job.average_retry_count == 2.0  # 6/3 = 2.0

    def test_zero_track_count_rates(self):
        """Test rate calculations with zero track count."""
        job = JobMetrics(
            job_id="job_123",
            snapshot_hash="hash_456",
            source_provider="yandex",
            target_provider="spotify",
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
        
        assert job.overall_success_rate == 0.0
        assert job.overall_error_rate == 0.0
        assert job.overall_not_found_rate == 0.0
        assert job.average_batch_duration_ms == 0.0
        assert job.average_retry_count == 0.0


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.collector = MetricsCollector(
            job_id="test_job",
            snapshot_hash="test_hash",
            source_provider="yandex",
            target_provider="spotify"
        )

    def test_initialization(self):
        """Test metrics collector initialization."""
        assert self.collector.job_id == "test_job"
        assert self.collector.snapshot_hash == "test_hash"
        assert self.collector.source_provider == "yandex"
        assert self.collector.target_provider == "spotify"
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.job_id == "test_job"
        assert job_metrics.snapshot_hash == "test_hash"
        assert job_metrics.source_provider == "yandex"
        assert job_metrics.target_provider == "spotify"

    def test_start_and_end_job(self):
        """Test job start and end tracking."""
        self.collector.start_job()
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.start_time is not None
        
        self.collector.end_job()
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.end_time is not None
        assert job_metrics.total_duration_ms >= 0  # Can be 0 if very fast

    def test_start_playlist(self):
        """Test playlist start tracking."""
        self.collector.start_playlist("playlist_123", 10)
        job_metrics = self.collector.get_job_metrics()
        
        assert job_metrics.total_playlists == 1
        assert job_metrics.total_tracks == 10

    def test_start_and_end_batch(self):
        """Test batch start and end tracking."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        batch_metrics = self.collector.get_batch_metrics()
        
        assert batch_metrics.batch_id == "batch_1"
        assert batch_metrics.playlist_id == "playlist_123"
        assert batch_metrics.track_count == 5
        assert batch_metrics.start_time is not None
        
        self.collector.end_batch()
        job_metrics = self.collector.get_job_metrics()
        
        assert job_metrics.total_batches == 1
        assert len(job_metrics.batches) == 1
        assert job_metrics.batches[0].batch_id == "batch_1"
        assert job_metrics.batches[0].end_time is not None
        assert job_metrics.batches[0].duration_ms >= 0  # Can be 0 if very fast

    def test_record_track_success(self):
        """Test recording track success."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        self.collector.record_track_success()
        self.collector.record_track_success()
        self.collector.end_batch()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_success_count == 2
        assert job_metrics.batches[0].success_count == 2

    def test_record_track_error(self):
        """Test recording track error."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        self.collector.record_track_error()
        self.collector.end_batch()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_error_count == 1
        assert job_metrics.batches[0].error_count == 1

    def test_record_track_not_found(self):
        """Test recording track not found."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        self.collector.record_track_not_found()
        self.collector.end_batch()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_not_found_count == 1
        assert job_metrics.batches[0].not_found_count == 1

    def test_record_retry(self):
        """Test recording retry attempts."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        self.collector.record_retry()
        self.collector.record_retry()
        self.collector.end_batch()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_retry_count == 2
        assert job_metrics.batches[0].retry_count == 2

    def test_record_rate_limit_wait(self):
        """Test recording rate limit wait time."""
        self.collector.start_batch("batch_1", "playlist_123", 5)
        self.collector.record_rate_limit_wait(500)
        self.collector.record_rate_limit_wait(300)
        self.collector.end_batch()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_rate_limit_wait_ms == 800
        assert job_metrics.batches[0].rate_limit_wait_ms == 800

    def test_batch_context_manager(self):
        """Test batch context manager."""
        with self.collector.batch_context("batch_1", "playlist_123", 5) as collector:
            collector.record_track_success()
            collector.record_track_error()
        
        job_metrics = self.collector.get_job_metrics()
        assert job_metrics.total_batches == 1
        assert job_metrics.total_success_count == 1
        assert job_metrics.total_error_count == 1
        assert job_metrics.batches[0].batch_id == "batch_1"

    def test_to_dict_serialization(self):
        """Test metrics serialization to dictionary."""
        self.collector.start_job()
        self.collector.start_playlist("playlist_123", 10)
        
        with self.collector.batch_context("batch_1", "playlist_123", 5) as collector:
            collector.record_track_success()
            collector.record_track_error()
        
        self.collector.end_job()
        
        metrics_dict = self.collector.to_dict()
        
        assert 'job_id' in metrics_dict
        assert 'snapshot_hash' in metrics_dict
        assert 'source_provider' in metrics_dict
        assert 'target_provider' in metrics_dict
        assert 'total_playlists' in metrics_dict
        assert 'total_tracks' in metrics_dict
        assert 'batches' in metrics_dict
        assert len(metrics_dict['batches']) == 1
        assert metrics_dict['batches'][0]['batch_id'] == "batch_1"

    def test_save_to_file(self):
        """Test saving metrics to file."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = os.path.join(self.temp_dir, 'test_metrics.json')
        
        try:
            self.collector.start_job()
            self.collector.start_playlist("playlist_123", 10)
            
            with self.collector.batch_context("batch_1", "playlist_123", 5) as collector:
                collector.record_track_success()
                collector.record_track_error()
            
            self.collector.end_job()
            self.collector.save_to_file(self.metrics_file)
            
            assert os.path.exists(self.metrics_file)
            
            with open(self.metrics_file, 'r') as f:
                data = json.load(f)
            
            assert data['job_id'] == "test_job"
            assert data['total_playlists'] == 1
            assert data['total_tracks'] == 10
            assert len(data['batches']) == 1
            
        finally:
            if os.path.exists(self.metrics_file):
                os.remove(self.metrics_file)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)

    def test_print_summary(self):
        """Test printing metrics summary."""
        self.collector.start_job()
        self.collector.start_playlist("playlist_123", 10)
        
        with self.collector.batch_context("batch_1", "playlist_123", 5) as collector:
            collector.record_track_success()
            collector.record_track_error()
            collector.record_track_not_found()
            collector.record_retry()
            collector.record_rate_limit_wait(500)
        
        self.collector.end_job()
        
        # This should not raise any exceptions
        self.collector.print_summary()


class TestMetricsAggregator:
    """Tests for MetricsAggregator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.aggregator = MetricsAggregator()

    def test_add_job_metrics(self):
        """Test adding job metrics to aggregator."""
        job1 = JobMetrics(
            job_id="job_1",
            snapshot_hash="hash_1",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        job2 = JobMetrics(
            job_id="job_2",
            snapshot_hash="hash_2",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=1,
            total_tracks=10,
            total_batches=2,
            total_success_count=9,
            total_error_count=0,
            total_not_found_count=1,
            total_retry_count=2,
            total_rate_limit_wait_ms=500,
            total_duration_ms=3000,
            start_time=datetime.now()
        )
        
        self.aggregator.add_job_metrics(job1)
        self.aggregator.add_job_metrics(job2)
        
        assert len(self.aggregator.jobs) == 2

    def test_get_aggregated_metrics_empty(self):
        """Test aggregated metrics with no jobs."""
        aggregated = self.aggregator.get_aggregated_metrics()
        assert aggregated == {}

    def test_get_aggregated_metrics_with_jobs(self):
        """Test aggregated metrics with jobs."""
        job1 = JobMetrics(
            job_id="job_1",
            snapshot_hash="hash_1",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=2,
            total_tracks=20,
            total_batches=3,
            total_success_count=18,
            total_error_count=1,
            total_not_found_count=1,
            total_retry_count=5,
            total_rate_limit_wait_ms=1000,
            total_duration_ms=5000,
            start_time=datetime.now()
        )
        
        job2 = JobMetrics(
            job_id="job_2",
            snapshot_hash="hash_2",
            source_provider="yandex",
            target_provider="spotify",
            total_playlists=1,
            total_tracks=10,
            total_batches=2,
            total_success_count=9,
            total_error_count=0,
            total_not_found_count=1,
            total_retry_count=2,
            total_rate_limit_wait_ms=500,
            total_duration_ms=3000,
            start_time=datetime.now()
        )
        
        self.aggregator.add_job_metrics(job1)
        self.aggregator.add_job_metrics(job2)
        
        aggregated = self.aggregator.get_aggregated_metrics()
        
        assert 'summary' in aggregated
        assert 'jobs' in aggregated
        assert aggregated['summary']['total_jobs'] == 2
        assert aggregated['summary']['total_playlists'] == 3
        assert aggregated['summary']['total_tracks'] == 30
        assert aggregated['summary']['overall_success_rate'] == 0.9  # 27/30
        assert abs(aggregated['summary']['overall_error_rate'] - 0.033) < 0.001  # 1/30 ≈ 0.033
        assert abs(aggregated['summary']['overall_not_found_rate'] - 0.067) < 0.001  # 2/30 ≈ 0.067
        assert aggregated['summary']['total_retries'] == 7
        assert aggregated['summary']['total_duration_ms'] == 8000
        assert aggregated['summary']['total_rate_limit_wait_ms'] == 1500
        assert aggregated['summary']['average_duration_per_job_ms'] == 4000.0
        assert aggregated['summary']['average_tracks_per_job'] == 15.0
        assert len(aggregated['jobs']) == 2

    def test_save_aggregated_metrics(self):
        """Test saving aggregated metrics to file."""
        self.temp_dir = tempfile.mkdtemp()
        self.aggregated_file = os.path.join(self.temp_dir, 'aggregated_metrics.json')
        
        try:
            job = JobMetrics(
                job_id="job_1",
                snapshot_hash="hash_1",
                source_provider="yandex",
                target_provider="spotify",
                total_playlists=2,
                total_tracks=20,
                total_batches=3,
                total_success_count=18,
                total_error_count=1,
                total_not_found_count=1,
                total_retry_count=5,
                total_rate_limit_wait_ms=1000,
                total_duration_ms=5000,
                start_time=datetime.now()
            )
            
            self.aggregator.add_job_metrics(job)
            self.aggregator.save_aggregated_metrics(self.aggregated_file)
            
            assert os.path.exists(self.aggregated_file)
            
            with open(self.aggregated_file, 'r') as f:
                data = json.load(f)
            
            assert 'summary' in data
            assert 'jobs' in data
            assert data['summary']['total_jobs'] == 1
            assert len(data['jobs']) == 1
            
        finally:
            if os.path.exists(self.aggregated_file):
                os.remove(self.aggregated_file)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
