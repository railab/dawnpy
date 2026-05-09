# dawnpy

Core Python tooling for Dawn.

Main Dawn project: [railab/dawn](https://github.com/railab/dawn).

`dawnpy` owns:

- repository and build helpers
- descriptor parsing, validation, and generation
- object ID decoding
- shared device/runtime helpers used by other Dawn Python packages

Transport clients and the project QA runner are split into separate packages:

- `dawnpy-serial`
- `dawnpy-can`
- `dawnpy-udp`
- `dawnpy-modbus`
- `dawnpy-tests`

## Install

Dawnpy can be installed by running `pip install dawnpy`.

To install latest development version, use:

`pip install git+https://github.com/railab/dawnpy.git`

Or install directly from Dawn project sources:

```sh
cd tools/dawnpy
pip install -e .
```

## Core Commands

Show help:

```sh
python -m dawnpy --help
```

Validate a descriptor config:

```sh
python -m dawnpy desc-valid boards/sim/sim/sim/configs/nsh_tests
```

Generate descriptor C++ from YAML:

```sh
python -m dawnpy desc-gen descriptor.yaml
```

Build a board/config:

```sh
python -m dawnpy build sim/sim/sim:nsh_tests
```

Build a batch of configs:

```sh
python -m dawnpy batch tools/config-build-all.txt
```

## Development

Run the core package QA locally:

```sh
cd tools/dawnpy
tox -e py
tox -e format
tox -e flake8
tox -e type
```

Unit tests must be runnable from the standalone `dawnpy` repository without
the Dawn source tree checked out. Tests that exercise source-backed behavior
should heavily mock Dawn source discovery and header loading, or build minimal
fake Dawn source/header layouts inside temporary directories, instead of
reading real Dawn sources.

## Documentation

See [Dawn Python tooling](https://railab.github.io/dawn/tools/dawnpy.html)
for the full Dawn Python tooling documentation.
