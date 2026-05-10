# tools/dawnpy/tests/descriptor/handlers/test_io_timestamp.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler-owned descriptor tests."""

import pytest

from dawnpy.descriptor.definitions.objects import IoObject
from tests.descriptor.helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestIoHandlers:

    def test_generate_io_config_with_interval(self, generator):
        """Test generating IO config with interval."""
        obj = IoObject(
            obj_id="test_io",
            io_type="timestamp",
            dtype="uint32",
            instance=1,
            timestamp=False,
            rw=False,
            notify=False,
            tags=[],
            config={"interval_us": 1000000},
            subtype=None,
            variant=None,
        )
        lines = generator._generate_io_config("TEST_IO", obj)
        assert "TEST_IO, 1," in lines[0]
        assert "CIOTimestamp::cfgInterval" in lines[1]
        assert "1000000," in lines[2]


def test_timestamp_io_with_interval(generator):
    """Test timestamp IO with interval configuration."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "ts1",
                "type": "timestamp",
                "instance": 1,
                "dtype": "uint64",
                "timestamp": False,
                "config": {"interval_us": 1000000},
            }
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected: should use cfgInterval (not cfgIdInterval)
    expected_lines = [
        "  TS1, 1,",
        "    CIOTimestamp::cfgInterval(false),",
        "      1000000,",
    ]

    for expected in expected_lines:
        assert any(
            expected in line for line in output.split("\n")
        ), f"Expected line not found: {expected}"
