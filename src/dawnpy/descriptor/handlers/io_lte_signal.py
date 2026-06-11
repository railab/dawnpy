# tools/dawnpy/src/dawnpy/descriptor/handlers/io_lte_signal.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Complete handler for the ``lte_signal`` IO type.

A read-only, timer-driven modem signal-quality IO. One read returns the full
metric vector [RSRP, RSRQ, SINR, band] (signed dBm/dB, hence int16); a timerfd
polls every ``interval`` microseconds and notifies, so a ``vecsplit`` program
can fan the vector out into the individual scalars.
"""

from dawnpy.descriptor.definitions.type_info import ConfigField
from dawnpy.descriptor.encoding.io_serialization import _IOSerializeContext

yaml_type: str = "lte_signal"
cpp_class: str = "CIOLteSignal"
nuttx_requirements: tuple[str, ...] = ("CONFIG_LTE_LAPI",)
no_fields: bool = True
pass_through: bool = False
dtype: str | None = "int16"
variant_dtypes: dict[str, str] = {}


def config_fields() -> list[ConfigField]:
    """Return the poll-interval config field (microseconds)."""
    return [
        ConfigField(
            name="interval",
            cpp_helper="CIOLteSignal::cfgIdInterval",
            value_type="int",
        ),
    ]


def encode_binary(ctx: _IOSerializeContext) -> None:
    """No per-instance binary encoding."""
    del ctx  # pragma: no cover
