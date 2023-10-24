import logging
import os

from rich.logging import RichHandler

__all__ = ["logger"]

LOG_LEVEL = os.getenv("LEMBAS_LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(show_level=False, show_path=False, show_time=False)],
)

logger = logging.getLogger("lembas")
