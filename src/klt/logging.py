import logging
import sys
from pathlib import Path
from typing import Any

import requests
from loguru import logger

from .settings import LoggingSettings

logger.remove()


class InterceptHandler(logging.Handler):
    @logger.catch(default=True, onerror=lambda _: sys.exit(1))
    def emit(self, record: logging.LogRecord) -> None:
        # Get the corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the caller from where the logged message originated.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logger_http = logger.bind(scope="http")
logger_dlt = logging.getLogger("dlt")
logger_dlt.addHandler(InterceptHandler())


def http_log(response: requests.Response, *args: Any, **kwargs: Any) -> requests.Response:
    logger_http.debug(
        f"{response.request.method} on {response.url} with status code {response.status_code}"
    )
    return response


logging_settings = LoggingSettings()
log_dir = Path(logging_settings.log_dir)
# TODO: Discuss the automated creation of the directory silently
log_dir.mkdir(parents=True, exist_ok=True)

logger.add(
    log_dir / "dlt.log", filter=lambda record: record["extra"].get("scope") != "http"
)
logger.add(
    log_dir / "dlt_http.log",
    filter=lambda record: record["extra"].get("scope") == "http",
)
