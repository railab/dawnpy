# tools/dawnpy/tests/descriptor/handlers/test_io_trigger.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from tests.descriptor.handlers.helpers import to_io_obj

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_trigger_io_full(self, generator):
        """Test special IO generator for trigger target/allowed payload."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["prog1"],
                    "allowed": ["trigger1", "trigger2"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]
        assert "PROG1," in lines[2]
        assert "CIOTrigger::cfgIdAllowed()," in lines[3]
        assert "TRIG_ALLOW_TRIGGER1" in lines[4]
        assert "TRIG_ALLOW_TRIGGER2" in lines[4]

    def test_generate_trigger_io_reset_only(self, generator):
        """Test trigger payload with only reset allowed."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["reset"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]
        assert "IO1," in lines[2]
        assert "CIOTrigger::cfgIdAllowed()," in lines[3]
        assert "TRIG_ALLOW_RESET" in lines[4]
        assert "TRIG_ALLOW_TRIGGER1" not in lines[4]

    def test_generate_trigger_io_via_generate_io_config(self, generator):
        """Test that _generate_io_config dispatches to trigger handler."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1"],
                    "allowed": ["trigger1"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(1)," in lines[1]

    def test_generate_trigger_io_multi_target(self, generator):
        """Test trigger payload with multiple targets."""
        obj = to_io_obj(
            {
                "type": "trigger",
                "config": {
                    "targets": ["io1", "io2", "io3"],
                    "allowed": ["trigger1"],
                },
            },
            obj_id="trig1",
        )
        lines = generator._generate_io_config("TRIG1", obj)
        assert "TRIG1, 2," in lines[0]
        assert "CIOTrigger::cfgIdAllocObj(3)," in lines[1]
        assert "IO1," in lines[2]
        assert "IO2," in lines[3]
        assert "IO3," in lines[4]
        assert "CIOTrigger::cfgIdAllowed()," in lines[5]
