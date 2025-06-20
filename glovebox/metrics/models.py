"""Metrics models for tracking application performance and usage."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from glovebox.models.base import GloveboxBaseModel


class OperationStatus(str, Enum):
    """Status of an operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class OperationType(str, Enum):
    """Type of operation being tracked."""

    LAYOUT_COMPILATION = "layout_compilation"
    FIRMWARE_COMPILATION = "firmware_compilation"
    FIRMWARE_FLASH = "firmware_flash"
    LAYOUT_VALIDATION = "layout_validation"
    LAYOUT_GENERATION = "layout_generation"


class ErrorCategory(str, Enum):
    """Categories of errors for classification."""

    VALIDATION_ERROR = "validation_error"
    COMPILATION_ERROR = "compilation_error"
    DOCKER_ERROR = "docker_error"
    FILE_ERROR = "file_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class OperationMetrics(GloveboxBaseModel):
    """Base model for tracking operation metrics."""

    operation_id: str = Field(description="Unique identifier for the operation")
    operation_type: OperationType = Field(description="Type of operation")
    status: OperationStatus = Field(description="Final status of the operation")

    # Timing information
    start_time: datetime = Field(description="When the operation started")
    end_time: datetime | None = Field(
        default=None, description="When the operation completed"
    )
    duration_seconds: float | None = Field(
        default=None, description="Total duration in seconds"
    )

    # Context information
    profile_name: str | None = Field(
        default=None, description="Profile used for operation"
    )
    keyboard_name: str | None = Field(default=None, description="Keyboard name")
    firmware_version: str | None = Field(default=None, description="Firmware version")

    # Error information
    error_message: str | None = Field(
        default=None, description="Error message if operation failed"
    )
    error_category: ErrorCategory | None = Field(
        default=None, description="Category of error"
    )
    error_details: dict[str, Any] | None = Field(
        default=None, description="Additional error context"
    )

    # Cache information
    cache_hit: bool | None = Field(
        default=None, description="Whether operation used cached results"
    )
    cache_key: str | None = Field(default=None, description="Cache key used")

    @model_validator(mode="after")
    def compute_duration(self) -> "OperationMetrics":
        """Compute duration from start/end times if not provided."""
        if self.duration_seconds is None and self.start_time and self.end_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        return self


class LayoutMetrics(OperationMetrics):
    """Metrics specific to layout operations."""

    operation_type: OperationType = Field(default=OperationType.LAYOUT_COMPILATION)

    # Layout-specific information
    input_file: Path | None = Field(default=None, description="Input layout file path")
    output_directory: Path | None = Field(
        default=None, description="Output directory path"
    )
    layer_count: int | None = Field(
        default=None, description="Number of layers in layout"
    )
    binding_count: int | None = Field(
        default=None, description="Total number of key bindings"
    )
    behavior_count: int | None = Field(
        default=None, description="Number of unique behaviors"
    )

    # Generation timing
    parsing_time_seconds: float | None = Field(
        default=None, description="Time spent parsing layout"
    )
    validation_time_seconds: float | None = Field(
        default=None, description="Time spent validating"
    )
    generation_time_seconds: float | None = Field(
        default=None, description="Time spent generating output"
    )


class FirmwareMetrics(OperationMetrics):
    """Metrics specific to firmware compilation operations."""

    operation_type: OperationType = Field(default=OperationType.FIRMWARE_COMPILATION)

    # Compilation-specific information
    compilation_strategy: str | None = Field(
        default=None, description="Compilation strategy used"
    )
    board_targets: list[str] | None = Field(
        default=None, description="Board targets compiled"
    )
    docker_image: str | None = Field(default=None, description="Docker image used")
    workspace_path: Path | None = Field(
        default=None, description="Workspace directory used"
    )

    # Build timing
    setup_time_seconds: float | None = Field(
        default=None, description="Time spent setting up build"
    )
    build_time_seconds: float | None = Field(
        default=None, description="Time spent building firmware"
    )
    artifact_collection_time_seconds: float | None = Field(
        default=None, description="Time collecting artifacts"
    )

    # Build results
    artifacts_generated: int | None = Field(
        default=None, description="Number of artifacts generated"
    )
    firmware_size_bytes: int | None = Field(
        default=None, description="Total size of firmware files"
    )


class FlashMetrics(OperationMetrics):
    """Metrics specific to firmware flashing operations."""

    operation_type: OperationType = Field(default=OperationType.FIRMWARE_FLASH)

    # Flash-specific information
    device_path: str | None = Field(
        default=None, description="Device path used for flashing"
    )
    device_vendor_id: str | None = Field(default=None, description="USB vendor ID")
    device_product_id: str | None = Field(default=None, description="USB product ID")
    firmware_file: Path | None = Field(
        default=None, description="Firmware file flashed"
    )
    firmware_size_bytes: int | None = Field(
        default=None, description="Size of firmware file"
    )

    # Flash timing
    device_detection_time_seconds: float | None = Field(
        default=None, description="Time to detect device"
    )
    flash_time_seconds: float | None = Field(
        default=None, description="Time to flash firmware"
    )
    verification_time_seconds: float | None = Field(
        default=None, description="Time to verify flash"
    )


class MetricsSummary(GloveboxBaseModel):
    """Summary statistics for a collection of metrics."""

    # Time range
    start_time: datetime = Field(description="Start of time range")
    end_time: datetime = Field(description="End of time range")

    # Operation counts
    total_operations: int = Field(description="Total number of operations")
    successful_operations: int = Field(description="Number of successful operations")
    failed_operations: int = Field(description="Number of failed operations")

    # Success rates by operation type
    layout_success_rate: float | None = Field(
        default=None, description="Layout operation success rate"
    )
    firmware_success_rate: float | None = Field(
        default=None, description="Firmware operation success rate"
    )
    flash_success_rate: float | None = Field(
        default=None, description="Flash operation success rate"
    )

    # Performance statistics
    average_duration_seconds: float | None = Field(
        default=None, description="Average operation duration"
    )
    median_duration_seconds: float | None = Field(
        default=None, description="Median operation duration"
    )
    fastest_operation_seconds: float | None = Field(
        default=None, description="Fastest operation duration"
    )
    slowest_operation_seconds: float | None = Field(
        default=None, description="Slowest operation duration"
    )

    # Cache statistics
    cache_hit_rate: float | None = Field(
        default=None, description="Overall cache hit rate"
    )
    cache_enabled_operations: int | None = Field(
        default=None, description="Operations with caching enabled"
    )

    # Error analysis
    error_breakdown: dict[ErrorCategory, int] = Field(
        default_factory=dict, description="Error count by category"
    )
    most_common_error: ErrorCategory | None = Field(
        default=None, description="Most frequent error category"
    )


class MetricsSnapshot(GloveboxBaseModel):
    """Complete snapshot of metrics data for export/reporting."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="When snapshot was created"
    )
    glovebox_version: str | None = Field(default=None, description="Glovebox version")

    # Raw metrics data
    operations: list[OperationMetrics] = Field(
        default_factory=list, description="All operation metrics"
    )

    # Summary statistics
    summary: MetricsSummary | None = Field(
        default=None, description="Aggregated summary statistics"
    )

    # Metadata
    total_operations: int = Field(
        default=0, description="Total number of operations tracked"
    )
    date_range_start: datetime | None = Field(
        default=None, description="Earliest operation timestamp"
    )
    date_range_end: datetime | None = Field(
        default=None, description="Latest operation timestamp"
    )
