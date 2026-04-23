import sys
import os
from loguru import logger as _logger

# LOG_DIR = "logs"
# os.makedirs(LOG_DIR, exist_ok=True)

# LOG_FILE = os.path.join(LOG_DIR, "output.log")

# _logger.remove()

# _logger.add(
#     sys.stdout,
#     format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
#     level="INFO"
# )

# _logger.add(
#     LOG_FILE,
#     rotation="10 MB",
#     retention="30 days",
#     compression="zip",
#     encoding="utf-8",
#     level="DEBUG",
#     format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
#     backtrace=True,
# )

# logger = _logger