import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextvars import ContextVar
import threading

# Context variables for correlation
job_id_var: ContextVar[Optional[str]] = ContextVar('job_id', default=None)
snapshot_hash_var: ContextVar[Optional[str]] = ContextVar('snapshot_hash', default=None)
playlist_id_var: ContextVar[Optional[str]] = ContextVar('playlist_id', default=None)
stage_var: ContextVar[Optional[str]] = ContextVar('stage', default=None)


class SecretMasker:
    """Masks sensitive information in log messages."""
    
    def __init__(self):
        """Initialize secret masker with patterns."""
        # Patterns for sensitive data
        self.patterns = [
            # API tokens and keys
            r'(?i)(token|key|secret|password|auth)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{10,})["\']?',
            # Spotify access tokens
            r'(?i)(spotify_access_token|access_token)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{50,})["\']?',
            # Yandex tokens
            r'(?i)(yandex_token|yandex_access_token)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{20,})["\']?',
            # Client secrets
            r'(?i)(client_secret)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{20,})["\']?',
            # Authorization headers
            r'(?i)(authorization|bearer)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{50,})["\']?',
            # OAuth codes
            r'(?i)(code|authorization_code)[\s]*[:=][\s]*["\']?([a-zA-Z0-9\-_\.]{20,})["\']?',
        ]
        
        self.compiled_patterns = [re.compile(pattern) for pattern in self.patterns]
    
    def mask_secrets(self, text: str) -> str:
        """Mask sensitive information in text."""
        if not text:
            return text
        
        masked_text = text
        
        for pattern in self.compiled_patterns:
            def replace_match(match):
                prefix = match.group(1)
                secret = match.group(2)
                # Keep first 4 and last 4 characters, mask the rest
                if len(secret) > 8:
                    masked_secret = secret[:4] + '*' * (len(secret) - 8) + secret[-4:]
                else:
                    masked_secret = '*' * len(secret)
                return f"{prefix}: {masked_secret}"
            
            masked_text = pattern.sub(replace_match, masked_text)
        
        return masked_text
    
    def mask_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive information in dictionary."""
        if not data:
            return data
        
        masked_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                masked_data[key] = self.mask_secrets(value)
            elif isinstance(value, dict):
                masked_data[key] = self.mask_dict(value)
            elif isinstance(value, list):
                masked_data[key] = [self.mask_dict(item) if isinstance(item, dict) 
                                  else self.mask_secrets(item) if isinstance(item, str)
                                  else item for item in value]
            else:
                masked_data[key] = value
        
        return masked_data


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self):
        """Initialize formatter."""
        super().__init__()
        self.masker = SecretMasker()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get correlation data from context
        job_id = job_id_var.get()
        snapshot_hash = snapshot_hash_var.get()
        playlist_id = playlist_id_var.get()
        stage = stage_var.get()
        
        # Build log entry
        log_entry = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': self.mask_secrets(record.getMessage()),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add correlation fields if available
        if job_id:
            log_entry['jobId'] = job_id
        if snapshot_hash:
            log_entry['snapshotHash'] = snapshot_hash
        if playlist_id:
            log_entry['playlistId'] = playlist_id
        if stage:
            log_entry['stage'] = stage
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'fields') and record.fields:
            log_entry['fields'] = self.masker.mask_dict(record.fields)
        
        return json.dumps(log_entry, ensure_ascii=False)
    
    def mask_secrets(self, text: str) -> str:
        """Mask secrets in text."""
        return self.masker.mask_secrets(text)


class CorrelationContext:
    """Context manager for correlation data."""
    
    def __init__(self, job_id: Optional[str] = None, 
                 snapshot_hash: Optional[str] = None,
                 playlist_id: Optional[str] = None,
                 stage: Optional[str] = None):
        """Initialize correlation context."""
        self.job_id = job_id
        self.snapshot_hash = snapshot_hash
        self.playlist_id = playlist_id
        self.stage = stage
        self._old_values = {}
    
    def __enter__(self):
        """Set correlation context."""
        if self.job_id is not None:
            self._old_values['job_id'] = job_id_var.get()
            job_id_var.set(self.job_id)
        
        if self.snapshot_hash is not None:
            self._old_values['snapshot_hash'] = snapshot_hash_var.get()
            snapshot_hash_var.set(self.snapshot_hash)
        
        if self.playlist_id is not None:
            self._old_values['playlist_id'] = playlist_id_var.get()
            playlist_id_var.set(self.playlist_id)
        
        if self.stage is not None:
            self._old_values['stage'] = stage_var.get()
            stage_var.set(self.stage)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore correlation context."""
        if 'job_id' in self._old_values:
            job_id_var.set(self._old_values['job_id'])
        if 'snapshot_hash' in self._old_values:
            snapshot_hash_var.set(self._old_values['snapshot_hash'])
        if 'playlist_id' in self._old_values:
            playlist_id_var.set(self._old_values['playlist_id'])
        if 'stage' in self._old_values:
            stage_var.set(self._old_values['stage'])


