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

from typing import Dict, List, Optional, TypeVar

import click

from clu import BaseActor, Command
from clu.device import Device
from clu.legacy import LegacyActor
from clu.parsers.click import command_parser
from clu.tools import CommandStatus

from . import __version__
from .node import Node
from .tools import IDPool, select_nodes


T = TypeVar("T", bound="FLISwarmActor")


class FlicameraDevice(Device):
    """A device to handle the connection to a flicamera actor and camera."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        fliswarm_actor: "FLISwarmActor",
    ):

        self.name = name
        self.fliswarm_actor = fliswarm_actor
        self.id_pool = IDPool()

        self.running_commands: Dict[int, Command] = {}

        super().__init__(host, port)

    async def restart(self):
        """Restart the connection."""

        if self._client:
            await self.stop()
        await self.start()

    def send_message(
        self,
        parent_command: Command,
        message: str,
        command_id: Optional[int] = None,
    ) -> Command:
        """Sends a message to the device."""

        if not self.is_connected():
            raise OSError("Device is not connected")

        command_id = command_id or self.id_pool.get()

        dev_command = Command(message, command_id=command_id, parent=parent_command)
        self.running_commands[command_id] = dev_command

        self.write(f"{command_id} {message}")

        return dev_command

    async def process_message(self, line: str):
        """Receives a message from flicamera and outputs it in fliswarm."""

        if self.fliswarm_actor is None:
            return

        message = json.loads(line)

        if "header" not in message or message["header"] == {}:
            return

        sender = message["header"]["sender"]
        command_id = message["header"]["command_id"]
        dev_command_message_code = message["header"]["message_code"]

        # We don't want to output running or done/failed message codes,
        # but we want to keep the original message code to update the status
        # of the device command.
        if dev_command_message_code == ">":
            message_code = "d"
        elif dev_command_message_code == ":":
            message_code = "i"
        elif dev_command_message_code in ["f", "e"]:
            message_code = "w"
        else:
            message_code = dev_command_message_code

        data = message["data"]
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
            if dev_command.status.is_done:  # type: ignore
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

        self.observatory = os.environ["OBSERVATORY"]

        self.nodes = {}
        self.flicameras = {}

    def connect_nodes(self):
        """Connects to the nodes."""

        nconfig = self.config["nodes"]

        self.nodes = {
            name: Node(
                name,
                nconfig[name]["host"],
                daemon_addr=nconfig[name]["docker-client"],
                category=nconfig[name].get("category", None),
            )
            for name in self.config["enabled_nodes"]
        }

        for node in self.nodes.values():
            try:
                node.connect()
            except BaseException:
                pass

    async def start(self) -> BaseActor:
        """Starts the actor."""

        await super().start()

        self.connect_nodes()

        for node in self.nodes.values():

            self.flicameras[node.name] = FlicameraDevice(
                node.name,
                node.addr,
                self.config["nodes"][node.name]["port"],
                self,
            )

            if node.is_container_running(self.get_container_name(node)):
                try:
                    await self.flicameras[node.name].start()
                except OSError:
                    self.write(
                        "w",
                        text=f"{node.name}: failed to connect to "
                        f"the flicamera device.",
                    )

        self.parser_args = [self.nodes]

        return self

    def get_container_name(self, node: Node):
        """Returns the name of the container for a node."""

        return self.config["container_name"] + f"-{node.name}"


@command_parser.command()
async def status(command: Command, nodes: Dict[str, Node]):
    """Outputs the status of the nodes and containers."""

    enabled_nodes = [node for node in nodes.values() if node.enabled]
    command.info(enabledNodes=[node.name for node in enabled_nodes])

    for node in enabled_nodes:
        node.report_status(command)

    command.finish()


@command_parser.command()
@click.option(
    "--names",
    "-n",
    type=str,
    help="Comma-separated nodes to reconnect.",
)
@click.option(
    "--category",
    "-c",
    type=str,
    help="Category of nodes to reconnect (gfa, fvc).",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Stops and restarts services even if they are running.",
)
async def reconnect(
    command: Command,
    nodes: Dict[str, Node],
    names: str,
    category: str,
    force: bool,
):
    """Recreates volumes and restarts the Docker containers."""

    config = command.actor.config

    def reconnect_node(node):
        """Reconnect sync. Will be run in an executor."""

        actor = command.actor

        if not node.connected:
            node.report_status(command)
            command.warning(
                text=f"Node {node.name} is not pinging back or "
                "the Docker daemon is not running. Try "
                "rebooting the computer."
            )
            return

        # Stop container first, because we cannot remove volumes that are
        # attached to running containers.
        node.stop_container(
            config["container_name"] + f"-{node.name}",
            config["image"],
            force=force,
            command=command,
        )

        for vname in config["volumes"]:
            vconfig = config["volumes"][vname]
            node.create_volume(
                vname,
                driver=vconfig["driver"],
                opts=vconfig["opts"],
                force=force,
                command=command,
            )

        return node.run_container(
            actor.get_container_name(node),
            config["image"],
            volumes=list(config["volumes"]),
            privileged=True,
            registry=config["registry"],
            ports=[config["nodes"][node.name]["port"]],
            envs={"ACTOR_NAME": node.name, "OBSERVATORY": actor.observatory},
            force=force,
            command=command,
        )

    c_nodes = select_nodes(nodes, category, names)

    # Drop the device before doing anything with the containers, or we'll
    # get weird hangups.
    for node in c_nodes:
        node_name = node.name
        device = command.actor.flicameras[node_name]
        if device.is_connected():
            await device.stop()

    loop = asyncio.get_event_loop()
    await asyncio.gather(
        *[loop.run_in_executor(None, reconnect_node, node) for node in c_nodes]
    )

    command.info(text="Waiting 5 seconds before reconnecting the devices ...")
    await asyncio.sleep(5)

    for node in c_nodes:

        container_name = config["container_name"] + f"-{node.name}"
        if not node.is_container_running(container_name):
            command.warning(
                text=f"{node.name}: container is not running after reconnect."
            )
            continue

        device = command.actor.flicameras[node.name]
        await device.restart()

        if device.is_connected():
            port = device.port
            node.report_status(command)
            command.debug(text=f"{node.name}: reconnected to device on port {port}.")
        else:
            command.warning(text=f"{node.name}: failed to connect to device.")

    command.finish()


@command_parser.command()
@click.argument("CAMERA-COMMAND", nargs=-1, type=str)
@click.option(
    "--names",
    "-n",
    type=str,
    help="Comma-separated cameras to command.",
)
@click.option(
    "--category",
    "-c",
    type=str,
    help="Category of cameras to talk to (gfa, fvc).",
)
async def talk(
    command: Command,
    nodes: Dict[str, Node],
    camera_command: str,
    names: str,
    category: str,
):
    """Sends a command to selected or all cameras."""

    camera_command = " ".join(camera_command)

    c_nodes = select_nodes(nodes, category, names)
    node_names = [node.name for node in c_nodes]

    flicameras = command.actor.flicameras

    for name in node_names:
        if flicameras[name].is_connected():
            continue
        command.warning(text=f"Reconnecting to {name} ...")
        try:
            await flicameras[name].restart()
        except OSError:
            command.fail(text=f"Unable to connect to {name}.")
            return

    dev_commands = []

    for name in node_names:
        dev_commands.append(flicameras[name].send_message(command, camera_command))

    await asyncio.gather(*dev_commands, return_exceptions=True)

    command.finish()


@command_parser.command()
@click.argument("CAMERA-NAMES", nargs=-1, type=str)
@click.option("-a", "--all", is_flag=True, help="Disable all nodes/cameras.")
async def disable(
    command: Command,
    nodes: Dict[str, Node],
    camera_names: List[str],
    all: bool,
):
    """Disables one or multiple cameras/nodes."""

    if all is True:
        camera_names = list(nodes)

    for name in camera_names:
        if name not in nodes:
            command.warning(text=f"Cannot find node/camera {name}.")
            continue
        nodes[name].enabled = False

    command.finish()


@command_parser.command()
@click.argument("CAMERA-NAMES", nargs=-1, type=str)
@click.option("-a", "--all", is_flag=True, help="Enable all nodes/cameras.")
async def enable(
    command: Command,
    nodes: Dict[str, Node],
    camera_names: List[str],
    all: bool,
):
    """Enables one or multiple cameras/nodes."""

    if all is True:
        camera_names = list(nodes)

    for name in camera_names:
        if name not in nodes:
            command.warning(text=f"Cannot find node/camera {name}.")
            continue
        nodes[name].enabled = True

    command.finish()
