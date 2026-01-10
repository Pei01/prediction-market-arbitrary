import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.config import settings

# 建立存 logs 的資料夾
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def setup_logger(name: str = None, log_file: str = "app.log", level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    file_handler = RotatingFileHandler(
        LOG_DIR / log_file,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )

    file_handler.setFormatter(FORMATTER)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
