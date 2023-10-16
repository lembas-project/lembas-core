import logging

from rich.logging import RichHandler

__all__ = ["logger"]

logging.basicConfig(
    level="NOTSET",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(show_level=False, show_path=False, show_time=False)],
)

logger = logging.getLogger("lembas")
