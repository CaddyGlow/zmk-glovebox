"""Metrics storage implementation using cache backend."""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from glovebox.core.cache_v2 import create_default_cache
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.logging import get_logger
from glovebox.metrics.models import (
    FirmwareMetrics,
    FlashMetrics,
    LayoutMetrics,
    OperationMetrics,
    OperationType,
)
from glovebox.metrics.protocols import MetricsStorageProtocol


class MetricsStorage:
    """Storage adapter for metrics using cache backend."""

    def __init__(self, cache_manager: CacheManager) -> None:
        """Initialize metrics storage with cache manager.

        Args:
            cache_manager: Cache manager instance for storage
        """
        self.cache = cache_manager
        self.logger = get_logger(__name__)

        # Cache keys
        self._operations_key = "metrics:operations"
        self._operations_index_key = "metrics:operations:index"

        # TTL for metrics data (30 days)
        self._metrics_ttl = 30 * 24 * 60 * 60

    def _deserialize_operation_metrics(
        self, operation_data: dict[str, Any]
    ) -> OperationMetrics:
        """Deserialize operation data to the appropriate metrics model type."""
        # Compute duration if not already set and we have start/end times
        if operation_data.get("duration_seconds") is None:
            start_time_str = operation_data.get("start_time")
            end_time_str = operation_data.get("end_time")

            if start_time_str and end_time_str:
                try:
                    start_time = datetime.fromisoformat(
                        start_time_str.replace("Z", "+00:00")
                    )
                    end_time = datetime.fromisoformat(
                        end_time_str.replace("Z", "+00:00")
                    )
                    operation_data["duration_seconds"] = (
                        end_time - start_time
                    ).total_seconds()
                except (ValueError, AttributeError) as e:
                    self.logger.debug(
                        "Failed to compute duration from timestamps: %s", e
                    )

        operation_type = operation_data.get("operation_type")

        # Use specific model class based on operation type
        if (
            operation_type == OperationType.LAYOUT_COMPILATION
            or operation_type == "layout_compilation"
        ):
            return LayoutMetrics.model_validate(operation_data)
        elif (
            operation_type == OperationType.FIRMWARE_COMPILATION
            or operation_type == "firmware_compilation"
        ):
            return FirmwareMetrics.model_validate(operation_data)
        elif (
            operation_type == OperationType.FIRMWARE_FLASH
            or operation_type == "firmware_flash"
        ):
            return FlashMetrics.model_validate(operation_data)
        else:
            # Fallback to base model
            return OperationMetrics.model_validate(operation_data)

    def store_operation_metrics(self, metrics: OperationMetrics) -> None:
        """Store operation metrics data.

        Args:
            metrics: Operation metrics to store
        """
        try:
            # Store individual operation with unique key
            operation_key = f"{self._operations_key}:{metrics.operation_id}"
            self.cache.set(operation_key, metrics.to_dict(), ttl=self._metrics_ttl)

            # Update operations index
            self._add_to_operations_index(metrics.operation_id, metrics)

            self.logger.debug("Stored metrics for operation %s", metrics.operation_id)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to store operation metrics: %s", e, exc_info=exc_info
            )

    def get_operation_metrics(
        self,
        operation_id: str | None = None,
        operation_type: OperationType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[OperationMetrics]:
        """Retrieve operation metrics with optional filtering.

        Args:
            operation_id: Filter by specific operation ID
            operation_type: Filter by operation type
            start_time: Filter operations after this time
            end_time: Filter operations before this time
            limit: Maximum number of records to return

        Returns:
            List of matching operation metrics
        """
        try:
            if operation_id:
                # Get specific operation
                operation_key = f"{self._operations_key}:{operation_id}"
                operation_data = self.cache.get(operation_key)
                if operation_data:
                    return [self._deserialize_operation_metrics(operation_data)]
                return []

            # Get operations from index
            operations_index = self._get_operations_index()
            if not operations_index:
                return []

            # Apply filters
            filtered_operations = []
            for op_id, op_info in operations_index.items():
                # Check operation type filter
                if operation_type and op_info.get("operation_type") != operation_type:
                    continue

                # Check time filters
                op_start_time = op_info.get("start_time")
                if op_start_time:
                    if isinstance(op_start_time, str):
                        op_start_time = datetime.fromisoformat(
                            op_start_time.replace("Z", "+00:00")
                        )

                    if start_time and op_start_time < start_time:
                        continue
                    if end_time and op_start_time > end_time:
                        continue

                # Load full operation data
                operation_key = f"{self._operations_key}:{op_id}"
                operation_data = self.cache.get(operation_key)
                if operation_data:
                    try:
                        operation = self._deserialize_operation_metrics(operation_data)
                        filtered_operations.append(operation)
                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse operation %s: %s", op_id, e
                        )
                        continue

            # Sort by start time (most recent first)
            filtered_operations.sort(
                key=lambda x: x.start_time if x.start_time else datetime.min,
                reverse=True,
            )

            # Apply limit
            if limit and len(filtered_operations) > limit:
                filtered_operations = filtered_operations[:limit]

            return filtered_operations

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to retrieve operation metrics: %s", e, exc_info=exc_info
            )
            return []

    def delete_operation_metrics(
        self,
        operation_id: str | None = None,
        before_time: datetime | None = None,
    ) -> int:
        """Delete operation metrics.

        Args:
            operation_id: Delete specific operation by ID
            before_time: Delete all operations before this time

        Returns:
            Number of records deleted
        """
        try:
            deleted_count = 0

            if operation_id:
                # Delete specific operation
                operation_key = f"{self._operations_key}:{operation_id}"
                if self.cache.delete(operation_key):
                    deleted_count = 1
                    self._remove_from_operations_index(operation_id)
            else:
                # Delete operations before specified time
                operations_index = self._get_operations_index()
                if operations_index and before_time:
                    operations_to_delete = []

                    for op_id, op_info in operations_index.items():
                        op_start_time = op_info.get("start_time")
                        if op_start_time:
                            if isinstance(op_start_time, str):
                                op_start_time = datetime.fromisoformat(
                                    op_start_time.replace("Z", "+00:00")
                                )

                            if op_start_time < before_time:
                                operations_to_delete.append(op_id)

                    for op_id in operations_to_delete:
                        operation_key = f"{self._operations_key}:{op_id}"
                        if self.cache.delete(operation_key):
                            deleted_count += 1
                            self._remove_from_operations_index(op_id)

            if deleted_count > 0:
                self.logger.info("Deleted %d operation metrics", deleted_count)

            return deleted_count

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to delete operation metrics: %s", e, exc_info=exc_info
            )
            return 0

    def get_metrics_count(self) -> int:
        """Get total count of stored metrics.

        Returns:
            Total number of metrics records
        """
        try:
            operations_index = self._get_operations_index()
            return len(operations_index) if operations_index else 0
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to get metrics count: %s", e, exc_info=exc_info)
            return 0

    def clear_all_metrics(self) -> int:
        """Clear all stored metrics.

        Returns:
            Number of records deleted
        """
        try:
            operations_index = self._get_operations_index()
            if not operations_index:
                return 0

            deleted_count = 0
            for op_id in operations_index:
                operation_key = f"{self._operations_key}:{op_id}"
                if self.cache.delete(operation_key):
                    deleted_count += 1

            # Clear the index
            self.cache.delete(self._operations_index_key)

            if deleted_count > 0:
                self.logger.info(
                    "Cleared all metrics: %d records deleted", deleted_count
                )

            return deleted_count

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to clear all metrics: %s", e, exc_info=exc_info)
            return 0

    def _get_operations_index(self) -> dict[str, dict[str, Any]]:
        """Get the operations index from cache.

        Returns:
            Dictionary mapping operation IDs to operation metadata
        """
        index_data = self.cache.get(self._operations_index_key, {})
        if isinstance(index_data, str):
            try:
                parsed_data = json.loads(index_data)
                return parsed_data if isinstance(parsed_data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return index_data if isinstance(index_data, dict) else {}

    def _add_to_operations_index(
        self, operation_id: str, metrics: OperationMetrics
    ) -> None:
        """Add operation to the operations index.

        Args:
            operation_id: Operation ID to add
            metrics: Operation metrics for indexing
        """
        operations_index = self._get_operations_index()

        # Store minimal metadata for filtering
        operations_index[operation_id] = {
            "operation_type": metrics.operation_type,
            "start_time": metrics.start_time.isoformat()
            if metrics.start_time
            else None,
            "status": metrics.status,
            "profile_name": metrics.profile_name,
            "keyboard_name": metrics.keyboard_name,
        }

        # Save updated index
        self.cache.set(
            self._operations_index_key, operations_index, ttl=self._metrics_ttl
        )

    def _remove_from_operations_index(self, operation_id: str) -> None:
        """Remove operation from the operations index.

        Args:
            operation_id: Operation ID to remove
        """
        operations_index = self._get_operations_index()
        if operation_id in operations_index:
            del operations_index[operation_id]
            self.cache.set(
                self._operations_index_key, operations_index, ttl=self._metrics_ttl
            )


def create_metrics_storage(
    cache: CacheManager | None = None,
) -> MetricsStorageProtocol:
    """Create metrics storage with optional cache backend dependency injection.

    Args:
        cache: Optional cache manager instance. If None, creates default cache.

    Returns:
        MetricsStorageProtocol: Configured metrics storage
    """
    if cache is None:
        cache = create_default_cache(tag="metrics")
    return MetricsStorage(cache)
