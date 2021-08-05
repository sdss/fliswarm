#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-26
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os
import warnings

import click
from click_default_group import DefaultGroup

from sdsstools.configuration import read_yaml_file
from sdsstools.daemonizer import DaemonGroup, cli_coro

from fliswarm.actor import FLISwarmActor


@click.group(cls=DefaultGroup, default="actor", default_if_no_args=True)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to an external configuration file.",
)
@click.option(
    "--nodes",
    type=str,
    help="Comma-separated nodes to connect.",
)
@click.pass_obj
def fliswarm(obj, config=None, nodes=None):
    """CLI for the fliswarm actor."""

    obj["config"] = config

    if nodes is not None:
        nodes = list(map(lambda x: x.strip(), nodes.split(",")))

    obj["nodes"] = nodes


@fliswarm.group(cls=DaemonGroup, prog="actor", workdir=os.getcwd())
@click.pass_obj
@cli_coro()
async def actor(obj):
    """Start/stop the actor as a daemon."""

    try:
        observatory = os.environ["OBSERVATORY"]
    except KeyError:
        warnings.warn("$OBSERVATORY not set. Assuming APO.", UserWarning)
        observatory = "APO"
        os.environ["OBSERVATORY"] = "APO"

    config = obj["config"]

    if config is None:
        cdir = os.path.dirname(__file__)
        config = os.path.join(cdir, "etc/fliswarm.yaml")

    if obj["nodes"] is not None:
        config = read_yaml_file(config)
        config["enabled_nodes"][observatory] = obj["nodes"]

    actor = await FLISwarmActor.from_config(config).start()
    await actor.run_forever()  # type: ignore


def main():
    fliswarm(obj={})


if __name__ == "__main__":
    main()
