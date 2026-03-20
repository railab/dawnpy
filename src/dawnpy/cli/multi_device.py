# tools/dawnpy/src/dawnpy/cli/multi_device.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Multi-device management helpers for shared-bus protocols."""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass
class DeviceState:
    """Tracks per-device state."""

    name: str
    heartbeat: HeartbeatLike | None = None


class HeartbeatLike(Protocol):
    """Protocol-agnostic heartbeat state interface."""

    interval_s: float
    timeout_mult: int
    last_seen: float | None

    def is_live(self, now: float | None = None) -> bool:
        """Return True if heartbeat is considered live."""
        raise NotImplementedError


class MultiDeviceManager:
    """Tracks multi-device liveness on a shared bus."""

    def __init__(self, device_names: Iterable[str]) -> None:
        """Initialize device registry."""
        self.devices: dict[int, DeviceState] = {
            idx: DeviceState(name=name)
            for idx, name in enumerate(device_names)
        }

    def set_heartbeat(self, idx: int, heartbeat: HeartbeatLike | None) -> None:
        """Assign a heartbeat tracker to a device."""
        if idx in self.devices:
            self.devices[idx].heartbeat = heartbeat

    def wait_for_heartbeats(self) -> None:
        """Wait for heartbeats from all configured devices."""
        for idx, state in self.devices.items():
            hb = state.heartbeat
            if not hb:
                continue
            print(f"Waiting for heartbeat from device {idx} ({state.name})...")
            timeout = hb.interval_s * hb.timeout_mult
            end = time.time() + timeout
            while time.time() < end:
                if hb.is_live():
                    print(f"Heartbeat detected for device {idx}.")
                    break
                time.sleep(0.05)
            else:
                print(
                    f"No heartbeat received for device {idx}. "
                    "Device may be offline."
                )

    def heartbeat_status(self, idx: int) -> dict[str, object] | None:
        """Return heartbeat status for a device."""
        state = self.devices.get(idx)
        if not state or not state.heartbeat:
            return None
        hb = state.heartbeat
        return {
            "live": hb.is_live(),
            "last_seen": hb.last_seen,
            "interval_s": hb.interval_s,
        }
