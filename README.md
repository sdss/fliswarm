# fliswarm

![Versions](https://img.shields.io/badge/python->3.10-blue)
[![Documentation Status](https://readthedocs.org/projects/sdss-fliswarm/badge/?version=latest)](https://sdss-fliswarm.readthedocs.io/en/latest/?badge=latest)
[![Tests Status](https://github.com/sdss/flicamera/workflows/Test/badge.svg)](https://github.com/sdss/flicamera/actions)
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

For development, `fliswarm` uses [uv](https://docs.astral.sh/uv/). `fliswarm` can be installed in a virtual environment by doing

```console
uv sync
```
