# Changelog

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
