"""Device waiting state management for flash operations."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from glovebox.firmware.flash.models import BlockDevice


@dataclass
class DeviceWaitState:
    """State management for device waiting operations."""

    target_count: int
    query: str
    timeout: float
    poll_interval: float = 0.5
    show_progress: bool = True

    # Runtime state
    found_devices: list[BlockDevice] = field(default_factory=list)
    waiting: bool = True
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since waiting started."""
        return time.time() - self.start_time

    @property
    def is_timeout(self) -> bool:
        """Check if timeout has been reached."""
        return self.elapsed_time >= self.timeout

    @property
    def is_target_reached(self) -> bool:
        """Check if target device count has been reached."""
        return len(self.found_devices) >= self.target_count

    @property
    def should_stop_waiting(self) -> bool:
        """Check if waiting should stop (target reached or timeout)."""
        return not self.waiting or self.is_target_reached or self.is_timeout

    def add_device(self, device: BlockDevice) -> None:
        """Add a device to the found devices list."""
        if device not in self.found_devices:
            self.found_devices.append(device)

    def remove_device(self, device: BlockDevice) -> None:
        """Remove a device from the found devices list."""
        self.found_devices = [
            d for d in self.found_devices if d.device_node != device.device_node
        ]

    def stop_waiting(self) -> None:
        """Stop the waiting process."""
        self.waiting = False


DeviceCallback = Callable[[str, BlockDevice], None]
ProgressCallback = Callable[[DeviceWaitState], None]
