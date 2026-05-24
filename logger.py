import logging
import sys
import structlog
from config import settings

def setup_logger():
    """
    Configures structured logging for the application.
    Uses JSON format in production for log aggregators (e.g., Datadog, ELK).
    Uses human-readable ConsoleRenderer in development.
    """
    log_level = logging.getLevelName(settings.LOG_LEVEL.upper())
    
    # Base logging config to intercept anything using standard library `logging`
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    if settings.is_production:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create root application logger
    log = structlog.get_logger("ai_media_os")
    log = log.bind(env=settings.ENVIRONMENT)
    return log

logger = setup_logger()
