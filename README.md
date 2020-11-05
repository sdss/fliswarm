# fliswarm

![Versions](https://img.shields.io/badge/python->3.8-blue)
[![Documentation Status](https://readthedocs.org/projects/sdss-fliswarm/badge/?version=latest)](https://sdss-fliswarm.readthedocs.io/en/latest/?badge=latest)
[![Build](https://img.shields.io/github/workflow/status/sdss/fliswarm/Test)](https://github.com/sdss/fliswarm/actions)
[![codecov](https://codecov.io/gh/sdss/fliswarm/branch/main/graph/badge.svg)](https://codecov.io/gh/sdss/fliswarm)

A tool to create and manage Docker instances of [flicamera](https://github.org/sdss/flicamera).

## Installation

You can install ``fliswarm`` by doing

```console
pip install sdss-fliswarm
```

To build from source, use

```console
git clone git@github.com:sdss/fliswarm
cd fliswarm
pip install .
```

## Development

`fliswarm` uses [poetry](http://poetry.eustace.io/) for dependency management and packaging. To work with an editable install it's recommended that you setup `poetry` and install `fliswarm` in a virtual environment by doing

```console
poetry install
```

Pip does not support editable installs with PEP-517 yet. That means that running `pip install -e .` will fail because `poetry` doesn't use a `setup.py` file. As a workaround, you can use the `create_setup.py` file to generate a temporary `setup.py` file. To install `fliswarm` in editable mode without `poetry`, do

```console
pip install poetry
python create_setup.py
pip install -e .
```
