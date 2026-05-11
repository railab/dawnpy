# tools/dawnpy/tests/test_descriptor_types.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for descriptor type loading and mapping."""

import pytest

from dawnpy.descriptor.definitions.registry import (
    DTYPE_INITVAL_PARAM_MAP,
    DTYPE_MAP,
    IO_TYPES,
    PROG_TYPES,
    PROTO_TYPES,
    IOTypeInfo,
    ProgTypeInfo,
    ProtoTypeInfo,
    get_io_helper_call,
    get_prog_helper_call,
    get_proto_helper_call,
)

pytestmark = pytest.mark.usefixtures("source_free_headers")


class TestTypeLoading:
    """Test YAML configuration loading."""

    def test_dtype_map_loaded(self):
        """Test that data type map is loaded from YAML."""
        assert len(DTYPE_MAP) > 0
        assert "bool" in DTYPE_MAP
        assert "int32" in DTYPE_MAP
        assert "float" in DTYPE_MAP
        assert DTYPE_MAP["bool"] == "SObjectId::DTYPE_BOOL"

    def test_dtype_initval_param_map_loaded(self):
        """Test cfgIdInitval dtype params match SObjectId::DTYPE_*."""
        assert DTYPE_INITVAL_PARAM_MAP["bool"] == 1
        assert DTYPE_INITVAL_PARAM_MAP["int8"] == 2
        assert DTYPE_INITVAL_PARAM_MAP["uint8"] == 3
        assert DTYPE_INITVAL_PARAM_MAP["int16"] == 4
        assert DTYPE_INITVAL_PARAM_MAP["uint16"] == 5
        assert DTYPE_INITVAL_PARAM_MAP["int32"] == 6
        assert DTYPE_INITVAL_PARAM_MAP["uint32"] == 7
        assert DTYPE_INITVAL_PARAM_MAP["int64"] == 8
        assert DTYPE_INITVAL_PARAM_MAP["uint64"] == 9
        assert DTYPE_INITVAL_PARAM_MAP["float"] == 10
        assert DTYPE_INITVAL_PARAM_MAP["double"] == 11

    def test_io_types_loaded(self):
        """Test that IO types are loaded from YAML."""
        assert len(IO_TYPES) > 0
        assert "dummy" in IO_TYPES
        assert "adc_fetch" in IO_TYPES
        assert "adc_sync" in IO_TYPES
        assert "adc_stream" in IO_TYPES
        assert isinstance(IO_TYPES["dummy"], IOTypeInfo)

    def test_prog_types_loaded(self):
        """Test that program types are loaded from YAML."""
        assert len(PROG_TYPES) > 0
        assert "stats" in PROG_TYPES
        assert "sampling" in PROG_TYPES
        assert "latest" in PROG_TYPES
        assert "redirect" in PROG_TYPES
        assert "dummy" in PROG_TYPES
        assert "statsrms" in PROG_TYPES
        assert "movingavg" in PROG_TYPES
        assert "iirfilter" in PROG_TYPES
        assert "manytoone" in PROG_TYPES
        assert "onetomany" in PROG_TYPES
        assert "iomux" in PROG_TYPES
        assert "iodemux" in PROG_TYPES
        assert isinstance(PROG_TYPES["stats"], ProgTypeInfo)

    def test_proto_types_loaded(self):
        """Test that protocol types are loaded from YAML."""
        assert len(PROTO_TYPES) > 0
        assert "serial" in PROTO_TYPES
        assert "can" in PROTO_TYPES
        assert "dummy" in PROTO_TYPES
        assert isinstance(PROTO_TYPES["serial"], ProtoTypeInfo)


