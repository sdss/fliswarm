#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: nuc.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import subprocess

from docker import DockerClient, types

from .tools import FakeCommand


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

        self.enabled = True

    def connect(self):
        """Connects to the Docker client on the remote host."""

        if not self.ping():
            raise ConnectionError(f'Host {self.host} is not responding.')

        self.client = DockerClient(self.daemon_addr, timeout=1)

    @property
    def connected(self):
        """Returns `True` if the NUC and the Docker client are connected."""

        return (self.enabled and self.ping() and
                self.client and self.client.ping())

    def is_container_running(self, name):
        """Returns `True` if the container is running."""

        if not self.client:
            return False

        containers = self.client.containers.list(
            filters={'name': name, 'status': 'running'})

        if len(containers) == 1:
            return True

        return False

    def ping(self, timeout=0.1):
        """Pings the NUC host. Returns `True` if the host is responding."""

        ping = subprocess.run(['ping', '-c', '1',
                               '-W', str(timeout), self.host],
                              capture_output=True)

        return True if ping.returncode == 0 else False

    def get_volume(self, name):
        """Returns the volume that matches the name, if it exists."""

        volumes = self.client.volumes.list()

        for vol in volumes:
            if vol.name == name:
                return vol
        return False

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
            command.warning(text=f'Host {self.host} is not pinging back.')
            command.info(NUC=status)
            return

        status[3] = True  # The NUC is responding.

        if not self.client or not self.client.ping():
            command.warning(text=f'Docker client on host {self.host} '
                                 'is not connected.')
            command.info(NUC=status)
            return

        status[4] = True
        command.info(NUC=status)

        if containers:
            image = config['registry'] + '/' + config['image'].split(':')[0]
            containers = self.client.containers.list(
                all=True, filters={'ancestor': image, 'status': 'running'})

            if len(containers) == 0:
                command.warning(text=f'No containers running on {self.host}.')
                command.debug(container=[self.name, 'NA'])
            elif len(containers) > 1:
                command.warning(text=f'Multiple containers with image {image} '
                                     f'running on host {self.host}.')
                command.debug(container=[self.name, 'NA'])
            else:
                command.debug(container=[self.name, containers[0].short_id])

        if volumes:
            volumes = self.client.volumes.list()
            for vname in config['volumes']:
                volume = self.get_volume(vname)
                if volume is False:
                    command.warning(text=f'Volume {vname} not present '
                                         f'in {self.name}.')
                    command.debug(volume=[self.name, vname, False, 'NA'])
                    continue
                command.debug(volume=[self.name, vname, True,
                                      volume.attrs['Options']['device']])

    def stop_container(self, name, image, force=False, command=None):
        """Stops and removes the container.

        Parameters
        ----------
        name : str
            The name to assign to the container.
        image : str
            The image to run.
        force : bool
            If `True`, removes any stopped containers of the same name or
            with the same image as ancestor.
        command : ~clu.command.Command
            A command to which output messages.

        """

        command = command or FakeCommand()

        base_image = image.split(':')[0]

        # Silently remove any exited containers that match the name or image
        # TODO: In the future we may want to restart them instead.
        exited_containers = self.client.containers.list(
            all=True, filters={'name': name, 'status': 'exited'})

        if len(exited_containers) > 0:
            map(lambda c: c.remove(v=False, force=True), exited_containers)

        if force:
            ancestors = self.client.containers.list(
                all=True, filters={'ancestor': base_image})
            for container in ancestors:
                command.warning(
                    text=f'{self.name}: removing container '
                         f'({container.name}, {container.short_id}) '
                         f'that uses image {base_image}.')
                container.remove(v=False, force=True)

        name_containers = self.client.containers.list(
            all=True, filters={'name': name, 'status': 'running'})
        if len(name_containers) > 0:
            container = name_containers[0]
            command.warning(text=f'{self.name}: removing running '
                                 f'container {name}.')
            container.remove(v=False, force=True)
            command.debug(container=[self.name, 'NA'])

    def run_container(self, name, image, volumes=[], privileged=False,
                      registry=None, envs={}, ports=[], force=False,
                      command=None):
        """Runs a container in the NUC, in detached mode.

        Parameters
        ----------
        name : str
            The name to assign to the container.
        image : str
            The image to run.
        volumes : list
            Names of the volumes to mount. The mount point in the container
            will match the original device. The volumes must already exist
            in the NUC.
        privileged : bool
            Whether to run the container in privileged mode.
        registry : bool
            The registry from which to pull the image, if it doesn't exist
            locally.
        envs : dict
            A dictionary of environment variable to value to pass to the
            container.
        ports : dict or list
            Ports to bind inside the container. The format must be
            ``{'2222/tcp': 3333}`` which will expose port 2222 inside the
            container as port 3333 on the host. Also accepted is a list of
            integers; each integer port will be exposed in the container
            and bound to the same port in the host.
        force : bool
            If `True`, removes any running containers of the same name,
            or any container with the same image as ancestor.
        command : ~clu.command.Command
            A command to which output messages.

        Returns
        -------
        The container object.

        """

        # This is the command in general we aim to run.
        # docker --context gfa1 run
        #        --rm -d -p 19995:19995
        #        --mount source=data,target=/data
        #        --mount source=home,target=/home/sdss
        #        --env OBSERVATORY=APO --env ACTOR_NAME=gfa
        #        --privileged
        #        sdss-hub:5000/flicamera:latest

        command = command or FakeCommand()

        if self.is_container_running(name) and not force:
            command.debug(text=f'{self.name}: container already running.')
            return

        self.stop_container(name, image, force=force, command=command)

        if registry:
            image = registry + '/' + image

        if isinstance(ports, (list, tuple)):
            ports = {f'{port}/tcp': ('0.0.0.0', port) for port in ports}

        mounts = []
        for vname in volumes:
            volume = self.client.volumes.get(vname)
            target = volume.attrs['Options']['device'].strip(':')
            mounts.append(types.Mount(target, vname))

        command.debug(text=f'{self.name}: pulling latest image.')
        self.client.images.pull(image)

        command.info(text=f'{self.name}: running {name} from {image}.')
        container = self.client.containers.run(image,
                                               name=name,
                                               tty=False,
                                               detach=True,
                                               remove=True,
                                               environment=envs,
                                               ports=ports,
                                               privileged=privileged,
                                               mounts=mounts,
                                               stdin_open=False,
                                               stdout=False)

        return container

    def create_volume(self, name, driver='local', opts={}, force=False,
                      command=None):
        """Creates a volume in the NUC Docker.

        Parameters
        ----------
        name : str
            The name of the volume to create.
        driver : str
            The driver to use.
        opts : dict
            A dict of key-values with the options to pass to the volume when
            creating it.
        force : bool
            If `True`, and the volume already exists, removes it and
            creates it anew.
        command : ~clu.command.Command
            A command to which output messages.

        Returns
        -------
        The volume object.

        Examples
        --------
        To create an NFS volume pointing to ``/data`` on ``sdss-hub`` ::

            nuc.create_volume('data', driver='local'
                              opts=['type=nfs',
                                    'o=nfsvers=4,addr=sdss-hub,rw',
                                    'device=:/data'])

        """

        command = command or FakeCommand()

        volume = self.get_volume(name)
        if volume is not False:
            if not force:
                command.debug(text=f'{self.name}: volume {name} '
                              'already exists.')
                return
            command.warning(text=f'{self.name}: recreating existing '
                            f'volume {name}.')
            volume.remove(force=True)

        volume = self.client.volumes.create(name, driver=driver,
                                            driver_opts=opts)

        command.debug(text=f'{self.name}: creating volume {name}.')
        command.debug(volume=[self.name, name, True,
                              volume.attrs['Options']['device']])

        return
