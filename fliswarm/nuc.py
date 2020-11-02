#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: nuc.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import subprocess

from docker import DockerClient


DEFAULT_DOCKER_PORT = 2375


class NUC(object):
    """A client to handle a NUC.

    Parameters
    ----------
    name : str
        The name associated with this NUC.
    host : str
        The address to the NUC host.
    category : str
        A category to use as a filter.
    daemon_addr : str
        The address to the Docker daemon. If `None`, defaults to
        ``tcp://host:port`` where ``port`` is the default Docker daemon port.
    registry : str
        The path to the Docker registry.

    """

    def __init__(self, name, host, category=None,
                 daemon_addr=None, registry=None):

        self.name = name
        self.host = host
        self.category = category

        if daemon_addr:
            self.daemon_addr = daemon_addr
        else:
            self.daemon_addr = f'tcp://{host}:{DEFAULT_DOCKER_PORT}'

        self.registry = registry
        self.client = None

    def connect(self):
        """Connects to the Docker client on the remote host."""

        if not self.ping():
            raise ConnectionError(f'Host {self.host} is not responding.')

        self.client = DockerClient(self.daemon_addr, timeout=1)

    @property
    def connected(self):
        """Returns `True` if the NUC and the Docker client are connected."""

        return self.ping() and self.client and self.client.ping()

    def ping(self, timeout=0.1):
        """Pings the NUC host. Returns `True` if the host is responding."""

        ping = subprocess.run(['ping', '-c', '1',
                               '-W', str(timeout), self.host],
                              capture_output=True)

        return True if ping.returncode == 0 else False

    def report_status(self, command, volumes=True, containers=True):
        """Reports the status of the NUC.

        Parameters
        ----------
        command : ~clu.command.Command
            The command that is requesting the status.
        volumes : bool
            Whether to report the volumes connected to the NUC Docker.
        containers : bool
            Whether to report the containers running. Only reports running
            containers whose ancestor matches the ``config['image']``.

        Notes
        -----
        Outputs the ``nuc`` keyword, with format
        ``NUC={nuc_name, host, daemon_addr, nuc_alive, docker_alive}``.
        If ``containers=True``, outputs the ``container`` keyword with
        format ``container={nuc_name, container_short_id}``. If
        ``volumes=True``, reports the ``volume`` keyword with format
        ``volume={nuc_name, volume, exists, mount_point}``

        """

        status = [self.name, self.host, self.daemon_addr, False, False]

        config = command.actor.config

        if not self.ping(timeout=config['ping_timeout']):
            command.error(text=f'Host {self.host} is not pinging back.')
            command.info(NUC=status)
            return

        status[3] = True  # The NUC is responding.

        if not self.client or not self.client.ping():
            command.error(text=f'Docker client on host {self.host} '
                               'is not connected.')
            command.info(NUC=status)
            return

        status[4] = True
        command.info(NUC=status)

        if containers:

            image = config['image'].split(':')[0]

            containers = self.client.containers.list(
                filters={'ancestor': image, 'status': 'running'})

            for container in containers:
                command.debug(container=[self.name, container.short_id])

            if len(containers) == 0:
                command.error(text=f'No containers running on {self.host}.')
            elif len(containers) > 1:
                command.error(text=f'Multiple containes with image {image} '
                                   f'running on host {self.host}.')

        if volumes:
            volumes = self.client.volumes.list()
            for vname in config['volumes']:
                if vname not in [v.name for v in volumes]:
                    command.error(text=f'Volume {vname} not present '
                                       f'in {self.name}.')
                    command.debug(volume=[self.name, vname, False, 'NA'])
                    continue
                volume = [v for v in volumes if v.name == vname][0]
                command.debug(volume=[self.name, vname, True,
                                      volume.attrs['Options']['device']])
