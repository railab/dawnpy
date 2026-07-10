# tools/dawnpy/tests/descriptor/handlers/test_prog_common.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Program config generator integration tests.

Per-field C++ emitters are covered by ``test_prog_config_cpp.py`` (shared
generic emitters) and each handler's own test module (program-specific
value-types). This module exercises the ``generate_prog_config`` orchestrator.
"""

import pytest

from dawnpy.descriptor.definitions.objects import ProgramObject
from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.generation.generator import DescriptorGenerator

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_generate_prog_config_handles_id_single(monkeypatch):
    generator = DescriptorGenerator()
    monkeypatch.setattr(
        generator.config_loader,
        "get_prog_type_fields",
        lambda prog_type: [
            ConfigField(
                name="target",
                value_type="id_single",
                cpp_helper="CProgProcess::cfgIdTarget",
            ),
        ],
    )

    obj = ProgramObject.from_spec(
        {
            "id": "prog1",
            "type": "stats",
            "instance": 1,
            "config": {"target": "io1"},
        }
    )
    assert obj is not None
    lines = generator._generate_prog_config("PROG1", obj)
    assert any("IO1" in line for line in lines)

    obj_no_target = ProgramObject.from_spec(
        {
            "id": "prog1",
            "type": "stats",
            "instance": 1,
            "config": {},
        }
    )
    assert obj_no_target is not None
    lines_no_target = generator._generate_prog_config("PROG1", obj_no_target)
    assert any("0," in line for line in lines_no_target)
