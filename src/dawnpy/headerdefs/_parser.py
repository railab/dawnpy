# tools/dawnpy/src/dawnpy/headerdefs/_parser.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Tree-sitter C++ parsing primitives + cpp-int expression evaluator."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._paths import HeaderDefsError

tree_sitter: Any
tree_sitter_cpp: Any
try:
    import tree_sitter as _tree_sitter
    import tree_sitter_cpp as _tree_sitter_cpp

    tree_sitter = _tree_sitter
    tree_sitter_cpp = _tree_sitter_cpp
except ImportError:
    tree_sitter = None
    tree_sitter_cpp = None


def _eval_cpp_int(expr: str, symbols: dict[str, int]) -> int:
    """Evaluate a constrained integer C/C++ expression."""
    normalized = expr.strip()
    normalized = re.sub(
        r"\b(static_cast|reinterpret_cast|const_cast)\s*<[^>]+>",
        "",
        normalized,
    )
    # Strip integer literal suffixes without altering identifier tokens.
    normalized = re.sub(
        r"(?<=[0-9a-fA-F])(?:ULL|LLU|UL|LU|LL|U|L)\b",
        "",
        normalized,
    )

    for name, value in sorted(symbols.items(), key=lambda item: -len(item[0])):
        normalized = re.sub(rf"\b{re.escape(name)}\b", str(value), normalized)

    if not re.fullmatch(r"[0-9a-fA-FxXbB_()+\-*/%<>&|~ \t\n\r]+", normalized):
        raise HeaderDefsError(f"Unsupported expression: {expr}")

    try:
        result = eval(normalized, {"__builtins__": None}, {})  # noqa: S307
    except Exception as exc:  # pragma: no cover - defensive
        raise HeaderDefsError(
            f"Failed to evaluate expression '{expr}'"
        ) from exc

    return int(result)


@lru_cache(maxsize=1)
def _cpp_parser() -> Any:
    """Return configured tree-sitter C++ parser."""
    if tree_sitter is None or tree_sitter_cpp is None:
        raise HeaderDefsError(
            "tree-sitter parser unavailable; install tree-sitter packages"
        )
    language = tree_sitter.Language(tree_sitter_cpp.language())
    parser = tree_sitter.Parser(language)
    return parser


def _iter_ts_nodes(root: Any) -> list[Any]:
    """Return tree-sitter nodes in pre-order traversal."""
    out: list[Any] = []
    stack = [root]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(list(node.children)))
    return out


def _ts_text(node: Any, source: bytes) -> str:
    """Decode node slice from source bytes."""
    return source[node.start_byte : node.end_byte].decode(
        "utf-8", errors="ignore"
    )


def _normalize_preprocessed_cpp(text: str) -> str:
    """Drop preprocessor markers and normalize enum typedef form."""
    without_markers = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    return re.sub(
        r"\}\s*typedef\s+([A-Za-z_][A-Za-z0-9_]*)\s*;",
        r"} \1;",
        without_markers,
    )


def _is_constexpr_static_field(node: Any, source: bytes) -> bool:
    """Return True when field declaration contains constexpr static markers."""
    if node.type != "field_declaration":
        return False
    child_types = [child.type for child in node.children]
    if "type_qualifier" not in child_types:
        return False
    if "storage_class_specifier" not in child_types:
        return False
    text = _ts_text(node, source)
    return "constexpr" in text and "static" in text


def _field_name_and_expr(node: Any, source: bytes) -> tuple[str | None, str]:
    """Extract field identifier and initializer expression text."""
    field_name: str | None = None
    for child in node.children:
        if child.type == "field_identifier":
            field_name = _ts_text(child, source).strip()
    expr = _rhs_expr_from_node(node, source, terminator=";")
    return field_name, expr


def _enumerator_name_and_expr(
    node: Any, source: bytes
) -> tuple[str | None, str]:
    """Extract enumerator identifier and value expression."""
    enum_name: str | None = None
    for child in node.children:
        if child.type == "identifier" and enum_name is None:
            enum_name = _ts_text(child, source).strip()
    enum_expr = _rhs_expr_from_node(node, source, terminator=",")
    return enum_name, enum_expr


def _rhs_expr_from_node(node: Any, source: bytes, terminator: str) -> str:
    """Return expression text between '=' and node terminator."""
    eq_end: int | None = None
    term_start: int | None = None
    for child in node.children:
        if child.type == "=":
            eq_end = child.end_byte
            continue
        if child.type == terminator:
            term_start = child.start_byte
            break
    if eq_end is None:
        return ""
    end = term_start if term_start is not None else node.end_byte
    if end <= eq_end:
        return ""
    return source[eq_end:end].decode("utf-8", errors="ignore").strip()


def _first_ts_error_node(root: Any) -> Any | None:
    """Return first tree-sitter error node if present."""
    for node in _iter_ts_nodes(root):
        if getattr(node, "type", None) == "ERROR":
            return node
    return None


def _has_extractable_nodes(root: Any) -> bool:
    """Return True when AST has nodes we can extract definitions from."""
    for node in _iter_ts_nodes(root):
        if getattr(node, "type", None) in (
            "field_declaration",
            "enumerator",
        ):
            return True
    return False


def _parse_cpp_header(header: Path) -> tuple[bytes, Any]:
    """Parse a C++ header with tree-sitter without preprocessing."""
    source = header.read_bytes()
    tree = _cpp_parser().parse(source)
    root = tree.root_node
    has_error = bool(getattr(root, "has_error", False))
    if has_error and not _has_extractable_nodes(root):
        err_node = _first_ts_error_node(root)
        if err_node is not None:
            line = err_node.start_point[0] + 1
            col = err_node.start_point[1] + 1
            raise HeaderDefsError(
                f"Header parse error in {header}:{line}:{col}"
            )
        raise HeaderDefsError(f"Header parse error in {header}")
    return source, root


def _extract_constexpr_values_from_tree(
    source: bytes, root: Any
) -> dict[str, int]:
    """Extract constexpr static fields from C++ tree-sitter AST."""
    out: dict[str, int] = {}
    for node in _iter_ts_nodes(root):
        if not _is_constexpr_static_field(node, source):
            continue
        field_name, expr = _field_name_and_expr(node, source)
        if (
            not isinstance(field_name, str)
            or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", field_name)
            or not expr
        ):
            continue
        try:
            out[field_name] = _eval_cpp_int(expr, out)
        except HeaderDefsError:
            continue
    return out


def _extract_enum_constants_from_tree(
    source: bytes, root: Any, prefixes: tuple[str, ...]
) -> dict[str, int]:
    """Extract enum constants filtered by prefixes from AST."""
    out: dict[str, int] = {}
    current_value: int | None = None
    for node in _iter_ts_nodes(root):
        if node.type != "enumerator":
            continue
        enum_name, enum_expr = _enumerator_name_and_expr(node, source)
        if not isinstance(enum_name, str):
            continue
        if not any(enum_name.startswith(prefix) for prefix in prefixes):
            continue
        if enum_expr:
            try:
                current_value = _eval_cpp_int(enum_expr, out)
                out[enum_name] = current_value
                continue
            except HeaderDefsError:
                pass
        if current_value is None:
            current_value = 0
        else:
            current_value += 1
        out[enum_name] = current_value
    return out
