import logging
import sys
from typing import ClassVar


def hex_to_ansi(hex_color: str) -> str:
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"\x1b[38;2;{r};{g};{b}m"


NAME_COLOR = hex_to_ansi("404bbd")


class _ColourFormatter(logging.Formatter):  # stolen from discord.py LMAO
    LEVEL_COLOURS: ClassVar = [
        (logging.DEBUG, "\x1b[40;1m"),
        (logging.INFO, hex_to_ansi("5865F2")),
        # (logging.INFO, "\x1b[34;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]

    FORMATS: ClassVar = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m {NAME_COLOR}%(name)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, colour in LEVEL_COLOURS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output


def create_logger(name: str, suffix: str = ""):
    logger = logging.getLogger(f"{name} [{suffix}]" if suffix else name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_ColourFormatter())

        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG)
    return logger