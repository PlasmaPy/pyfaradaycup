"""Paths to files distributed with pyfaradaycup."""

__all__ = ["data_dir"]

import pathlib

#: The package data directory, ``src/pyfaradaycup/data/``.
data_dir = pathlib.Path(__file__).parent / "data"
