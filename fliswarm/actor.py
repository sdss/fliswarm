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
from clu import Command
from clu.device import Device
from clu.legacy import LegacyActor
from clu.parser import command_parser
from clu.tools import CommandStatus

from . import __version__
from .nuc import NUC
from .tools import IDPool, select_nucs


class FlicameraDevice(Device):
    """A device to handle the connection to a flicamera actor and camera."""

    def __init__(self, host, port, fliswarm_actor):

        self.fliswarm_actor = fliswarm_actor
        self.id_pool = IDPool()

        self.running_commands = {}

        super().__init__(host, port)

    async def restart(self):
        """Restart the connection."""

        if self._client:
            await self.stop()
        await self.start()

    def send_message(self, parent_command, message, command_id=None):
        """Sends a message to the device."""

        if not self.is_connected():
            raise OSError('Device is not connected')

        command_id = command_id or self.id_pool.get()

        dev_command = Command(message, command_id=command_id,
                              parent=parent_command)
        self.running_commands[command_id] = dev_command

        self.write(f'{command_id} {message}')

        return dev_command

    async def process_message(self, line):
        """Receives a message from flicamera and outputs it in fliswarm."""

        if self.fliswarm_actor is None:
            return

        message = json.loads(line)

        if 'header' not in message or message['header'] == {}:
            return

        sender = message['header']['sender']
        command_id = message['header']['command_id']
        dev_command_message_code = message['header']['message_code']

        # We don't want to output running or done/failed message codes,
        # but we want to keep the original message code to update the status
        # of the device command.
        if dev_command_message_code == '>':
            message_code = 'd'
        elif dev_command_message_code == ':':
            message_code = 'i'
        elif dev_command_message_code in ['f', 'e']:
            message_code = 'w'
        else:
            message_code = dev_command_message_code

        data = message['data']
        for key in data:
            if not isinstance(data[key], list):
                data[key] = [data[key]]
            data[key] = [sender] + data[key]

        if command_id in self.running_commands:

            # If the message has keywords, output them but using the
            # modified message code.
            dev_command = self.running_commands[command_id]
            if len(data) > 0:
                dev_command.write(message_code, data)

            # Update the device command with the real message code of the
            # received message. Do it with silent=True to avoid CLU
            # informing about the change in status.
            status = CommandStatus.code_to_status(dev_command_message_code)
            dev_command.set_status(status, silent=True)

            # If the command is done, return the command_id to the pool.
            if dev_command.status.is_done:
                self.running_commands.pop(command_id)
                self.id_pool.put(command_id)

        else:  # This should not happen, but https://xkcd.com/2200/.
            if len(data) > 0:
                self.fliswarm_actor.write(message_code, data, broadcast=True)


class FLISwarmActor(LegacyActor):
    """FLISwarm actor."""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.version = __version__

        self.observatory = os.environ['OBSERVATORY']

        self.nucs = {}
        self.flicameras = {}

    def connect_nucs(self):
        """Connects to the NUCs."""

        nuc_config = self.config['nucs']

        self.nucs = {name: NUC(name, nuc_config[name]['host'],
                               daemon_addr=nuc_config[name]['docker-client'],
                               category=nuc_config[name].get('category', None))
                     for name in self.config['enabled_nucs']}

        for nuc in self.nucs.values():
            try:
                nuc.connect()
            except BaseException:
                pass

    async def start(self):
        """Starts the actor."""

        self.connect_nucs()

        for nuc in self.nucs.values():

            self.flicameras[nuc.name] = FlicameraDevice(
                nuc.name, nuc.host,
                self.config['nucs'][nuc.name]['port'], self)

            if nuc.is_container_running(self.get_container_name(nuc)):
                try:
                    await self.flicameras[nuc.name].start()
                except OSError:
                    self.write('w', text=f'{nuc.name}: failed to connect to '
                                         f'the flicamera device.')

        self.parser_args = [self.nucs]

        return await super().start()

    def get_container_name(self, nuc):
        """Returns the name of the container for a NUC."""

        return self.config['container_name'] + f'-{nuc.name}'


