import pytest

from tests.descriptor.descriptor_helpers import generate_from_spec

pytestmark = pytest.mark.usefixtures("source_free_headers")


def test_rand_io_with_timestamp(generator):
    """Test rand IO with timestamp parameter."""
    spec = {
        "metadata": {"version": "1.0"},
        "ios": [
            {
                "id": "rand1",
                "type": "rand",
                "instance": 1,
                "dtype": "uint64",
                "timestamp": False,
            }
        ],
        "programs": [],
        "protocols": [],
    }

    output = generate_from_spec(generator, spec)

    # Expected: rand objectId should have dtype, timestamp, instance
    # (not duplicate instance)
    expected = "CIORand::objectId(SObjectId::DTYPE_UINT64, false, 1)"
    assert expected in output, f"Expected objectId not found: {expected}"
