# tools/dawnpy/src/dawnpy/templates.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Discovery and rendering of bundled dawnpy templates.

Templates are grouped by *kind* so the tooling can host more than one
flavour without callers having to know the on-disk layout:

* :data:`PROJECT_KIND` (``"project"``) - full out-of-tree Dawn project
  scaffolds rendered as a directory tree (e.g. ``minimal-sim``).
* :data:`DEVICE_KIND` (``"device"``) - YAML descriptor templates for
  individual devices. Reserved for future use; declared here so that
  enumeration, lookup, and rendering already work uniformly.

On disk:

.. code-block:: text

    templates/
        index.toml          # one TOML section per kind
        project/<name>/...  # rendered by `dawnpy project new`
        device/<name>/...   # future
"""

import tomllib
from importlib import resources
from pathlib import Path
from string import Template

PROJECT_KIND = "project"
DEVICE_KIND = "device"

_KNOWN_KINDS: tuple[str, ...] = (PROJECT_KIND, DEVICE_KIND)


class UnknownTemplateKindError(ValueError):
    """Raised when a caller passes an unrecognised template kind."""


class UnknownTemplateError(ValueError):
    """Raised when a caller asks for a template that does not exist."""


def known_kinds() -> tuple[str, ...]:
    """Return all template kinds the tooling currently understands."""
    return _KNOWN_KINDS


def templates_root() -> Path:
    """Return the root directory containing every bundled template."""
    return Path(str(resources.files("dawnpy").joinpath("templates")))


def _manifest_path() -> Path:
    return templates_root() / "index.toml"


def _check_kind(kind: str) -> None:
    if kind not in _KNOWN_KINDS:
        raise UnknownTemplateKindError(
            f"Unknown template kind: {kind!r} "
            f"(expected one of {_KNOWN_KINDS})"
        )


def _load_manifest() -> dict[str, dict[str, str]]:
    """Parse ``index.toml`` into a ``{kind: {name: description}}`` mapping."""
    with _manifest_path().open("rb") as handle:
        data = tomllib.load(handle)

    parsed: dict[str, dict[str, str]] = {}
    for kind in _KNOWN_KINDS:
        section = data.get(kind, {})
        if not isinstance(section, dict):
            section = {}
        parsed[kind] = {str(k): str(v) for k, v in section.items()}
    return parsed


def list_templates(kind: str) -> dict[str, str]:
    """Return ``{name: description}`` for every template of ``kind``."""
    _check_kind(kind)
    return _load_manifest()[kind]


def template_dir(kind: str, name: str) -> Path:
    """Return the on-disk directory for a single template.

    :raises UnknownTemplateKindError: if ``kind`` is not registered.
    :raises UnknownTemplateError: if no such template exists on disk.
    """
    _check_kind(kind)
    path = templates_root() / kind / name
    if not path.is_dir():
        raise UnknownTemplateError(f"Unknown {kind} template: {name}")
    return path


def render_tree(
    *,
    kind: str,
    name: str,
    target_root: Path,
    substitutions: dict[str, str],
) -> None:
    """Render template ``name`` of ``kind`` into ``target_root``.

    Each file in the template is treated as a :class:`string.Template`
    and rendered with ``substitutions`` (missing keys are left intact
    via :meth:`~string.Template.safe_substitute`). Directory structure
    is preserved verbatim. Python bytecode artefacts (``__pycache__``,
    ``*.pyc``, ``*.pyo``) are skipped so editable installs stay clean.

    :param kind: template kind (see :func:`known_kinds`).
    :param name: template name within that kind.
    :param target_root: destination directory; created on demand.
    :param substitutions: ``$NAME`` placeholders to substitute.
    """
    template_root = template_dir(kind, name)
    for source_path in template_root.rglob("*"):
        relative_path = source_path.relative_to(template_root)
        if any(part == "__pycache__" for part in relative_path.parts):
            continue
        if source_path.suffix in {".pyc", ".pyo"}:
            continue
        target_path = target_root / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        rendered = Template(
            source_path.read_text(encoding="utf-8")
        ).safe_substitute(substitutions)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(rendered, encoding="utf-8")
