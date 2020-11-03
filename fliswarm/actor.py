#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import json
import os

import click
from clu.device import Device
from clu.legacy import LegacyActor
from clu.parser import command_parser

from . import __version__
from .nuc import NUC
from .tools import select_nucs


class FlicameraDevice(Device):
    """A device to handle the connection to a flicamera actor and camera."""

    def __init__(self, host, port, fliswarm_actor):

        self.fliswarm_actor = fliswarm_actor

        super().__init__(host, port)

    async def restart(self):
        """Restart the connection."""

        if self._client:
            await self.stop()
        await self.start()

    async def process_message(self, line):
        """Receives a message from flicamera and outputs it in fliswarm."""

        if self.fliswarm_actor is None:
            return

        message = json.loads(line)

        if 'header' not in message or message['header'] == {}:
            return
        if 'data' not in message or message['data'] == {}:
            return

        sender = message['header']['sender']
        message_code = message['header']['message_code']

        if message_code == '>':
            message_code = 'd'
        elif message_code == 'f':
            message_code = 'e'

        data = message['data']
        for key in data:
            if not isinstance(data[key], list):
                data[key] = [data[key]]
            data[key] = [sender] + data[key]

        self.fliswarm_actor.write(message_code, data, broadcast=True)


class FLISwarmActor(LegacyActor):
    """FLISwarm actor."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.version = __version__

        self.observatory = os.environ['OBSERVATORY']

        self.nucs = []
        self.flicameras = {}

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

        for nuc in self.nucs:
            self.flicameras[nuc.name] = FlicameraDevice(
                nuc.host, self.config['nucs'][nuc.name]['port'], self)

            try:
                await self.flicameras[nuc.name].start()
            except OSError:
                pass

        self.parser_args = [self.nucs]

        return await super().start()


@command_parser.command()
async def status(command, nucs):
    """Outputs the status of the NUCs and containers."""

    command.info(enabledNUCs=[nuc.name for nuc in nucs])

    for nuc in nucs:
        nuc.report_status(command)

    command.finish()


@command_parser.command()
@click.option('--names', '-n', type=str,
              help='Comma-separated NUCs to reconnect.')
@click.option('--category', '-c', type=str,
              help='Category of NUCs to reconnect (gfa, fvc).')
@click.option('--force', '-f', is_flag=True,
              help='Stops and restarts services even if they are running.')
async def reconnect(command, nucs, names, category, force):
    """Recreates volumes and restarts the Docker containers."""

    config = command.actor.config

    def reconnect_nuc(nuc):
        """Reconnect sync. Will be run in an executor."""

        actor = command.actor

        if not nuc.connected:
            nuc.report_status(command)
            command.error(text=f'NUC {nuc.name} is not pinging back or '
                               'the Docker daemon is not running. Try '
                               'rebooting the computer.')
            return

        # Stop container first, because we cannot remove volumes that are
        # attached to running containers.
        nuc.stop_container(config['container_name'] + f'-{nuc.name}',
                           config['image'],
                           force=force,
                           command=command)

        for vname in config['volumes']:
            vconfig = config['volumes'][vname]
            nuc.create_volume(vname,
                              driver=vconfig['driver'],
                              opts=vconfig['opts'],
                              force=force,
                              command=command)

        return nuc.run_container(config['container_name'] + f'-{nuc.name}',
                                 config['image'],
                                 volumes=list(config['volumes']),
                                 privileged=True,
                                 registry=config['registry'],
                                 ports=[config['nucs'][nuc.name]['port']],
                                 envs={'ACTOR_NAME': nuc.name,
                                       'OBSERVATORY': actor.observatory},
                                 force=force,
                                 command=command)

    reconnect_nucs = select_nucs(nucs, category, names)

    # Drop the device before doing anything with the containers, or we'll
    # get weird hangups.
    for nuc in reconnect_nucs:
        device = command.actor.flicameras[nuc.name]
        if device.is_connected():
            await device.stop()

    loop = asyncio.get_event_loop()
    await asyncio.gather(*[loop.run_in_executor(None, reconnect_nuc, nuc)
                           for nuc in reconnect_nucs])

    command.info(text='Waiting 5 seconds before reconnecting the devices ...')
    await asyncio.sleep(5)

    for nuc in reconnect_nucs:

        container_name = config['container_name'] + f'-{nuc.name}'
        if not nuc.is_container_running(container_name):
            continue

        device = command.actor.flicameras[nuc.name]
        await device.restart()

        if device.is_connected():
            port = device.port
            command.debug(text=f'{nuc.name}: reconnected to '
                               f'device on port {port}.')
        else:
            command.warning(text=f'{nuc.name}: failed to connect to device.')

    command.finish()
