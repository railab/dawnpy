# SPDX-License-Identifier: Apache-2.0

"""Helpers for descriptor descriptor output tests."""

import tempfile
from pathlib import Path
from typing import Any

import yaml

from dawnpy.descriptor.generation.generator import DescriptorGenerator


def generate_from_spec(
    generator: DescriptorGenerator, spec: dict[str, Any]
) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(spec, f)
        yaml_path = f.name

    try:
        return generator.generate(yaml_path)
    finally:
        Path(yaml_path).unlink(missing_ok=True)
