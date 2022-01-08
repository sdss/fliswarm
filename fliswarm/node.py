#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: node.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from functools import partial

from typing import Any, Dict, List, Optional, Tuple, Union

import docker.errors
import requests
from docker import DockerClient, types

from clu.command import Command

from .tools import FakeCommand, subprocess_run_async


DEFAULT_DOCKER_PORT = 2375


class Node:
    """A client to handle a computer node.

    Parameters
    ----------
    name
        The name associated with this node.
    addr
        The address to the node.
    category
        A category to use as a filter.
    daemon_addr
        The address to the Docker daemon. If `None`, defaults to
        ``tcp://node:port`` where ``port`` is the default Docker daemon port.
    registry
        The path to the Docker registry.
    """

    def __init__(
        self,
        name: str,
        addr: str,
        category: Optional[str] = None,
        daemon_addr: Optional[str] = None,
        registry: Optional[str] = None,
    ):

        self.name = name
        self.addr = addr
        self.category = category

        self.loop = asyncio.get_running_loop()

        if daemon_addr:
            self.daemon_addr = daemon_addr
        else:
            self.daemon_addr = f"tcp://{addr}:{DEFAULT_DOCKER_PORT}"

        self.registry = registry
        self.client: DockerClient | None = None

        self.enabled = True

    async def _run(self, fn, *args, **kwargs):
        """Run in executor."""

        return await self.loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def connect(self):
        """Connects to the Docker client on the remote node."""

        if not await self.ping():
            raise ConnectionError(f"Node {self.addr} is not responding.")

        self.client = await self._run(DockerClient, self.daemon_addr, timeout=3)

    async def client_alive(self) -> bool:
        """Checks whether the Docker client is connected and pinging."""

        if not self.client:
            return False

        try:
            client_alive = await asyncio.wait_for(self._run(self.client.ping), 1)
            if client_alive:
                return True
            return False
        except (
            requests.exceptions.ConnectionError,
            docker.errors.APIError,
            asyncio.TimeoutError,
        ):
            return False

    async def connected(self) -> bool:
        """Returns `True` if the node and the Docker client are connected."""

        return self.enabled and (await self.ping()) and (await self.client_alive())

    async def is_container_running(self, name: str):
        """Returns `True` if the container is running."""

        if not self.client:
            return False

        containers = await self._run(
            self.client.containers.list,
            filters={"name": name, "status": "running"},
        )

        if len(containers) == 1:
            return True

        return False

    async def ping(self, timeout=0.5) -> bool:
        """Pings the node. Returns `True` if the node is responding."""

        try:
            ping = await asyncio.wait_for(
                subprocess_run_async(
                    f"ping -c 1 -w {timeout} {self.addr}",
                    shell=True,
                ),
                timeout,
            )
            return True if ping.returncode == 0 else False
        except asyncio.TimeoutError:
            return False

    async def get_volume(self, name: str):
        """Returns the volume that matches the name, if it exists."""

        assert self.client, "Client is not connected."

        volumes: List[Any] = await self.loop.run_in_executor(
            None,
            self.client.volumes.list,
        )

        for vol in volumes:
            if vol.name == name:
                return vol
        return False

    async def report_status(
        self,
        command: Command,
        volumes: bool = True,
        containers: bool = True,
    ):
        """Reports the status of the node to an actor.

        Parameters
        ----------
        command
            The command that is requesting the status.
        volumes
            Whether to report the volumes connected to the node Docker engine.
        containers
            Whether to report the containers running. Only reports running
            containers whose ancestor matches the ``config['image']``.

        Notes
        -----
        Outputs the ``node`` keyword, with format
        ``node={node_name, addr, daemon_addr, node_alive, docker_alive}``.
        If ``containers=True``, outputs the ``container`` keyword with
        format ``container={node_name, container_short_id}``. If
        ``volumes=True``, reports the ``volume`` keyword with format
        ``volume={node_name, volume, ping, docker_client}``
        """

        status = [self.name, self.addr, self.daemon_addr, False, False]

        config = command.actor.config

        if not self.client:
            command.warning(f"Node {self.addr} has no client.")
            return

        if not (await self.ping(timeout=config["ping_timeout"])):
            command.warning(text=f"Node {self.addr} is not pinging back.")
            command.info(node=status)
            if self.client:
                self.client.close()
            return

        status[3] = True  # The NUC is responding.

        if not (await self.client_alive()):
            command.warning(text=f"Docker client on node {self.addr} is not connected.")
            command.info(node=status)
            if self.client:
                self.client.close()
            return

        status[4] = True
        command.info(node=status)

        if containers:

            image = config["image"].split(":")[0]
            if config["registry"]:
                image = config["registry"] + "/" + image

            container_list: List[Any] = await self._run(
                self.client.containers.list,
                all=True,
                filters={"ancestor": image, "status": "running"},
            )

            if len(container_list) == 0:
                command.warning(text=f"No containers running on {self.addr}.")
                command.debug(container=[self.name, "NA"])
            elif len(container_list) > 1:
                command.warning(
                    text=f"Multiple containers with image {image} "
                    f"running on node {self.addr}."
                )
                command.debug(container=[self.name, "NA"])
            else:
                command.debug(container=[self.name, container_list[0].short_id])

        if volumes:
            for vname in config["volumes"]:
                volume: Any = await self.get_volume(vname)
                if volume is False:
                    command.warning(text=f"Volume {vname} not present in {self.name}.")
                    command.debug(volume=[self.name, vname, False, "NA"])
                    continue
                command.debug(
                    volume=[self.name, vname, True, volume.attrs["Options"]["device"]]
                )

    async def stop_container(
        self,
        name: str,
        image: str,
        force: bool = False,
        command: Optional[Union[Command, FakeCommand]] = None,
    ):
        """Stops and removes the container.

        Parameters
        ----------
        name
            The name to assign to the container.
        image
            The image to run.
        force
            If `True`, removes any stopped containers of the same name or
            with the same image as ancestor.
        command
            A command to which output messages.
        """

        assert self.client, "Client is not connected."

        command = command or FakeCommand()

        base_image = image.split(":")[0]

        # Silently remove any exited containers that match the name or image
        # TODO: In the future we may want to restart them instead.
        exited_containers: List[Any] = await self._run(
            self.client.containers.list, all=True, filters={"name": name}
        )

        if len(exited_containers) > 0:
            list(map(lambda c: c.remove(v=False, force=True), exited_containers))

        if force:
            ancestors: List[Any] = await self._run(
                self.client.containers.list, all=True, filters={"ancestor": base_image}
            )
            for container in ancestors:
                command.warning(
                    text=f"{self.name}: removing container "
                    f"({container.name}, {container.short_id}) "
                    f"that uses image {base_image}."
                )
                container.remove(v=False, force=True)

        name_containers: List[Any] = await self._run(
            self.client.containers.list,
            all=True,
            filters={"name": name, "status": "running"},
        )
        if len(name_containers) > 0:
            container = name_containers[0]
            command.warning(text=f"{self.name}: removing running container {name}.")
            container.remove(v=False, force=True)
            command.debug(container=[self.name, "NA"])

    async def run_container(
        self,
        name: str,
        image: str,
        volumes: List[Any] = [],
        privileged: bool = False,
        registry: Optional[Any] = None,
        envs: Dict[str, Any] = {},
        ports: Union[List[int], Dict[str, Tuple[str, int]]] = [],
        force: bool = False,
        command: Optional[Union[Command, FakeCommand]] = None,
    ):
        """Runs a container in the node, in detached mode.

        Parameters
        ----------
        name
            The name to assign to the container.
        image
            The image to run.
        volumes
            Names of the volumes to mount. The mount point in the container
            will match the original device. The volumes must already exist
            in the node Docker engine.
        privileged
            Whether to run the container in privileged mode.
        registry
            The registry from which to pull the image, if it doesn't exist
            locally.
        envs
            A dictionary of environment variable to value to pass to the
            container.
        ports
            Ports to bind inside the container. The format must be
            ``{'2222/tcp': 3333}`` which will expose port 2222 inside the
            container as port 3333 on the node. Also accepted is a list of
            integers; each integer port will be exposed in the container
            and bound to the same port in the node.
        force
            If `True`, removes any running containers of the same name,
            or any container with the same image as ancestor.
        command
            A command to which output messages.

        Returns
        -------
        :
            The container object.
        """

        assert self.client, "Client is not connected."

        # This is the command we aim to run.
        # docker --context gfa1 run
        #        --rm -d --network host
        #        --mount source=data,target=/data
        #        --mount source=home,target=/home/sdss
        #        --env OBSERVATORY=APO --env ACTOR_NAME=gfa
        #        --privileged
        #        sdss-hub:5000/flicamera:latest

        command = command or FakeCommand()

        if (await self.is_container_running(name)) and not force:
            command.debug(text=f"{self.name}: container already running.")
            return

        await self.stop_container(name, image, force=force, command=command)

        if registry:
            image = registry + "/" + image

        if isinstance(ports, (list, tuple)):
            ports = {f"{port}/tcp": ("0.0.0.0", port) for port in ports}

        mounts = []
        for vname in volumes:
            volume = await self._run(self.client.volumes.get, vname)
            target = volume.attrs["Options"]["device"].strip(":")
            mounts.append(types.Mount(target, vname))

        command.debug(text=f"{self.name}: pulling latest image.")
        await self._run(self.client.images.pull, image)

        command.info(text=f"{self.name}: running {name} from {image}.")
        container = await self._run(
            self.client.containers.run,
            image,
            name=name,
            tty=False,
            detach=True,
            remove=True,
            environment=envs,
            # ports=ports,
            privileged=privileged,
            mounts=mounts,
            stdin_open=False,
            stdout=False,
            network="host",
        )

        return container

    async def create_volume(
        self,
        name: str,
        driver: str = "local",
        opts: Dict[str, Any] = {},
        force: bool = False,
        command: Optional[Union[Command, FakeCommand]] = None,
    ):
        """Creates a volume in the node Docker engine.

        Parameters
        ----------
        name
            The name of the volume to create.
        driver
            The driver to use.
        opts
            A dict of key-values with the options to pass to the volume when
            creating it.
        force
            If `True`, and the volume already exists, removes it and
            creates it anew.
        command
            A command to which output messages.

        Returns
        -------
        :
            The volume object.

        Examples
        --------
        To create an NFS volume pointing to ``/data`` on ``sdss-hub`` ::

            nuc.create_volume('data', driver='local'
                              opts=['type=nfs', 'o=nfsvers=4,addr=sdss-hub,rw',
                                    'device=:/data'])

        """

        assert self.client, "Client is not connected."

        command = command or FakeCommand()

        volume: Any = await self.get_volume(name)
        if volume is not False:
            if not force:
                command.debug(text=f"{self.name}: volume {name} already exists.")
                return volume
            command.warning(text=f"{self.name}: recreating existing volume {name}.")
            await self._run(volume.remove, force=True)

        volume = await self._run(
            self.client.volumes.create,
            name,
            driver=driver,
            driver_opts=opts,
        )

        command.debug(text=f"{self.name}: creating volume {name}.")
        command.debug(volume=[self.name, name, True, volume.attrs["Options"]["device"]])

        return volume
