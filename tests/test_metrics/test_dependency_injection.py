"""Tests for dependency injection in metrics system."""

from unittest.mock import Mock

import pytest

from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.metrics import (
    create_metrics_collector,
    create_metrics_service,
    create_metrics_storage,
)
from glovebox.metrics.models import OperationType
from glovebox.metrics.protocols import MetricsServiceProtocol, MetricsStorageProtocol


class TestMetricsDependencyInjection:
    """Test dependency injection functionality in metrics system."""

    def test_create_metrics_storage_with_injected_cache(self):
        """Test creating metrics storage with injected cache."""
        mock_cache = Mock(spec=CacheManager)

        storage = create_metrics_storage(cache=mock_cache)

        assert storage is not None
        assert storage.cache is mock_cache

    def test_create_metrics_storage_with_default_cache(self):
        """Test creating metrics storage with default cache."""
        storage = create_metrics_storage()

        assert storage is not None
        assert storage.cache is not None
        # Should create its own cache instance

    def test_create_metrics_service_with_injected_storage(self):
        """Test creating metrics service with injected storage."""
        mock_storage = Mock(spec=MetricsStorageProtocol)

        service = create_metrics_service(storage=mock_storage)

        assert service is not None
        assert service.storage is mock_storage

    def test_create_metrics_service_with_default_storage(self):
        """Test creating metrics service with default storage."""
        service = create_metrics_service()

        assert service is not None
        assert service.storage is not None
        # Should create its own storage instance

    def test_create_metrics_collector_with_injected_service(self):
        """Test creating metrics collector with injected service."""
        mock_service = Mock(spec=MetricsServiceProtocol)

        collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            metrics_service=mock_service,
        )

        assert collector is not None
        assert collector.metrics_service is mock_service
        assert collector.operation_type == OperationType.LAYOUT_COMPILATION

    def test_create_metrics_collector_with_default_service(self):
        """Test creating metrics collector with default service."""
        collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION
        )

        assert collector is not None
        assert collector.metrics_service is not None
        assert collector.operation_type == OperationType.LAYOUT_COMPILATION

    def test_full_dependency_injection_chain(self):
        """Test injecting dependencies through the entire chain."""
        # Create mock cache
        mock_cache = Mock(spec=CacheManager)

        # Create storage with injected cache
        storage = create_metrics_storage(cache=mock_cache)

        # Create service with injected storage
        service = create_metrics_service(storage=storage)

        # Create collector with injected service
        collector = create_metrics_collector(
            operation_type=OperationType.FIRMWARE_COMPILATION,
            operation_id="test-operation",
            metrics_service=service,
        )

        # Verify the entire chain is connected
        assert collector.metrics_service is service
        assert service.storage is storage
        assert storage.cache is mock_cache
        assert collector.operation_id == "test-operation"

    def test_mixed_dependency_injection(self):
        """Test partial dependency injection with some defaults."""
        # Inject only storage, let service create its own dependencies
        mock_storage = Mock(spec=MetricsStorageProtocol)
        service = create_metrics_service(storage=mock_storage)

        # Use service to create collector, but let collector use default for operation_id
        collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION, metrics_service=service
        )

        assert collector.metrics_service is service
        assert service.storage is mock_storage
        assert collector.operation_id is not None  # Auto-generated

    def test_dependency_injection_independence(self):
        """Test that different instances with dependency injection are independent."""
        # Create two separate caches
        mock_cache1 = Mock(spec=CacheManager)
        mock_cache2 = Mock(spec=CacheManager)

        # Create two storage instances with different caches
        storage1 = create_metrics_storage(cache=mock_cache1)
        storage2 = create_metrics_storage(cache=mock_cache2)

        # Create two service instances with different storages
        service1 = create_metrics_service(storage=storage1)
        service2 = create_metrics_service(storage=storage2)

        # Verify independence
        assert service1 is not service2
        assert service1.storage is not service2.storage
        assert storage1.cache is not storage2.cache
        assert storage1.cache is mock_cache1
        assert storage2.cache is mock_cache2

    def test_default_vs_injected_behavior_equivalence(self):
        """Test that default creation and injection produce equivalent behavior."""
        # Create with defaults
        default_storage = create_metrics_storage()
        default_service = create_metrics_service()
        default_collector = create_metrics_collector(OperationType.LAYOUT_COMPILATION)

        # Create with explicit injection of new instances
        injected_storage = create_metrics_storage()
        injected_service = create_metrics_service(storage=injected_storage)
        injected_collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            metrics_service=injected_service,
        )

        # Both should have the same types and structure
        assert isinstance(default_storage, type(injected_storage))
        assert isinstance(default_service, type(injected_service))
        assert isinstance(default_collector, type(injected_collector))

        # Both should have proper dependencies
        assert default_service.storage is not None
        assert injected_service.storage is not None
        assert default_collector.metrics_service is not None
        assert injected_collector.metrics_service is not None

    def test_backward_compatibility(self):
        """Test that existing code without dependency injection still works."""
        # This simulates how existing code would call the factories

        # Old way - should still work
        service = create_metrics_service()
        storage = create_metrics_storage()
        collector = create_metrics_collector(OperationType.FIRMWARE_COMPILATION)

        # Verify everything is properly created
        assert service is not None
        assert storage is not None
        assert collector is not None
        assert service.storage is not None
        assert collector.metrics_service is not None

    def test_none_injection_equivalent_to_default(self):
        """Test that passing None is equivalent to not passing the parameter."""
        # Create with explicit None
        service_none = create_metrics_service(storage=None)
        storage_none = create_metrics_storage(cache=None)
        collector_none = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION, metrics_service=None
        )

        # Create with defaults (no parameters)
        service_default = create_metrics_service()
        storage_default = create_metrics_storage()
        collector_default = create_metrics_collector(OperationType.LAYOUT_COMPILATION)

        # Should have same types and proper initialization
        assert isinstance(service_none, type(service_default))
        assert isinstance(storage_none, type(storage_default))
        assert isinstance(collector_none, type(collector_default))

        assert service_none.storage is not None
        assert storage_none.cache is not None
        assert collector_none.metrics_service is not None
