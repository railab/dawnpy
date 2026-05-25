# tools/dawnpy/src/dawnpy/descriptor/vars.py
#
# SPDX-License-Identifier: Apache-2.0
#

"""Descriptor variable resolution with Kconfig integration."""

from __future__ import annotations

import ast
import copy
import os
import re
from pathlib import Path
from typing import Any, cast

import yaml

from dawnpy.descriptor.support.utils import resolve_reference

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_INCLUDE_PATTERN = re.compile(r'^#include\s+(?:"([^"]+)"|(\S+))\s*$')
_INCLUDE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INPUT_TOKEN_PREFIX = "@INPUTS."


def load_yaml_with_vars(
    yaml_path: str,
    kconfig_path: str | None = None,
    resolve_kconfig_values: bool = True,
    kconfig_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load descriptor YAML, resolve variables, and expand includes."""
    return _load_yaml_with_vars_recursive(
        Path(yaml_path),
        kconfig_path=kconfig_path,
        resolve_kconfig_values=resolve_kconfig_values,
        kconfig_overrides=kconfig_overrides,
        include_stack=(),
    )


def _load_yaml_with_vars_recursive(
    yaml_path: Path,
    *,
    kconfig_path: str | None,
    resolve_kconfig_values: bool,
    kconfig_overrides: dict[str, Any] | None,
    include_stack: tuple[Path, ...],
) -> dict[str, Any]:
    resolved_path = yaml_path.resolve()
    if resolved_path in include_stack:
        cycle = " -> ".join(
            [str(path) for path in (*include_stack, resolved_path)]
        )
        raise ValueError(f"Descriptor include cycle detected: {cycle}")

    spec = _load_yaml_mapping(yaml_path)
    if not spec:
        return {}

    resolved_spec = resolve_yaml_vars(
        spec,
        str(yaml_path),
        kconfig_path=kconfig_path,
        resolve_kconfig_values=resolve_kconfig_values,
        kconfig_overrides=kconfig_overrides,
    )
    return _expand_yaml_includes(
        resolved_spec,
        yaml_path,
        kconfig_path=kconfig_path,
        resolve_kconfig_values=resolve_kconfig_values,
        kconfig_overrides=kconfig_overrides,
        include_stack=(*include_stack, resolved_path),
    )


def _load_yaml_mapping(yaml_path: Path) -> dict[str, Any]:
    with open(yaml_path) as f:
        spec = yaml.safe_load(f) or {}
    if not isinstance(spec, dict):
        return {}
    return cast("dict[str, Any]", spec)


def _expand_yaml_includes(
    spec: dict[str, Any],
    yaml_path: Path,
    *,
    kconfig_path: str | None,
    resolve_kconfig_values: bool,
    kconfig_overrides: dict[str, Any] | None,
    include_stack: tuple[Path, ...],
) -> dict[str, Any]:
    if _is_multi_descriptor_spec(spec):
        expanded: dict[str, Any] = {}
        for key, value in spec.items():
            if key.startswith("descriptor") and isinstance(value, dict):
                expanded[key] = _expand_single_descriptor_includes(
                    value,
                    yaml_path,
                    kconfig_path=kconfig_path,
                    resolve_kconfig_values=resolve_kconfig_values,
                    kconfig_overrides=kconfig_overrides,
                    include_stack=include_stack,
                )
            else:
                expanded[key] = value
        return expanded

    return _expand_single_descriptor_includes(
        spec,
        yaml_path,
        kconfig_path=kconfig_path,
        resolve_kconfig_values=resolve_kconfig_values,
        kconfig_overrides=kconfig_overrides,
        include_stack=include_stack,
    )


def _is_multi_descriptor_spec(spec: dict[str, Any]) -> bool:
    return "descriptor0" in spec


def _expand_single_descriptor_includes(  # noqa: C901
    spec: dict[str, Any],
    yaml_path: Path,
    *,
    kconfig_path: str | None,
    resolve_kconfig_values: bool,
    kconfig_overrides: dict[str, Any] | None,
    include_stack: tuple[Path, ...],
) -> dict[str, Any]:
    includes = spec.get("includes", [])
    if includes is None:
        includes = []
    if not isinstance(includes, list):
        raise ValueError(f"{yaml_path}: includes must be a list")

    if not includes:
        result = copy.deepcopy(spec)
        _ensure_unique_object_ids(result, yaml_path)
        return result

    expanded_ios: list[Any] = []
    expanded_programs: list[Any] = []
    expanded_protocols: list[Any] = []
    output_refs: dict[str, str] = {}
    include_ids: set[str] = set()

    for include_index, include_spec in enumerate(includes):
        include_id, include_file, include_inputs = _parse_include_entry(
            include_spec, yaml_path, include_index
        )
        if include_id in include_ids:
            raise ValueError(
                f"{yaml_path}: duplicate include id '{include_id}'"
            )
        include_ids.add(include_id)

        include_inputs = cast(
            "dict[str, Any]",
            _substitute_exact_strings(include_inputs, output_refs),
        )
        unresolved_input_ref = _find_first_named_output_token(include_inputs)
        if unresolved_input_ref is not None:
            raise ValueError(
                f"{yaml_path}: unknown include output reference "
                f"'{unresolved_input_ref}'"
            )

        block_spec = _load_yaml_with_vars_recursive(
            include_file,
            kconfig_path=kconfig_path,
            resolve_kconfig_values=resolve_kconfig_values,
            kconfig_overrides=kconfig_overrides,
            include_stack=include_stack,
        )
        instance_spec, instance_outputs = _instantiate_include_block(
            block_spec,
            namespace=include_id,
            provided_inputs=include_inputs,
            include_file=include_file,
        )

        expanded_ios.extend(instance_spec["ios"])
        expanded_programs.extend(instance_spec["programs"])
        expanded_protocols.extend(instance_spec["protocols"])
        for output_name, output_ref in instance_outputs.items():
            output_refs[f"@{include_id}.{output_name}"] = output_ref

    result = copy.deepcopy(spec)
    result.pop("includes", None)
    result["ios"] = expanded_ios + _list_section(result.get("ios"), "ios")
    result["programs"] = expanded_programs + _list_section(
        result.get("programs"), "programs"
    )
    result["protocols"] = expanded_protocols + _list_section(
        result.get("protocols"), "protocols"
    )
    if "outputs" in result:
        result["outputs"] = _substitute_exact_strings(
            result["outputs"], output_refs
        )
    for section in ("ios", "programs", "protocols"):
        result[section] = _substitute_exact_strings(
            result[section], output_refs
        )

    unresolved_ref = _find_first_named_output_token(
        {
            "ios": result["ios"],
            "programs": result["programs"],
            "protocols": result["protocols"],
            "outputs": result.get("outputs", []),
        }
    )
    if unresolved_ref is not None:
        raise ValueError(
            f"{yaml_path}: unknown include output reference "
            f"'{unresolved_ref}'"
        )

    _ensure_unique_object_ids(result, yaml_path)
    return result


def _instantiate_include_block(  # noqa: C901
    block_spec: dict[str, Any],
    *,
    namespace: str,
    provided_inputs: dict[str, Any],
    include_file: Path,
) -> tuple[dict[str, list[Any]], dict[str, str]]:
    if not _INCLUDE_ID_PATTERN.match(namespace):
        raise ValueError(
            f"{include_file}: include id '{namespace}' is invalid; "
            "use [A-Za-z_][A-Za-z0-9_]*"
        )

    declared_inputs = _parse_block_inputs(
        block_spec.get("inputs"), include_file
    )
    declared_outputs = _parse_block_outputs(
        block_spec.get("outputs"), include_file
    )

    unexpected_inputs = sorted(set(provided_inputs) - set(declared_inputs))
    if unexpected_inputs:
        joined = ", ".join(unexpected_inputs)
        raise ValueError(f"{include_file}: unknown block inputs: {joined}")

    missing_inputs = [
        name for name in declared_inputs if name not in provided_inputs
    ]
    if missing_inputs:
        joined = ", ".join(missing_inputs)
        raise ValueError(f"{include_file}: missing block inputs: {joined}")

    instance_spec = {
        "ios": copy.deepcopy(_list_section(block_spec.get("ios"), "ios")),
        "programs": copy.deepcopy(
            _list_section(block_spec.get("programs"), "programs")
        ),
        "protocols": copy.deepcopy(
            _list_section(block_spec.get("protocols"), "protocols")
        ),
    }

    input_map = {
        f"{_INPUT_TOKEN_PREFIX}{name}": _normalize_interface_ref(
            value, include_file
        )
        for name, value in provided_inputs.items()
    }
    instance_spec = cast(
        "dict[str, list[Any]]",
        _substitute_exact_strings(instance_spec, input_map),
    )

    unresolved_input = _find_first_input_token(instance_spec)
    if unresolved_input is not None:
        raise ValueError(
            f"{include_file}: unresolved block input reference "
            f"'{unresolved_input}'"
        )

    unresolved_output = _find_first_named_output_token(instance_spec)
    if unresolved_output is not None:
        raise ValueError(
            f"{include_file}: unknown include output reference "
            f"'{unresolved_output}'"
        )

    object_ids = set(_collect_object_ids(instance_spec))
    resolved_outputs: dict[str, str] = {}
    promoted_ids: dict[str, str] = {}

    for output_name, output_ref in declared_outputs.items():
        resolved_ref = _normalize_interface_ref(
            _substitute_exact_strings(output_ref, input_map),
            include_file,
        )
        if _is_named_output_token(resolved_ref):
            raise ValueError(
                f"{include_file}: unknown include output reference "
                f"'{resolved_ref}'"
            )
        resolved_outputs[output_name] = resolved_ref

        if resolved_ref not in object_ids:
            continue

        previous_name = promoted_ids.get(resolved_ref)
        if previous_name is not None and previous_name != output_name:
            raise ValueError(
                f"{include_file}: internal object '{resolved_ref}' is "
                "exported more than once"
            )
        promoted_ids[resolved_ref] = output_name

    id_map = {
        obj_id: promoted_ids.get(obj_id, f"{namespace}__{obj_id}")
        for obj_id in object_ids
    }
    instance_spec = cast(
        "dict[str, list[Any]]",
        _substitute_exact_strings(instance_spec, id_map),
    )

    exports: dict[str, str] = {}
    for output_name, resolved_ref in resolved_outputs.items():
        if resolved_ref in object_ids:
            exports[output_name] = output_name
        else:
            exports[output_name] = resolved_ref

    _ensure_unique_object_ids(instance_spec, include_file)
    return instance_spec, exports


def _parse_include_entry(
    include_spec: Any,
    yaml_path: Path,
    include_index: int,
) -> tuple[str, Path, dict[str, Any]]:
    if not isinstance(include_spec, dict):
        raise ValueError(
            f"{yaml_path}: includes[{include_index}] must be a mapping"
        )

    include_id = include_spec.get("id")
    if not include_id:
        raise ValueError(
            f"{yaml_path}: includes[{include_index}] is missing id"
        )

    path_value = include_spec.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError(
            f"{yaml_path}: includes[{include_index}] is missing path"
        )

    inputs = include_spec.get("inputs", {})
    if inputs is None:
        inputs = {}
    if not isinstance(inputs, dict):
        raise ValueError(
            f"{yaml_path}: includes[{include_index}].inputs must be a mapping"
        )

    include_file = (yaml_path.parent / path_value).resolve()
    if not include_file.exists():
        raise ValueError(f"{yaml_path}: include path '{path_value}' not found")

    return str(include_id), include_file, cast("dict[str, Any]", inputs)


def _parse_block_inputs(spec: Any, include_file: Path) -> list[str]:
    if spec is None:
        return []
    if not isinstance(spec, list):
        raise ValueError(f"{include_file}: inputs must be a list")

    inputs: list[str] = []
    for index, entry in enumerate(spec):
        if isinstance(entry, str):
            input_name = entry
        elif isinstance(entry, dict):
            input_name = str(entry.get("id", ""))
        else:
            raise ValueError(
                f"{include_file}: inputs[{index}] must be a string or mapping"
            )
        if not input_name:
            raise ValueError(f"{include_file}: inputs[{index}] is missing id")
        inputs.append(input_name)
    return inputs


def _parse_block_outputs(spec: Any, include_file: Path) -> dict[str, str]:
    if spec is None:
        return {}

    outputs: dict[str, str] = {}
    if isinstance(spec, dict):
        for output_name, output_ref in spec.items():
            outputs[str(output_name)] = _normalize_interface_ref(
                output_ref, include_file
            )
        return outputs

    if not isinstance(spec, list):
        raise ValueError(f"{include_file}: outputs must be a list or mapping")

    for index, entry in enumerate(spec):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{include_file}: outputs[{index}] must be a mapping"
            )
        output_name = str(entry.get("id", ""))
        if not output_name:
            raise ValueError(f"{include_file}: outputs[{index}] is missing id")
        if output_name in outputs:
            raise ValueError(
                f"{include_file}: outputs[{index}] duplicates id "
                f"'{output_name}'"
            )
        if "ref" not in entry:
            raise ValueError(
                f"{include_file}: outputs[{index}] is missing ref"
            )
        outputs[output_name] = _normalize_interface_ref(
            entry["ref"], include_file
        )
    return outputs


def _normalize_interface_ref(value: Any, include_file: Path) -> str:
    resolved = resolve_reference(value)
    if resolved is None or not resolved:
        raise ValueError(f"{include_file}: interface reference is invalid")
    return str(resolved)


def _list_section(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Descriptor section '{name}' must be a list")
    return value


def _substitute_exact_strings(node: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {
            key: _substitute_exact_strings(value, replacements)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_substitute_exact_strings(item, replacements) for item in node]
    if isinstance(node, str):
        return replacements.get(node, node)
    return node


def _find_first_input_token(node: Any) -> str | None:
    if isinstance(node, dict):
        for value in node.values():
            found = _find_first_input_token(value)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_first_input_token(item)
            if found is not None:
                return found
        return None
    if isinstance(node, str) and node.startswith(_INPUT_TOKEN_PREFIX):
        return node
    return None


def _find_first_named_output_token(node: Any) -> str | None:
    if isinstance(node, dict):
        for value in node.values():
            found = _find_first_named_output_token(value)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_first_named_output_token(item)
            if found is not None:
                return found
        return None
    if isinstance(node, str) and _is_named_output_token(node):
        return node
    return None


def _is_named_output_token(value: str) -> bool:
    return value.startswith("@") and not value.startswith(_INPUT_TOKEN_PREFIX)


def _collect_object_ids(spec: dict[str, Any]) -> list[str]:
    object_ids: list[str] = []
    for section in ("ios", "programs", "protocols"):
        for entry in spec.get(section, []):
            if not isinstance(entry, dict):
                continue
            object_id = entry.get("id")
            if object_id is None:
                continue
            object_ids.append(str(object_id))
    return object_ids


def _ensure_unique_object_ids(spec: dict[str, Any], yaml_path: Path) -> None:
    seen: set[str] = set()
    for object_id in _collect_object_ids(spec):
        if object_id in seen:
            raise ValueError(
                f"{yaml_path}: duplicate object id '{object_id}' "
                "after include expansion"
            )
        seen.add(object_id)


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
