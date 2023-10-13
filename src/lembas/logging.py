import logging

from rich.logging import RichHandler

__all__ = ["logger"]

FORMAT = "%(message)s"
logger = logging.getLogger(__name__)

logging.basicConfig(
    level="NOTSET",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(show_level=False, show_path=False, show_time=False)],
)
