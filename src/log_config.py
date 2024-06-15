import logging
import threading

#-------------------------Setup logging-------------------------
class ThreadInfoFilter(logging.Filter):
    """
    Log filter to add thread information to log records.
    """
    def filter(self, record):
        record.translation_thread_name = threading.current_thread().name
        parts = record.translation_thread_name.split(' ')
        if len(parts) == 4:
            record.project = parts[1]
            record.component = parts[2]
            record.language = parts[3]
            
        return True

# Define your logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'threadInfoFilter': {
            '()': ThreadInfoFilter,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'stream': 'ext://sys.stdout',
            'filters': ['threadInfoFilter'],
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}