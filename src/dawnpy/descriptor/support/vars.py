# tools/dawnpy/src/dawnpy/descriptor/vars.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor variable resolution with Kconfig integration."""

import ast
import os
import re
from pathlib import Path
from typing import Any, cast

import yaml

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_INCLUDE_PATTERN = re.compile(r'^#include\s+(?:"([^"]+)"|(\S+))\s*$')


def load_yaml_with_vars(
    yaml_path: str,
    kconfig_path: str | None = None,
    resolve_kconfig_values: bool = True,
    kconfig_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load descriptor YAML and resolve variables."""
    with open(yaml_path) as f:
        spec = yaml.safe_load(f) or {}
    if not isinstance(spec, dict):
        return {}
    return resolve_yaml_vars(
        spec,
        yaml_path,
        kconfig_path=kconfig_path,
        resolve_kconfig_values=resolve_kconfig_values,
        kconfig_overrides=kconfig_overrides,
    )


def resolve_yaml_vars(
    spec: dict[str, Any],
    yaml_path: str,
    kconfig_path: str | None = None,
    resolve_kconfig_values: bool = True,
    kconfig_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve vars in a descriptor spec."""
    vars_spec = spec.get("vars")
    if not isinstance(vars_spec, dict) or not vars_spec:
        unknown = _find_first_var_ref(spec)
        if unknown:
            raise ValueError(f"Unknown variable: {unknown}")
        return spec

    needs_kconfig = any(
        isinstance(value, dict) and value.get("kconfig")
        for value in vars_spec.values()
    )

    kconfig_values: dict[str, Any] = {}
    if needs_kconfig and resolve_kconfig_values:
        kconfig_file = _select_kconfig_path(yaml_path, kconfig_path)
        if kconfig_file:
            kconfig_values = _load_kconfig_values(kconfig_file)
        if kconfig_overrides:
            kconfig_values.update(kconfig_overrides)

    resolved_vars = _resolve_vars(
        vars_spec,
        kconfig_values,
        resolve_kconfig_values=resolve_kconfig_values,
    )
    return cast("dict[str, Any]", _substitute_node(spec, resolved_vars))


def _find_first_var_ref(node: Any) -> str | None:
    if isinstance(node, dict):
        for value in node.values():
            found = _find_first_var_ref(value)
            if found:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_first_var_ref(item)
            if found:
                return found
        return None
    if isinstance(node, str):
        match = _VAR_PATTERN.search(node)
        if match:
            return match.group(1)
    return None


def _select_kconfig_path(
    yaml_path: str, kconfig_path: str | None
) -> str | None:
    if kconfig_path:
        return kconfig_path

    env_path = os.environ.get("KCONFIG_CONFIG")
    if env_path and Path(env_path).exists():
        return env_path

    yaml_dir = Path(yaml_path).parent
    dot_config = yaml_dir / ".config"
    if dot_config.exists():
        return str(dot_config)

    defconfig = yaml_dir / "defconfig"
    if defconfig.exists():
        return str(defconfig)

    return None


def _load_kconfig_values(kconfig_path: str) -> dict[str, Any]:
    return _load_kconfig_values_recursive(Path(kconfig_path), set())


def _load_kconfig_values_recursive(
    kconfig_path: Path, visited: set[Path]
) -> dict[str, Any]:
    values: dict[str, Any] = {}

    resolved = kconfig_path.resolve()
    if resolved in visited:
        return values
    visited.add(resolved)

    with open(kconfig_path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            match = _INCLUDE_PATTERN.match(line)
            if match:
                include_name = match.group(1) or match.group(2)
                include_path = kconfig_path.parent / include_name
                if include_path.exists():
                    include_values = _load_kconfig_values_recursive(
                        include_path, visited
                    )
                    values.update(include_values)
                continue

            if line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if not key.startswith("CONFIG_"):
                continue
            values[key] = _parse_kconfig_value(raw_value.strip())
    return values


def _parse_kconfig_value(raw_value: str) -> Any:
    if raw_value.startswith('"') and raw_value.endswith('"'):
        return raw_value[1:-1]
    if raw_value in ("y", "n"):
        return raw_value == "y"
    try:
        return int(raw_value, 0)
    except ValueError:
        return raw_value


def _resolve_vars(
    vars_spec: dict[str, Any],
    kconfig_values: dict[str, Any],
    resolve_kconfig_values: bool,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}

    for name, var_def in vars_spec.items():
        if isinstance(var_def, dict):
            value = _resolve_var_from_dict(
                name,
                var_def,
                kconfig_values,
                resolve_kconfig_values=resolve_kconfig_values,
            )
        else:
            value = var_def
        resolved[name] = value

    return resolved


def _resolve_var_from_dict(
    name: str,
    var_def: dict[str, Any],
    kconfig_values: dict[str, Any],
    resolve_kconfig_values: bool,
) -> Any:
    value: Any = None
    if "kconfig" in var_def:
        if "default" in var_def:
            raise ValueError(f"Kconfig var {name} should not define default")
        symbol = str(var_def.get("kconfig"))
        if not resolve_kconfig_values:
            return symbol
        if symbol in kconfig_values:
            value = kconfig_values[symbol]
        else:
            return symbol
    elif "value" in var_def:
        value = var_def.get("value")
    elif "default" in var_def:
        value = var_def.get("default")
    else:
        raise ValueError(f"Variable {name} has no value or default")

    return _coerce_type(value, var_def.get("type"))


def _coerce_type(value: Any, type_name: str | None) -> Any:
    if type_name is None:
        return value

    type_name = str(type_name).lower()
    if type_name in ("int", "hex"):
        return _to_int(value)
    if type_name == "bool":
        return _to_bool(value)
    if type_name == "string":
        return str(value)

    raise ValueError(f"Unsupported var type: {type_name}")


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"Cannot convert {value!r} to int")


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        value_lc = value.strip().lower()
        if value_lc in ("y", "yes", "true", "1"):
            return True
        if value_lc in ("n", "no", "false", "0"):
            return False
    raise ValueError(f"Cannot convert {value!r} to bool")


def _substitute_node(node: Any, vars_map: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        resolved: dict[str, Any] = {}
        for key, value in node.items():
            if key == "vars":
                resolved[key] = value
            else:
                resolved[key] = _substitute_node(value, vars_map)
        return resolved
    if isinstance(node, list):
        return [_substitute_node(item, vars_map) for item in node]
    if isinstance(node, str):
        return _resolve_string(node, vars_map)
    return node


def _resolve_string(value: str, vars_map: dict[str, Any]) -> Any:
    if not _VAR_PATTERN.search(value):
        return value

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in vars_map:
            raise ValueError(f"Unknown variable: {name}")
        return str(vars_map[name])

    substituted = _VAR_PATTERN.sub(replace, value)
    evaluated = _eval_expression(substituted)
    if evaluated is None:
        return substituted
    return evaluated


def _eval_expression(expr: str) -> int | None:
    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    try:
        return _eval_ast(parsed)
    except ValueError:
        return None


def _eval_ast(node: ast.AST) -> int:  # noqa: C901
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp):
        unary_op = node.op
        operand = _eval_ast(node.operand)
        if isinstance(unary_op, ast.UAdd):
            return +operand
        if isinstance(unary_op, ast.USub):
            return -operand
        raise ValueError("Unsupported unary op")
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        bin_op = node.op
        if isinstance(bin_op, ast.Add):
            return left + right
        if isinstance(bin_op, ast.Sub):
            return left - right
        if isinstance(bin_op, ast.Mult):
            return left * right
        if isinstance(bin_op, ast.FloorDiv):
            return left // right
        if isinstance(bin_op, ast.Mod):
            return left % right
        if isinstance(bin_op, ast.LShift):
            return left << right
        if isinstance(bin_op, ast.RShift):
            return left >> right
        if isinstance(bin_op, ast.BitOr):
            return left | right
        if isinstance(bin_op, ast.BitAnd):
            return left & right
        if isinstance(bin_op, ast.BitXor):
            return left ^ right
        raise ValueError("Unsupported binary op")
    raise ValueError("Unsupported expression")
