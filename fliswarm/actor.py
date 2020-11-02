#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import click
from clu.legacy import LegacyActor
from clu.parser import command_parser

from . import __version__
from .nuc import NUC
from .tools import select_nucs


class FLISwarmActor(LegacyActor):
    """FLISwarm actor."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.version = __version__

        self.nucs = []

    def connect_nucs(self):
        """Connects to the NUCs."""

        nuc_config = self.config['nucs']

        self.nucs = [NUC(name, nuc_config[name]['host'],
                         daemon_addr=nuc_config[name]['docker-client'],
                         category=nuc_config[name].get('category', None))
                     for name in self.config['enabled_nucs']]

        for nuc in self.nucs:
            try:
                nuc.connect()
            except BaseException:
                pass

    async def start(self):
        """Starts the actor."""

        self.connect_nucs()

        self.parser_args = [self.nucs]

        return await super().start()


@command_parser.command()
async def status(command, nucs):
    """Outputs the status of the NUCs and containers."""

    command.info(enabledNUCs=[nuc.name for nuc in nucs])

    for nuc in nucs:
        nuc.report_status(command)

    command.finish()