class TestIOTypeInfo:
    """Test IOTypeInfo class."""

    def test_initialization(self):
        """Test IOTypeInfo initialization."""
        info = IOTypeInfo(
            cpp_class="CIODummy",
            header="dawn/io/dummy.hxx",
            helper_func="{cpp_class}::objectId",
            params=["dtype", "rw", "instance"],
        )
        assert info.cpp_class == "CIODummy"
        assert info.header == "dawn/io/dummy.hxx"
        assert info.params == ["dtype", "rw", "instance"]

    def test_generate_helper_call_simple(self):
        """Test generating simple helper call."""
        info = IOTypeInfo(
            cpp_class="CIODummy",
            header="dawn/io/dummy.hxx",
            helper_func="{cpp_class}::objectId",
            params=["dtype", "rw", "instance"],
        )
        call = info.generate_helper_call(
            "CIODummy",
            "SObjectId::DTYPE_BOOL",
            {},
            1,
        )
        assert call == "CIODummy::objectId(SObjectId::DTYPE_BOOL, false, 1)"

    def test_generate_helper_call_with_flags(self):
        """Test generating helper call with flags."""
        info = IOTypeInfo(
            cpp_class="CIOAdcFetch",
            header="dawn/io/adc_fetch.hxx",
            helper_func="{cpp_class}::objectId",
            params=["timestamp", "instance"],
        )
        call = info.generate_helper_call(
            "CIOAdcFetch",
            "SObjectId::DTYPE_INT32",
            {"timestamp": True},
            2,
        )
        assert call == "CIOAdcFetch::objectId(true, 2)"

    def test_generate_helper_call_default_rw(self):
        """Test generating helper call with default rw value."""
        info = IOTypeInfo(
            cpp_class="CIODummy",
            header="dawn/io/dummy.hxx",
            helper_func="{cpp_class}::objectId",
            params=["dtype", "rw", "instance"],
        )
        # Don't provide rw in flags - should default to false
        call = info.generate_helper_call(
            "CIODummy",
            "SObjectId::DTYPE_BOOL",
            {},  # Empty flags dict
            1,
        )
        assert call == "CIODummy::objectId(SObjectId::DTYPE_BOOL, false, 1)"

    def test_generate_helper_call_default_timestamp(self):
        """Test generating helper call with default timestamp value."""
        info = IOTypeInfo(
            cpp_class="CIOAdcFetch",
            header="dawn/io/adc_fetch.hxx",
            helper_func="{cpp_class}::objectId",
            params=["timestamp", "instance"],
        )
        # Don't provide timestamp in flags - should default to false
        call = info.generate_helper_call(
            "CIOAdcFetch",
            "SObjectId::DTYPE_INT32",
            {},  # Empty flags dict
            2,
        )
        assert call == "CIOAdcFetch::objectId(false, 2)"

    def test_generate_helper_call_default_notify(self):
        """Test generating helper call with default notify value."""
        info = IOTypeInfo(
            cpp_class="CIOGpi",
            header="dawn/io/gpi.hxx",
            helper_func="{cpp_class}::objectId",
            params=["notify", "instance"],
        )
        # Don't provide notify in flags - should default to false
        call = info.generate_helper_call(
            "CIOGpi", "", {}, 1  # Empty flags dict
        )
        assert call == "CIOGpi::objectId(false, 1)"