@command_parser.command()
async def status(command, nucs):
    """Outputs the status of the NUCs and containers."""

    enabled_nucs = [nuc for nuc in nucs.values() if nuc.enabled]
    command.info(enabledNUCs=[nuc.name for nuc in enabled_nucs])

    for nuc in enabled_nucs:
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
            command.warning(text=f'NUC {nuc.name} is not pinging back or '
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

        return nuc.run_container(actor.get_container_name(nuc),
                                 config['image'],
                                 volumes=list(config['volumes']),
                                 privileged=True,
                                 registry=config['registry'],
                                 ports=[config['nucs'][nuc.name]['port']],
                                 envs={'ACTOR_NAME': nuc.name,
                                       'OBSERVATORY': actor.observatory},
                                 force=force,
                                 command=command)

    c_nucs = select_nucs(nucs, category, names)

    # Drop the device before doing anything with the containers, or we'll
    # get weird hangups.
    for nuc in c_nucs:
        nuc_name = nuc.name
        device = command.actor.flicameras[nuc_name]
        if device.is_connected():
            await device.stop()

    loop = asyncio.get_event_loop()
    await asyncio.gather(*[loop.run_in_executor(None, reconnect_nuc, nuc)
                           for nuc in c_nucs])

    command.info(text='Waiting 5 seconds before reconnecting the devices ...')
    await asyncio.sleep(5)

    for nuc in c_nucs:

        container_name = config['container_name'] + f'-{nuc.name}'
        if not nuc.is_container_running(container_name):
            continue

        device = command.actor.flicameras[nuc.name]
        await device.restart()

        if device.is_connected():
            port = device.port
            nuc.report_status(command)
            command.debug(text=f'{nuc.name}: reconnected to '
                               f'device on port {port}.')
        else:
            command.warning(text=f'{nuc.name}: failed to connect to device.')

    command.finish()


@command_parser.command()
@click.argument('CAMERA-COMMAND', nargs=-1, type=str)
@click.option('--names', '-n', type=str,
              help='Comma-separated cameras to command.')
@click.option('--category', '-c', type=str,
              help='Category of cameras to talk to (gfa, fvc).')
async def talk(command, nucs, camera_command, names, category):
    """Sends a command to selected or all cameras."""

    camera_command = ' '.join(camera_command)

    c_nucs = select_nucs(nucs, category, names)
    names = [nuc.name for nuc in c_nucs]

    flicameras = command.actor.flicameras

    for name in names:
        if flicameras[name].is_connected():
            continue
        command.warning(text=f'Reconnecting to {name} ...')
        try:
            await flicameras[name].restart()
        except OSError:
            command.fail(text=f'Unable to connect to {name}.')
            return

    dev_commands = []

    for name in names:
        dev_commands.append(flicameras[name].send_message(command,
                                                          camera_command))

    await asyncio.gather(*dev_commands, return_exceptions=True)

    command.finish()


@command_parser.command()
@click.argument('CAMERA-NAMES', nargs=-1, type=str)
@click.option('-a', '--all', is_flag=True, help='Disable all NUCs/cameras.')
async def disable(command, nucs, camera_names, all):
    """Disables one or multiple cameras/NUCs."""

    if all is True:
        camera_names = list(nucs)

    for name in camera_names:
        if name not in nucs:
            command.warning(text=f'Cannot find NUC/camera {name}.')
            continue
        nucs[name].enabled = False

    command.finish()


@command_parser.command()
@click.argument('CAMERA-NAMES', nargs=-1, type=str)
@click.option('-a', '--all', is_flag=True, help='Enable all NUCs/cameras.')
async def enable(command, nucs, camera_names, all):
    """Enables one or multiple cameras/NUCs."""

    if all is True:
        camera_names = list(nucs)

    for name in camera_names:
        if name not in nucs:
            command.warning(text=f'Cannot find NUC/camera {name}.')
            continue
        nucs[name].enabled = True

    command.finish()
