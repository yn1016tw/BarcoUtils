# Author: James Yang <james.yang@barco.com>

import logging
import sys
from pathlib import Path


class Logger:
    """Write timestamped log messages to stdout and {output_dir}/logs.txt simultaneously."""

    def __init__(self, output_dir: str, name: str = "barcoutils"):
        self._logger = logging.getLogger(f"{name}.{id(self)}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%H:%M:%S",
        )

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        self._logger.addHandler(sh)

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(Path(output_dir) / "logs.txt", encoding="utf-8")
        fh.setFormatter(fmt)
        self._logger.addHandler(fh)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)
