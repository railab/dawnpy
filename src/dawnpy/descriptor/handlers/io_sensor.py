# tools/dawnpy/src/dawnpy/descriptor/handlers/io_sensor.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``sensor`` IO type (no per-instance fields)."""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "sensor"
cpp_class: str = "CIOSensor"
nuttx_requirements: tuple[str, ...] = ("CONFIG_SENSORS",)
no_fields: bool = True
pass_through: bool = False
dtype: str | None = None
# GNSS sub-IOs carry non-float fields: time as seconds (uint64) and the
# satellite count (uint32). Other subtypes default to the float sensor data.
variant_dtypes: dict[str, str] = {"gnss_time": "uint64", "gnss_sats": "uint32"}


def config_fields() -> list[ConfigField]:
    """Return user-facing sensor config fields."""
    return [
        ConfigField(
            name="update_interval",
            cpp_helper="CIOSensor::cfgIdUpdateInterval",
            value_type="int",
        ),
        ConfigField(
            name="measurement_period",
            cpp_helper="CIOSensor::cfgIdMeasurementPeriod",
            value_type="int",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
