#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-05-17
# @Filename: commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import glob as globlib
import itertools
import random as randomlib

from typing import TYPE_CHECKING, Dict, List

import click

from clu.command import Command
from clu.parsers.click import command_parser

from .node import Node
from .tools import select_nodes


if TYPE_CHECKING:
    from fliswarm.actor import FLISwarmActor


@command_parser.command()
async def status(command: Command, nodes: Dict[str, Node]):
    """Outputs the status of the nodes and containers."""

    enabled_nodes = [node for node in nodes.values() if node.enabled]
    command.info(enabledNodes=[node.name for node in enabled_nodes])

    for node in enabled_nodes:
        await node.report_status(command)

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

    assert command.actor
    config = command.actor.config

    async def reconnect_node(node):
        """Reconnect sync. Will be run in an executor."""

        actor = command.actor
        assert actor

        try:
            await node.connect()
            if not (await node.connected()):
                raise ConnectionError()
        except ConnectionError:
            command.warning(
                text=f"Node {node.name} is not pinging back or "
                "the Docker daemon is not running. Try "
                "rebooting the computer."
            )
            return

        # Stop container first, because we cannot remove volumes that are
        # attached to running containers.
        await node.stop_container(
            config["container_name"] + f"-{node.name}",
            config["image"],
            force=True,
            command=command,
        )

        for vname in config["volumes"]:
            vconfig = config["volumes"][vname]
            await node.create_volume(
                vname,
                driver=vconfig["driver"],
                opts=vconfig["opts"],
                force=force,
                command=command,
            )

        return await node.run_container(
            actor.get_container_name(node),
            config["image"],
            volumes=list(config["volumes"]),
            privileged=True,
            registry=config["registry"],
            ports=[config["nodes"][actor.observatory][node.name]["port"]],
            envs={"ACTOR_NAME": node.name, "OBSERVATORY": actor.observatory},
            force=True,
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

    await asyncio.gather(*[reconnect_node(node) for node in c_nodes])

    command.info(text="Waiting 5 seconds before reconnecting the devices ...")
    await asyncio.sleep(5)

    for node in c_nodes:

        container_name = config["container_name"] + f"-{node.name}"
        if not (await node.is_container_running(container_name)):
            continue

        device = command.actor.flicameras[node.name]
        await device.restart()

        if device.is_connected():
            port = device.port
            await node.report_status(command)
            command.debug(text=f"{node.name}: reconnected to device on port {port}.")
        else:
            command.warning(text=f"{node.name}: failed to connect to device.")

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
    "--hard",
    "-f",
    is_flag=True,
    help="Reboots the NUC by power cycling it.",
)
async def reboot(
    command: Command[FLISwarmActor],
    nodes: Dict[str, Node],
    names: str,
    category: str,
    hard: bool,
):
    """Reboot the NUC computer(s)."""

    assert command.actor is not None

    config = command.actor.config

    observatory = command.actor.observatory

    c_nodes = list(select_nodes(nodes, category, names))

    if not hard:
        cmds = []
        for node in c_nodes:
            if node.client:
                node.client.close()

            user = config["nodes"][observatory][node.name]["user"]
            host = config["nodes"][observatory][node.name]["host"]
            cmds.append(
                await asyncio.create_subprocess_shell(
                    f"ssh {user}@{host} sudo reboot",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            )
        await asyncio.gather(*[cmd.communicate() for cmd in cmds])
        for ii, cmd in enumerate(cmds):
            node = c_nodes[ii]
            if cmd.returncode and cmd.returncode in [0, 255]:
                command.info(f"Restarting {node.addr}.")
            else:
                command.error(f"Failed rebooting {node.addr}.")
    else:

        async def execute(mode):
            assert command.actor
            jobs = []
            for node in c_nodes:
                if mode == "off" and node.client:
                    node.client.close()
                power_config = config["power"].copy()
                power_config.update(
                    config["nodes"][observatory][node.name].get("power", {})
                )
                jobs.append(
                    command.actor.send_command(
                        power_config["actor"],
                        power_config["command"]["power" + mode]
                        + " "
                        + power_config.get("device", node.name),
                    )
                )
            command.info(f"Powering {mode} computers.")
            cmds = await asyncio.gather(*jobs)
            if any([cmd.status.did_fail for cmd in cmds]):
                return command.fail(
                    error="Failed commanding power cycling. "
                    "You will need to fix this problem manually."
                )

        # Run on and off commands.
        await execute("off")
        await asyncio.sleep(3)
        await execute("on")

    await asyncio.sleep(5)

    # Issue a status
    await (
        await Command(
            "status",
            actor=command.actor,
            commander_id=command.actor.name,
            parent=command,
        ).parse()
    )

    # Do not finish the command because the child "status" will do that, but see
    # sdss/clu#77.


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

    assert command.actor

    camera_command = " ".join(camera_command)

    c_nodes = select_nodes(nodes, category, names)
    node_names = [node.name for node in c_nodes if node.enabled]

    flicameras = command.actor.flicameras

    connected_nodes = []
    for name in node_names:
        if flicameras[name].is_connected():
            connected_nodes.append(name)
            continue
        command.warning(text=f"Failed connecting to {name}.")

    dev_commands = []

    for name in connected_nodes:
        dev_commands.append(flicameras[name].send_message(command, camera_command))

    await asyncio.gather(*dev_commands, return_exceptions=True)

    # Check if the device commands returned "filename" keywords. If so,
    # bundle them in a single keyword list that indicates all the filenames
    # for exposures taken together.
    filenames = []
    for reply in command.replies:
        if "filename" in reply.message:
            filenames.append(reply.message["filename"][1]["filename"])

    if len(filenames) > 0:
        command.info(filename_bundle=filenames)

    command.finish()


@command_parser.command()
@click.argument("nodes_to_disable", metavar="NODES", nargs=-1, type=str)
@click.option("-a", "--all", is_flag=True, help="Disable all nodes.")
async def disable(
    command: Command,
    nodes: Dict[str, Node],
    nodes_to_disable: List[str],
    all: bool,
):
    """Disables one or multiple cameras/nodes."""

    if all is True:
        nodes_to_disable = list(nodes)

    for name in nodes_to_disable:
        if name not in nodes:
            command.warning(text=f"Cannot find node {name}.")
            continue
        nodes[name].enabled = False

    command.finish()


@command_parser.command()
@click.argument("nodes_to_enable", metavar="NODES", nargs=-1, type=str)
@click.option("-a", "--all", is_flag=True, help="Enable all nodes.")
async def enable(
    command: Command,
    nodes: Dict[str, Node],
    nodes_to_enable: List[str],
    all: bool,
):
    """Enables one or multiple cameras."""

    if all is True:
        nodes_to_enable = list(nodes)

    for name in nodes_to_enable:
        if name not in nodes:
            # If the node is not in enabled_nodes it won't be in nodes. We add it.
            config_nodes = command.actor.config["nodes"][command.actor.observatory]
            if name not in config_nodes:
                command.warning("Node does not exist.")
                continue

            nodes[name] = Node(
                name,
                config_nodes[name]["host"],
                daemon_addr=config_nodes[name]["docker-client"],
                category=config_nodes[name].get("category", None),
            )

        nodes[name].enabled = True

    command.finish()


@command_parser.command(cancellable=True)
@click.argument("GLOB", type=str, required=False)
@click.option("--delay", type=float, default=5, help="Delay between outputting images.")
@click.option("--random", is_flag=True, help="Randomise images.")
async def simulate(
    command: Command,
    nodes: Dict[str, Node],
    glob: str,
    delay=5.0,
    random: bool = False,
):
    """Simulate images being written to disk."""

    # We make GLOB not required so that --stop doesn't need to specify a path,
    # but in this callback we want it defined.
    if glob is None:
        return command.fail(
            error="A valid path pattern is required to start the simulation."
        )

    images = globlib.glob(glob)
    if len(images) == 0:
        return command.fail(error="No images found.")

    sample = globlib.glob(glob)
    if random:
        randomlib.shuffle(sample)
    images_cycle = itertools.cycle(sample)

    while True:
        for node in nodes:
            command.info(filename=[node, node, next(images_cycle)])
        await asyncio.sleep(delay)
