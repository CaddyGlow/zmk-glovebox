"""Enums for file operations."""

from enum import Enum


class CopyStrategy(Enum):
    """Available file copy strategies."""

    BASELINE = "baseline"
    BUFFERED = "buffered"
    SENDFILE = "sendfile"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
