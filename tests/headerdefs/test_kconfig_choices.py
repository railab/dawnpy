#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for Kconfig choice extraction used by descriptor validation."""

from __future__ import annotations

from dawnpy.headerdefs._kconfig import (
    _scan_choices,
    implicit_choice_configs,
)

NIMBLE_KCONFIG = """
config DAWN_PROTO_NIMBLE
\tbool "Dawn NimBLE support"

if DAWN_PROTO_NIMBLE

choice
\tprompt "Dawn NimBLE role"
\tdefault DAWN_PROTO_NIMBLE_PERIPHERAL

config DAWN_PROTO_NIMBLE_PERIPHERAL
\tbool "Dawn NimBLE peripheral"

config DAWN_PROTO_NIMBLE_CENTRAL
\tbool "Dawn NimBLE central"

endchoice

endif
"""


def test_scan_choices_captures_default_members_and_guard() -> None:
    """A guarded choice yields its default, members and enclosing if."""
    default, members, guards = _scan_choices(NIMBLE_KCONFIG)[0]

    assert default == "CONFIG_DAWN_PROTO_NIMBLE_PERIPHERAL"
    assert members == (
        "CONFIG_DAWN_PROTO_NIMBLE_PERIPHERAL",
        "CONFIG_DAWN_PROTO_NIMBLE_CENTRAL",
    )
    assert guards == ("CONFIG_DAWN_PROTO_NIMBLE",)


def test_default_applies_when_guard_enabled() -> None:
    """Kconfig sets the default, so it need not be in the defconfig."""
    choices = tuple(_scan_choices(NIMBLE_KCONFIG))
    implicit = implicit_choice_configs({"CONFIG_DAWN_PROTO_NIMBLE"}, choices)

    assert implicit == {"CONFIG_DAWN_PROTO_NIMBLE_PERIPHERAL"}


def test_default_skipped_when_guard_disabled() -> None:
    """An unreachable choice must not enable anything."""
    choices = tuple(_scan_choices(NIMBLE_KCONFIG))

    assert implicit_choice_configs(set(), choices) == set()


def test_default_skipped_when_sibling_selected() -> None:
    """An explicit sibling selection wins over the default."""
    choices = tuple(_scan_choices(NIMBLE_KCONFIG))
    enabled = {
        "CONFIG_DAWN_PROTO_NIMBLE",
        "CONFIG_DAWN_PROTO_NIMBLE_CENTRAL",
    }

    assert implicit_choice_configs(enabled, choices) == set()


def test_choice_without_default_is_ignored() -> None:
    """Choices carrying no default contribute nothing."""
    text = 'choice\n\tprompt "x"\nconfig A\n\tbool\nendchoice\n'

    assert _scan_choices(text) == []


def test_loader_walks_dawn_kconfig_tree(tmp_path, monkeypatch) -> None:
    """The loader collects choices from every Kconfig under dawn/."""
    import dawnpy.headerdefs._kconfig as kconfig_mod

    kconfig_dir = tmp_path / "dawn" / "src" / "proto"
    kconfig_dir.mkdir(parents=True)
    (kconfig_dir / "Kconfig").write_text(NIMBLE_KCONFIG, encoding="utf-8")
    # An unreadable path must be skipped rather than abort the walk.
    (tmp_path / "dawn" / "Kconfig").mkdir()

    monkeypatch.setattr(kconfig_mod, "_require_repo_root", lambda: tmp_path)
    kconfig_mod.load_header_kconfig_choices.cache_clear()
    try:
        choices = kconfig_mod.load_header_kconfig_choices()
    finally:
        kconfig_mod.load_header_kconfig_choices.cache_clear()

    assert choices == (
        (
            "CONFIG_DAWN_PROTO_NIMBLE_PERIPHERAL",
            (
                "CONFIG_DAWN_PROTO_NIMBLE_PERIPHERAL",
                "CONFIG_DAWN_PROTO_NIMBLE_CENTRAL",
            ),
            ("CONFIG_DAWN_PROTO_NIMBLE",),
        ),
    )
