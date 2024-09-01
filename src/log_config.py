import logging
import threading

#-------------------------Setup logging-------------------------
class ThreadInfoFilter(logging.Filter):
    """
    Log filter to add thread information to log records.
    """
    def filter(self, record):
        thread_name = threading.current_thread().name
        record.translation_thread_name = thread_name
        parts = thread_name.split(' ')
        if len(parts) == 4:
            record.project, record.component, record.language = parts[1:]
        return True

# Define your logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(translation_thread_name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'filters': {
        'threadInfoFilter': {
            '()': ThreadInfoFilter,
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        'level': 'INFO',
            'formatter': 'detailed',
            'filters': ['threadInfoFilter'],
    },
    'file': {
            'class': 'logging.FileHandler',
            'filename': 'translation.log',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filters': ['threadInfoFilter'],
}
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'file'],
    },
}
