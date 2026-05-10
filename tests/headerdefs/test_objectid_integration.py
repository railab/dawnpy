# flake8: noqa
#
# SPDX-License-Identifier: Apache-2.0
#

from tests.headerdefs.context import *


def test_objectid_init_raises_when_headers_not_available(monkeypatch):
    monkeypatch.setattr(
        objectid_mod.ObjectIdDecoder, "_load_from_headers", lambda self: False
    )
    with pytest.raises(headerdefs.HeaderDefsError, match="Failed to load"):
        objectid_mod.ObjectIdDecoder()


def test_objectid_load_from_headers_bad_shapes_return_false(monkeypatch):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(
            header_defs={"bit_fields": {}, "object_types": {}, "dtype": {}}
        ),
    )
    assert decoder._load_from_headers() is False


@pytest.mark.parametrize(
    "payload",
    [
        {
            "bit_fields": [],
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": [],
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": [],
            "proto_classes": {},
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": [],
            "prog_classes": {},
        },
        {
            "bit_fields": {},
            "object_types": {},
            "dtype": [],
            "io_classes": {},
            "proto_classes": {},
            "prog_classes": [],
        },
    ],
)
def test_objectid_load_from_headers_shape_guards(monkeypatch, payload):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(header_defs=payload),
    )
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_handles_exception(monkeypatch):
    decoder = blank_objectid_decoder()

    def _boom():
        raise headerdefs.HeaderDefsError("x")

    monkeypatch.setattr(
        objectid_mod.header_bundle, "load_header_bundle", _boom
    )
    assert decoder._load_from_headers() is False


def test_objectid_load_from_headers_success(monkeypatch):
    decoder = blank_objectid_decoder()
    monkeypatch.setattr(
        header_bundle_mod,
        "load_header_bundle",
        lambda: _definition_set(
            header_defs={
                "bit_fields": {
                    "type": {"shift": 30, "width": 2, "max": 3},
                    "cls": {"shift": 21, "width": 9, "max": 511},
                    "dtype": {"shift": 16, "width": 4, "max": 15},
                    "flags": {"shift": 14, "width": 2, "max": 3},
                    "priv": {"shift": 0, "width": 14, "max": 16383},
                    "ext": {"shift": 20, "width": 1, "max": 1},
                },
                "object_types": {1: "IO"},
                "dtype": [
                    "bad",
                    {"type": "ignored", "size": 0},
                    {"value": None, "type": "ignored2", "size": 0},
                    {"value": 1, "type": "bool", "size": 32},
                ],
                "io_classes": {5: "dummy"},
                "proto_classes": {17: "serial"},
                "prog_classes": {6: "sampling"},
            },
        ),
    )

    assert decoder._load_from_headers() is True
    assert decoder.TYPE_SHIFT == 30
    assert decoder.object_types[1] == "IO"
    assert decoder.dtype_info[1]["type"] == "bool"


def test_blocked_repo_root_lookup_fails_fast():
    from tests import conftest as test_fixtures

    with pytest.raises(pytest.fail.Exception):
        test_fixtures.blocked_repo_root_lookup()
