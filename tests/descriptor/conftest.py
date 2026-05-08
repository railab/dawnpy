# SPDX-License-Identifier: Apache-2.0

"""Shared descriptor test fixtures."""

import pytest

from dawnpy.descriptor.generation.generator import DescriptorGenerator


@pytest.fixture
def generator():
    return DescriptorGenerator()
