#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-26
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os

import click
from click_default_group import DefaultGroup

from sdsstools.daemonizer import DaemonGroup, cli_coro

from fliswarm.actor import FLISwarmActor


@click.group(cls=DefaultGroup, default='actor', default_if_no_args=True)
@click.option('-c', '--config', type=click.Path(exists=True, dir_okay=False),
              help='Path to an external configuration file.')
@click.pass_obj
def fliswarm(obj, config):
    """CLI for the fliswarm actor."""

    obj['config'] = config


@fliswarm.group(cls=DaemonGroup, prog='actor', workdir=os.getcwd())
@click.pass_obj
@cli_coro()
async def actor(obj):
    """Start/stop the actor as a daemon."""

    config = obj['config']

    if config is None:
        cdir = os.path.dirname(__file__)
        config = os.path.join(cdir, 'etc/fliswarm.yaml')

    actor = await FLISwarmActor.from_config(config).start()
    await actor.run_forever()


def main():
    fliswarm(obj={})


if __name__ == '__main__':
    main()