class TestGetIOHelperCall:
    """Test get_io_helper_call function."""

    def test_dummy_io(self):
        """Test dummy IO helper call generation."""
        cpp_class, call = get_io_helper_call(
            io_type="dummy",
            subtype=None,
            variant=None,
            dtype="bool",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIODummy"
        assert "CIODummy::objectId" in call
        assert "DTYPE_BOOL" in call
        assert "false" in call
        assert "1" in call

    def test_adc_io_with_timestamp(self):
        """Test adc_fetch IO helper call with timestamp."""
        cpp_class, call = get_io_helper_call(
            io_type="adc_fetch",
            subtype=None,
            variant=None,
            dtype="float",
            instance=1,
            flags={"timestamp": True},
        )
        assert cpp_class == "CIOAdcFetch"
        assert "CIOAdcFetch::objectId" in call
        assert "true" in call  # timestamp=True
        assert "1" in call  # instance=1

    def test_adc_sync_io_with_timestamp(self):
        """Test adc_sync IO helper call with timestamp."""
        cpp_class, call = get_io_helper_call(
            io_type="adc_sync",
            subtype=None,
            variant=None,
            dtype="float",
            instance=1,
            flags={"timestamp": True},
        )
        assert cpp_class == "CIOAdcSync"
        assert "CIOAdcSync::objectId" in call
        assert "true" in call  # timestamp=True
        assert "1" in call  # instance=1

    def test_adc_stream_io_with_timestamp(self):
        """Test adc_stream IO helper call with timestamp."""
        cpp_class, call = get_io_helper_call(
            io_type="adc_stream",
            subtype=None,
            variant=None,
            dtype="float",
            instance=1,
            flags={"timestamp": True},
        )
        assert cpp_class == "CIOAdcStream"
        assert "CIOAdcStream::objectId" in call
        assert "true" in call  # timestamp=True
        assert "1" in call  # instance=1

    def test_sensor_with_subtype(self):
        """Test sensor IO with subtype."""
        cpp_class, call = get_io_helper_call(
            io_type="sensor",
            subtype="temp",
            variant=None,
            dtype="float",
            instance=1,
            flags={"timestamp": False},
        )
        assert cpp_class == "CIOSensor"
        assert "objectIdTemp" in call
        assert "DTYPE_FLOAT" in call

    def test_sensor_producer_with_subtype(self):
        """Test sensor producer IO with subtype."""
        cpp_class, call = get_io_helper_call(
            io_type="sensor_producer",
            subtype="temp",
            variant=None,
            dtype="float",
            instance=10,
            flags={"timestamp": False},
        )
        assert cpp_class == "CIOSensorProducer"
        assert "objectIdTemp" in call
        assert "DTYPE_FLOAT" in call

    def test_sensor_producer_with_atemp_subtype(self):
        """Test sensor producer ambient-temperature helper capitalization."""
        cpp_class, call = get_io_helper_call(
            io_type="sensor_producer",
            subtype="atemp",
            variant=None,
            dtype="float",
            instance=10,
            flags={"timestamp": False},
        )
        assert cpp_class == "CIOSensorProducer"
        assert "objectIdAtemp" in call
        assert "DTYPE_FLOAT" in call

    def test_sysinfo_uptime_variant(self):
        """Test sysinfo IO with uptime variant."""
        cpp_class, call = get_io_helper_call(
            io_type="sysinfo",
            subtype=None,
            variant="uptime",
            dtype="uint64",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOSysinfo"
        assert "objectIdUptime()" in call

    def test_sysinfo_cpuload_variant(self):
        """Test sysinfo IO with cpuload variant."""
        cpp_class, call = get_io_helper_call(
            io_type="sysinfo",
            subtype=None,
            variant="cpuload",
            dtype="float",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOSysinfo"

    def test_variant_required_but_not_provided(self):
        """Test error when variant is required but not provided."""
        with pytest.raises(
            ValueError, match="Variant required but not provided"
        ):
            get_io_helper_call(
                io_type="sysinfo",  # Has {variant} in helper_func
                subtype=None,
                variant=None,  # Not provided!
                dtype="uint64",
                instance=1,
                flags={},
            )

    def test_unknown_io_type(self):
        """Test unknown IO type raises error."""
        with pytest.raises(ValueError, match="Unknown IO type"):
            get_io_helper_call(
                io_type="unknown",
                subtype=None,
                variant=None,
                dtype="bool",
                instance=1,
                flags={},
            )


class TestGetProgHelperCall:
    """Test get_prog_helper_call function."""

    def test_stats_program(self):
        """Test stats program helper call."""
        cpp_class, call = get_prog_helper_call("stats", 1)
        assert cpp_class == "CProgProcess"
        assert call == "CProgProcess::objectId(1)"

    def test_sampling_program(self):
        """Test sampling program helper call."""
        cpp_class, call = get_prog_helper_call("sampling", 2)
        assert cpp_class == "CProgSampling"
        assert call == "CProgSampling::objectId(2)"

    def test_dummy_program(self):
        """Test dummy program helper call."""
        cpp_class, call = get_prog_helper_call("dummy", 2)
        assert cpp_class == "CProgDummy"
        assert call == "CProgDummy::objectId(2)"

    def test_latest_program(self):
        """Test latest program helper call."""
        cpp_class, call = get_prog_helper_call("latest", 3)
        assert cpp_class == "CProgLatest"
        assert call == "CProgLatest::objectId(3)"

    def test_stats_rms_program(self):
        """Test stats rms program helper call."""
        cpp_class, call = get_prog_helper_call("statsrms", 3)
        assert cpp_class == "CProgStatsRms"
        assert call == "CProgStatsRms::objectId(3)"

    def test_redirect_program(self):
        """Test redirect program helper call."""
        cpp_class, call = get_prog_helper_call("redirect", 4)
        assert cpp_class == "CProgRedirect"
        assert call == "CProgRedirect::objectId(4)"

    def test_movingavg_program(self):
        """Test moving average program helper call."""
        cpp_class, call = get_prog_helper_call("movingavg", 5)
        assert cpp_class == "CProgMovingAverage"
        assert call == "CProgMovingAverage::objectId(5)"

    def test_iirfilter_program(self):
        """Test IIR filter program helper call."""
        cpp_class, call = get_prog_helper_call("iirfilter", 6)
        assert cpp_class == "CProgIIRFilter"
        assert call == "CProgIIRFilter::objectId(6)"

    def test_unknown_prog_type(self):
        """Test unknown program type raises error."""
        with pytest.raises(ValueError, match="Unknown Program type"):
            get_prog_helper_call("unknown", 1)


class TestGetProtoHelperCall:
    """Test get_proto_helper_call function."""

    def test_serial_protocol(self):
        """Test serial protocol helper call."""
        cpp_class, call = get_proto_helper_call("serial", 1)
        assert cpp_class == "CProtoSerial"
        assert call == "CProtoSerial::objectId(1)"

    def test_can_protocol(self):
        """Test CAN protocol helper call."""
        cpp_class, call = get_proto_helper_call("can", 1)
        assert cpp_class == "CProtoCan"
        assert call == "CProtoCan::objectId(1)"

    def test_dummy_protocol(self):
        """Test dummy protocol helper call."""
        cpp_class, call = get_proto_helper_call("dummy", 2)
        assert cpp_class == "CProtoDummy"
        assert call == "CProtoDummy::objectId(2)"

    def test_unknown_proto_type(self):
        """Test unknown protocol type raises error."""
        with pytest.raises(ValueError, match="Unknown Protocol type"):
            get_proto_helper_call("unknown", 1)


class TestDTypeMapping:
    """Test data type mapping."""

    def test_all_basic_types_present(self):
        """Test that all basic data types are present."""
        expected_types = [
            "any",
            "bool",
            "int8",
            "uint8",
            "int16",
            "uint16",
            "int32",
            "uint32",
            "int64",
            "uint64",
            "float",
            "double",
        ]
        for dtype in expected_types:
            assert dtype in DTYPE_MAP

    def test_dtype_format(self):
        """Test that dtypes are in correct format."""
        for _, cpp_const in DTYPE_MAP.items():
            assert cpp_const.startswith("SObjectId::DTYPE_")


class TestIOTypeAttributes:
    """Test IO type attributes."""

    def test_dummy_io_attributes(self):
        """Test dummy IO type attributes."""
        dummy = IO_TYPES["dummy"]
        assert dummy.cpp_class == "CIODummy"
        assert dummy.header == "dawn/io/dummy.hxx"
        assert "dtype" in dummy.params
        assert "rw" not in dummy.params
        assert "instance" in dummy.params

    def test_adc_fetch_io_attributes(self):
        """Test adc_fetch IO type attributes."""
        adc = IO_TYPES["adc_fetch"]
        assert adc.cpp_class == "CIOAdcFetch"
        assert adc.header == "dawn/io/adc_fetch.hxx"
        assert "timestamp" in adc.params
        assert "instance" in adc.params

    def test_adc_sync_io_attributes(self):
        """Test adc_sync IO type attributes."""
        adc = IO_TYPES["adc_sync"]
        assert adc.cpp_class == "CIOAdcSync"
        assert adc.header == "dawn/io/adc_sync.hxx"
        assert "timestamp" in adc.params
        assert "instance" in adc.params

    def test_adc_stream_io_attributes(self):
        """Test adc_stream IO type attributes."""
        adc = IO_TYPES["adc_stream"]
        assert adc.cpp_class == "CIOAdcStream"
        assert adc.header == "dawn/io/adc_stream.hxx"
        assert "timestamp" in adc.params
        assert "instance" in adc.params

    def test_sensor_has_subtypes(self):
        """Test sensor IO has subtypes defined."""
        sensor = IO_TYPES["sensor"]
        assert hasattr(sensor, "subtypes")
        assert len(sensor.subtypes) > 0


class TestProgTypeAttributes:
    """Test program type attributes."""

    def test_stats_prog_attributes(self):
        """Test stats program type attributes."""
        stats = PROG_TYPES["stats"]
        assert stats.cpp_class == "CProgProcess"
        assert stats.header == "dawn/prog/process.hxx"

    def test_sampling_prog_attributes(self):
        """Test sampling program type attributes."""
        sampling = PROG_TYPES["sampling"]
        assert sampling.cpp_class == "CProgSampling"
        assert sampling.header == "dawn/prog/sampling.hxx"

    def test_dummy_prog_attributes(self):
        """Test dummy program type attributes."""
        dummy = PROG_TYPES["dummy"]
        assert dummy.cpp_class == "CProgDummy"
        assert dummy.header == "dawn/prog/dummy.hxx"

    def test_latest_prog_attributes(self):
        """Test latest program type attributes."""
        latest = PROG_TYPES["latest"]
        assert latest.cpp_class == "CProgLatest"
        assert latest.header == "dawn/prog/latest.hxx"

    def test_stats_rms_prog_attributes(self):
        """Test stats rms program type attributes."""
        rms = PROG_TYPES["statsrms"]
        assert rms.cpp_class == "CProgStatsRms"
        assert rms.header == "dawn/prog/statsrms.hxx"

    def test_redirect_prog_attributes(self):
        """Test redirect program type attributes."""
        redirect = PROG_TYPES["redirect"]
        assert redirect.cpp_class == "CProgRedirect"
        assert redirect.header == "dawn/prog/redirect.hxx"

    def test_movingavg_prog_attributes(self):
        """Test moving average program type attributes."""
        movavg = PROG_TYPES["movingavg"]
        assert movavg.cpp_class == "CProgMovingAverage"
        assert movavg.header == "dawn/prog/movingavg.hxx"

    def test_iirfilter_prog_attributes(self):
        """Test IIR filter program type attributes."""
        iir = PROG_TYPES["iirfilter"]
        assert iir.cpp_class == "CProgIIRFilter"
        assert iir.header == "dawn/prog/iirfilter.hxx"


class TestProtoTypeAttributes:
    """Test protocol type attributes."""

    def test_serial_proto_attributes(self):
        """Test serial protocol type attributes."""
        serial = PROTO_TYPES["serial"]
        assert serial.cpp_class == "CProtoSerial"
        assert serial.header == "dawn/proto/serial/simple.hxx"

    def test_can_proto_attributes(self):
        """Test CAN protocol type attributes."""
        can = PROTO_TYPES["can"]
        assert can.cpp_class == "CProtoCan"
        assert can.header == "dawn/proto/can/can.hxx"

    def test_dummy_proto_attributes(self):
        """Test dummy protocol type attributes."""
        dummy = PROTO_TYPES["dummy"]
        assert dummy.cpp_class == "CProtoDummy"
        assert dummy.header == "dawn/proto/dummy.hxx"


class TestHelperCallEdgeCases:
    """Test edge cases in helper call generation."""

    def test_gpi_io_with_notify(self):
        """Test GPI IO with notify flag."""
        cpp_class, call = get_io_helper_call(
            io_type="gpi",
            subtype=None,
            variant=None,
            dtype="bool",
            instance=1,
            flags={"notify": True},
        )
        assert cpp_class == "CIOGpi"
        assert "true" in call

    def test_gpo_io_with_notify(self):
        """Test GPO IO with notify flag."""
        cpp_class, call = get_io_helper_call(
            io_type="gpo",
            subtype=None,
            variant=None,
            dtype="bool",
            instance=2,
            flags={"notify": False},
        )
        assert cpp_class == "CIOGpo"
        assert "false" in call

    def test_dac_io(self):
        """Test DAC IO generation."""
        cpp_class, call = get_io_helper_call(
            io_type="dac",
            subtype=None,
            variant=None,
            dtype="uint16",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIODac"
        assert "CIODac::objectId" in call
        assert "false" in call  # timestamp=False
        assert "1" in call  # instance=1

    def test_rand_io(self):
        """Test random IO generation."""
        cpp_class, call = get_io_helper_call(
            io_type="rand",
            subtype=None,
            variant=None,
            dtype="uint32",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIORand"
        assert "DTYPE_UINT32" in call

    def test_virt_io_with_notify(self):
        """Test virtual IO with notify."""
        cpp_class, call = get_io_helper_call(
            io_type="virt",
            subtype=None,
            variant=None,
            dtype="float",
            instance=1,
            flags={"notify": True},
        )
        assert cpp_class == "CIOVirt"
        assert "DTYPE_FLOAT" in call
        assert "true" in call

    def test_config_io(self):
        """Test config IO generation."""
        cpp_class, call = get_io_helper_call(
            io_type="config",
            subtype=None,
            variant=None,
            dtype="uint32",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOConfig"
        assert "DTYPE_UINT32" in call

    def test_timestamp_io(self):
        """Test timestamp IO generation."""
        cpp_class, call = get_io_helper_call(
            io_type="timestamp",
            subtype=None,
            variant=None,
            dtype="uint64",
            instance=1,
            flags={"timestamp": False},
        )
        assert cpp_class == "CIOTimestamp"
        assert "DTYPE_UINT64" in call

    def test_uname_hostname_variant(self):
        """Test uname IO with hostname variant."""
        cpp_class, call = get_io_helper_call(
            io_type="uname",
            subtype=None,
            variant="hostname",
            dtype="char",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOUname"
        assert "objectIdHostname()" in call

    def test_boardctl_variant(self):
        """Test boardctl IO."""
        cpp_class, call = get_io_helper_call(
            io_type="boardctl",
            subtype=None,
            variant="default",
            dtype="bool",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOBoardctl"
        assert "objectIdDefault()" in call

    def test_boardctl_variant_snake_case(self):
        """Test boardctl variant with snake_case to CamelCase conversion."""
        cpp_class, call = get_io_helper_call(
            io_type="boardctl",
            subtype=None,
            variant="reset_cause",  # snake_case gets converted to ResetCause
            dtype="uint32",
            instance=1,
            flags={},
        )
        assert cpp_class == "CIOBoardctl"
        # Should convert reset_cause to ResetCause
        assert "objectIdResetCause" in call

    def test_sensor_with_different_subtypes(self):
        """Test sensor with various subtypes."""
        subtypes = ["accel", "gyro", "mag", "press", "humi"]
        for subtype in subtypes:
            cpp_class, call = get_io_helper_call(
                io_type="sensor",
                subtype=subtype,
                variant=None,
                dtype="float",
                instance=1,
                flags={},
            )
            assert cpp_class == "CIOSensor"
            assert f"objectId{subtype.capitalize()}" in call

    def test_all_prog_types(self):
        """Test all program types."""
        for prog_type in [
            "stats",
            "statsmin",
            "statsrms",
            "sampling",
            "dummy",
            "adjust",
            "latest",
            "redirect",
            "movingavg",
            "iirfilter",
            "manytoone",
            "onetomany",
            "iomux",
            "iodemux",
        ]:
            cpp_class, call = get_prog_helper_call(prog_type, 1)
            assert "objectId(1)" in call

    def test_all_proto_types(self):
        """Test all protocol types."""
        for proto_type in [
            "dummy",
            "serial",
            "modbus_rtu",
            "can",
            "shell",
            "nimble",
            "nxscope_dummy",
            "nxscope_serial",
        ]:
            cpp_class, call = get_proto_helper_call(proto_type, 1)
            assert "objectId(1)" in call


class TestIOTypeInfoOptionalParams:
    """Test IOTypeInfo with optional parameters."""

    def test_io_type_info_with_subtypes(self):
        """Test IOTypeInfo with subtypes."""
        info = IOTypeInfo(
            cpp_class="CIOSensor",
            header="dawn/io/sensor.hxx",
            helper_func="{cpp_class}::objectId{subtype}",
            params=["dtype", "timestamp", "instance"],
            subtypes=["temp", "accel"],
        )
        assert len(info.subtypes) == 2
        assert "temp" in info.subtypes

    def test_io_type_info_with_variants(self):
        """Test IOTypeInfo with variants."""
        variants = [
            {"name": "uptime", "params": []},
            {"name": "cpuload", "params": ["dtype"]},
        ]
        info = IOTypeInfo(
            cpp_class="CIOSysinfo",
            header="dawn/io/sysinfo.hxx",
            helper_func="{cpp_class}::objectId{variant}",
            params=[],
            variants=variants,
        )
        assert len(info.variants) == 2
