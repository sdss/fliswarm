#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-05-17
# @Filename: device.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import json

from typing import TYPE_CHECKING, Dict, Optional

from clu import Command
from clu.device import Device
from clu.tools import CommandStatus

from .tools import IDPool


if TYPE_CHECKING:
    from .actor import FLISwarmActor


__all__ = ["FlicameraDevice"]


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
            try:
                await self.stop()
            except ConnectionResetError:
                pass

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
                if "help" in data:
                    for value in data["help"]:
                        dev_command.write(message_code, {"help": value}, validate=False)
                else:
                    dev_command.write(message_code, data, validate=False)

            # Update the device command with the real message code of the
            # received message. Do it with silent=True to avoid CLU
            # informing about the change in status.
            status = CommandStatus.code_to_status(dev_command_message_code)
            dev_command.set_status(status, silent=True)

            # If the command is done, return the command_id to the pool.
            if dev_command.status.is_done:  # type: ignore
                self.running_commands.pop(command_id)
                self.id_pool.put(command_id)

        else:  # This should only happen for broadcasts.
            if len(data) > 0:
                self.fliswarm_actor.write(
                    message_code,
                    data,
                    broadcast=True,
                    validate=False,
                )
