# tools/dawnpy/src/dawnpy/descriptor/handlers/io_sensor_producer.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Handler for the ``sensor_producer`` IO type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

if TYPE_CHECKING:
    from dawnpy.descriptor.definitions.objects import IoObject
    from dawnpy.descriptor.generation.io_runtime import IoGeneratorContext

_CLASS_SUFFIXES: dict[str, str] = {
    "accel": "ACCELEROMETER",
    "mag": "MAGNETICFIELD",
    "gyro": "GYROSCOPE",
    "light": "LIGHT",
    "baro": "BAROMETER",
    "prox": "PROXIMITY",
    "hum": "HUMIDITY",
    "temp": "TEMPERATURE",
    "atemp": "ATEMPERATURE",
    "rgb": "RGB",
    "ir": "IR",
    "uv": "UV",
    "gas": "GAS",
}

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


def emit_config_field_cpp(
    lines: list[str],
    field: ConfigField,
    obj: IoObject,
    ctx: IoGeneratorContext,
) -> bool:
    """Emit a config ID tagged with the concrete producer class."""
    if field.name not in ("queue_size", "persist"):
        return False

    suffix = _CLASS_SUFFIXES[str(obj.subtype)]
    cls = f"CIOCommon::IO_CLASS_SENSOR_PRODUCER_{suffix}"
    ctx.format_helper.append_line(lines, 2, f"{field.cpp_helper}({cls}),")
    return True
