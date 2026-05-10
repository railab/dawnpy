# tools/dawnpy/tests/test_cli_table.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for CLI table helpers."""

from dawnpy.cli.table import print_table


def test_print_table_custom_printer(capsys):
    headers = ["a", "b"]
    rows = [["1", "two words"], ["", "x"]]

    def _printer(line: str) -> None:
        print(line)

    print_table(headers, rows, printer=_printer, max_width={"b": 4})
    out = capsys.readouterr().out
    assert "a | b" in out
    assert "-" in out
    assert "two" in out


def test_print_table_default_printer(capsys):
    headers = ["col"]
    rows = [["value"]]
    print_table(headers, rows)
    out = capsys.readouterr().out
    assert "col" in out