def setup_logging(level: str = 'INFO', 
                 log_file: Optional[str] = None,
                 job_id: Optional[str] = None,
                 snapshot_hash: Optional[str] = None) -> logging.Logger:
    """Setup structured logging."""
    # Create logger
    logger = logging.getLogger('musync')
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Set correlation context if provided
    if job_id:
        job_id_var.set(job_id)
    if snapshot_hash:
        snapshot_hash_var.set(snapshot_hash)
    
    return logger


def get_logger(name: str = 'musync') -> logging.Logger:
    """Get logger with structured formatting."""
    return logging.getLogger(name)


def log_with_fields(logger: logging.Logger, level: str, message: str, 
                   fields: Optional[Dict[str, Any]] = None, **kwargs):
    """Log message with additional fields."""
    # Create a custom log record with fields
    record = logger.makeRecord(
        logger.name, getattr(logging, level.upper()), 
        '', 0, message, (), None
    )
    
    # Add fields to record
    if fields:
        record.fields = fields
    if kwargs:
        if not hasattr(record, 'fields'):
            record.fields = {}
        record.fields.update(kwargs)
    
    # Log the record
    logger.handle(record)


# Convenience functions for common logging patterns
def log_job_start(logger: logging.Logger, job_id: str, snapshot_hash: str, 
                  source_provider: str, target_provider: str, **kwargs):
    """Log job start."""
    with CorrelationContext(job_id=job_id, snapshot_hash=snapshot_hash, stage='start'):
        log_with_fields(logger, 'INFO', 'Job started', {
            'source_provider': source_provider,
            'target_provider': target_provider,
            **kwargs
        })


def log_playlist_start(logger: logging.Logger, playlist_id: str, track_count: int, **kwargs):
    """Log playlist processing start."""
    with CorrelationContext(playlist_id=playlist_id, stage='playlist_start'):
        log_with_fields(logger, 'INFO', 'Playlist processing started', {
            'track_count': track_count,
            **kwargs
        })


def log_playlist_complete(logger: logging.Logger, playlist_id: str, 
                         success_count: int, error_count: int, **kwargs):
    """Log playlist processing completion."""
    with CorrelationContext(playlist_id=playlist_id, stage='playlist_complete'):
        log_with_fields(logger, 'INFO', 'Playlist processing completed', {
            'success_count': success_count,
            'error_count': error_count,
            **kwargs
        })


def log_job_complete(logger: logging.Logger, job_id: str, 
                    total_playlists: int, total_tracks: int, **kwargs):
    """Log job completion."""
    with CorrelationContext(job_id=job_id, stage='complete'):
        log_with_fields(logger, 'INFO', 'Job completed', {
            'total_playlists': total_playlists,
            'total_tracks': total_tracks,
            **kwargs
        })


def log_error(logger: logging.Logger, message: str, error: Exception, **kwargs):
    """Log error with exception details."""
    log_with_fields(logger, 'ERROR', message, {
        'error_type': type(error).__name__,
        'error_message': str(error),
        **kwargs
    }, exc_info=True)
