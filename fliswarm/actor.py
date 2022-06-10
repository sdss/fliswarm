#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-30
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os

from typing import TypeVar

from clu import BaseActor
from clu.legacy import LegacyActor

from . import __version__
from .commands import command_parser
from .device import FlicameraDevice
from .node import Node


__all__ = ["FLISwarmActor"]


T = TypeVar("T", bound="FLISwarmActor")


class FLISwarmActor(LegacyActor):
    """FLISwarm actor."""

    parser = command_parser

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.version = __version__

        if self.model and self.model.schema:
            self.model.schema["additionalProperties"] = True

        self.observatory = os.environ["OBSERVATORY"]

        self.nodes = {}
        self.flicameras = {}

        self.timed_commands.add_command("status", delay=300)

    async def connect_nodes(self):
        """Connects to the nodes."""

        nconfig = self.config["nodes"][self.observatory]

        self.nodes = {
            name: Node(
                name,
                nconfig[name]["host"],
                daemon_addr=nconfig[name]["docker-client"],
                category=nconfig[name].get("category", None),
            )
            for name in self.config["enabled_nodes"][self.observatory]
        }

        for node in self.nodes.values():
            try:
                await node.connect()
            except ConnectionError:
                pass

    async def start(self) -> BaseActor:
        """Starts the actor."""

        await self.connect_nodes()

        for node in self.nodes.values():

            self.flicameras[node.name] = FlicameraDevice(
                node.name,
                node.addr,
                self.config["nodes"][self.observatory][node.name]["port"],
                self,
            )

            if await node.is_container_running(self.get_container_name(node)):
                try:
                    await self.flicameras[node.name].start()
                except OSError:
                    self.write(
                        "w",
                        text=f"{node.name}: failed to connect to "
                        f"the flicamera device.",
                    )

        self.parser_args = [self.nodes]

        return await super().start()

    def get_container_name(self, node: Node):
        """Returns the name of the container for a node."""

        return self.config["container_name"] + f"-{node.name}"
