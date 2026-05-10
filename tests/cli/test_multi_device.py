# tools/dawnpy/tests/test_multi_device.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for multi-device manager."""

from dawnpy.cli.multi_device import MultiDeviceManager


class _HB:
    def __init__(self, live: bool):
        self.interval_s = 1.0
        self.timeout_mult = 2
        self.last_seen = None
        self._live = live

    def is_live(self, now=None):
        return self._live


def test_multi_device_manager_status():
    manager = MultiDeviceManager(["dev1", "dev2"])
    manager.set_heartbeat(0, _HB(True))
    manager.set_heartbeat(1, _HB(False))

    status = manager.heartbeat_status(0)
    assert status is not None
    assert status["live"]

    status = manager.heartbeat_status(1)
    assert status is not None
    assert not status["live"]

    assert manager.heartbeat_status(2) is None


def test_multi_device_wait_no_heartbeat(capsys):
    manager = MultiDeviceManager(["dev1"])
    manager.wait_for_heartbeats()
    out = capsys.readouterr().out
    assert out == ""


def test_multi_device_wait_with_heartbeat(capsys):
    manager = MultiDeviceManager(["dev1"])
    manager.set_heartbeat(0, _HB(True))
    manager.wait_for_heartbeats()
    out = capsys.readouterr().out
    assert "Waiting for heartbeat" in out
    assert "Heartbeat detected" in out


def test_multi_device_wait_timeout(capsys, monkeypatch):
    manager = MultiDeviceManager(["dev1"])
    manager.set_heartbeat(0, _HB(False))
    monkeypatch.setattr(
        "dawnpy.cli.multi_device.time.sleep", lambda *_args, **_kwargs: None
    )
    manager.wait_for_heartbeats()
    out = capsys.readouterr().out
    assert "No heartbeat received" in out
