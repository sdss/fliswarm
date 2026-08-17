# Changelog

## Next release

### ✨ Improved

* Improve handling of network mode and ports when creating a container.
* Support setting UID and GID in container.

### 🔧 Fixed

* Support different flavours of `ping` at APO and LCO.


## 0.6.1 - November 1, 2025

### ✨ Improved

* Allow multiple retries when reconnecting a device.


## 0.6.0 - July 29, 2025

### 🔥 Breaking Changes

* Require Python 3.10 or later.

### ⚙️ Engineering

* Use `uv` for package management.
* Support Python 3.13.
* Update workflows.


## 0.5.0 - December 22, 2023

### 🔧 Fixed

* Prevent `OSError` when restarting a device.

### ⚙️ Engineering

* Support 3.12.
* Lint using `ruff`.


## 0.4.0 - December 24, 2022

### ✨ Improved

* Bind `/dev/bus/usb` in the container, which ensures the camera can be connected without having to restart the container.
* Increase CPU and memory allocation in the container.

### 🏷️ Changed

* APO now mounts `/data` from `sdss5-hub`.


## 0.3.1 - September 11, 2022

### 🏷️ Changed

* Re-enabled GFA1 and 6 for APO.


## 0.3.0 - June 10, 2022

### 🚀 New

* Allow to use `force=True` when stopping or running a container.
* Allow to force enabling a node that's not in `enabled_nodes`.
* Add cameras and nodes for LCO.

### 🏷️ Changed

* Disabled GFA1 and 6 for APO.
* Use `nfsvers=4` for `/data` volume.
* Some engineering improvements.


## 0.2.0 - December 14, 2021

### 🚀 New

* [#1](https://github.com/sdss/fliswarm/issues/1) Implement NUC reboot commands.

### ✨ Improved

* Nodes are now organised by observatory.
* Default image name is not `sdss/flicamera:latest`.
* Add option to start `fliswarm` with only certain nodes from the CLI.
* Run containers with `network="host"` to allow instances of FLIcamera access to Tron.
* Initial operations testing at APO.


## 0.1.0 - November 11, 2020

### 🚀 New

* Initial version.
