# tools/dawnpy/tests/descriptor/handlers/test_io_control.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import IoObject
from tests.descriptor.handlers.helpers import to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_control_io_full(self, generator):
        """Test special IO generator for control target/allowed payload."""
        obj = IoObject(
            obj_id="ctrl1",
            io_type="control",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={
                "targets": ["sampling1", "sampling2"],
                "allowed": ["start", "stop"],
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(2)," in lines[1]
        assert "SAMPLING1," in lines[2]
        assert "SAMPLING2," in lines[3]
        assert "CIOControl::cfgIdAllowed()," in lines[4]
        assert "CTRL_ALLOW_START" in lines[5]
        assert "CTRL_ALLOW_STOP" in lines[5]

    def test_generate_control_io_start_only(self, generator):
        """Test control payload with only start allowed."""
        obj = IoObject(
            obj_id="ctrl1",
            io_type="control",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={
                "targets": ["io1"],
                "allowed": ["start"],
            },
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(1)," in lines[1]
        assert "IO1," in lines[2]
        assert "CIOControl::cfgIdAllowed()," in lines[3]
        assert "CTRL_ALLOW_START" in lines[4]
        assert "CTRL_ALLOW_STOP" not in lines[4]

    def test_generate_control_io_no_targets(self, generator):
        """Test control payload with no targets (only allowed)."""
        obj = to_io_obj(
            {
                "type": "control",
                "config": {
                    "allowed": ["stop"],
                },
            },
            obj_id="ctrl1",
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 1," in lines[0]
        assert "CIOControl::cfgIdAllowed()," in lines[1]
        assert "CTRL_ALLOW_STOP" in lines[2]

    def test_generate_control_io_via_generate_io_config(self, generator):
        """Test that _generate_io_config dispatches to control handler."""
        obj = to_io_obj(
            {
                "type": "control",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["start"],
                },
            },
            obj_id="ctrl1",
        )
        lines = generator._generate_io_config("CTRL1", obj)
        assert "CTRL1, 2," in lines[0]
        assert "CIOControl::cfgIdAllocObj(1)," in lines[1]

    def test_io_allowed_flag_map_from_config(self):
        """Test IO allow-flag enums are loaded from config."""
        from dawnpy.descriptor.handlers import io_control, io_trigger

        control_map = io_control.allowed_symbols
        trigger_map = io_trigger.allowed_symbols
        assert control_map["start"] == "CIOControl::CTRL_ALLOW_START"
        assert control_map["stop"] == "CIOControl::CTRL_ALLOW_STOP"
        assert trigger_map["trigger1"] == "CIOTrigger::TRIG_ALLOW_TRIGGER1"
        assert trigger_map["reset"] == "CIOTrigger::TRIG_ALLOW_RESET"

    def test_io_allowed_symbols_are_handler_owned(self):
        """Test allow-flag mappings live in the IO handlers."""
        from dawnpy.descriptor.handlers import io_control, io_dummy, io_trigger

        control_map = io_control.allowed_symbols
        trigger_map = io_trigger.allowed_symbols
        assert control_map["start"] == "CIOControl::CTRL_ALLOW_START"
        assert trigger_map["trigger3"] == "CIOTrigger::TRIG_ALLOW_TRIGGER3"
        assert not hasattr(io_dummy, "allowed_symbols")
