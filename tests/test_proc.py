# tools/dawnpy/tests/test_proc.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tests for the subprocess helpers in dawnpy.dawn.proc."""

import subprocess

import pytest

from dawnpy.dawn.proc import run_capture, run_capture_echo, run_stream


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _calling_error(
    stdout: str = "", stderr: str = "", returncode: int = 1
) -> subprocess.CalledProcessError:
    err = subprocess.CalledProcessError(returncode, ["cmd"])
    err.stdout = stdout
    err.stderr = stderr
    return err


def test_run_capture_success_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout="ok")
    )
    result = run_capture(["cmd"])
    assert result is not None
    assert result.returncode == 0


def test_run_capture_echo_stdout_on_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout="hello\n")
    )
    assert run_capture(["cmd"], echo_stdout_on_success=True) is not None
    captured = capsys.readouterr()
    assert "hello" in captured.out


def test_run_capture_failure_with_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        raise _calling_error(stderr="boom-err")

    monkeypatch.setattr(subprocess, "run", boom)
    assert run_capture(["cmd"], error_message="step failed") is None
    captured = capsys.readouterr()
    assert "step failed" in captured.err
    assert "boom-err" in captured.err


def test_run_capture_failure_silent_when_no_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        raise _calling_error(stderr="ignored")

    monkeypatch.setattr(subprocess, "run", boom)
    assert run_capture(["cmd"]) is None
    captured = capsys.readouterr()
    assert "ignored" not in captured.err


def test_run_capture_echo_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _completed(stdout="out", stderr="err"),
    )
    assert run_capture_echo(["cmd"]) is True
    captured = capsys.readouterr()
    assert "out" in captured.out
    assert "err" in captured.err


def test_run_capture_echo_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(returncode=1)
    )
    assert run_capture_echo(["cmd"], error_message="bad") is False
    captured = capsys.readouterr()
    assert "bad" in captured.err


def test_run_capture_echo_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def kaboom(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        raise RuntimeError("ouch")

    monkeypatch.setattr(subprocess, "run", kaboom)
    assert run_capture_echo(["cmd"], error_message="step") is False
    captured = capsys.readouterr()
    assert "step" in captured.err
    assert "ouch" in captured.err


def test_run_stream_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed())
    assert run_stream(["cmd"]) is True


def test_run_stream_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(returncode=2)
    )
    assert run_stream(["cmd"], error_message="streamed bad") is False
    captured = capsys.readouterr()
    assert "streamed bad" in captured.err


def test_run_stream_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def kaboom(*a: object, **k: object) -> subprocess.CompletedProcess[str]:
        raise OSError("missing")

    monkeypatch.setattr(subprocess, "run", kaboom)
    assert run_stream(["cmd"], error_message="step") is False
    captured = capsys.readouterr()
    assert "step" in captured.err
    assert "missing" in captured.err
