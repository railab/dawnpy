# tools/dawnpy/src/dawnpy/descriptor/handlers/io_sensor_producer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for the ``sensor_producer`` IO type."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "sensor_producer"
cpp_class: str = "CIOSensorProducer"
nuttx_requirements: tuple[str, ...] = ("CONFIG_SENSORS", "CONFIG_USENSOR")
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return user-facing sensor producer config fields."""
    return [
        ConfigField(
            name="queue_size",
            cpp_helper="CIOSensorProducer::cfgIdQueueSize",
            value_type="int",
        ),
        ConfigField(
            name="persist",
            cpp_helper="CIOSensorProducer::cfgIdPersist",
            value_type="bool",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
