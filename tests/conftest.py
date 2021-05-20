#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-04
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import json
import os

import pytest

from clu.testing import TestCommand, setup_test_actor

import fliswarm.actor
from fliswarm.actor import FLISwarmActor
from fliswarm.node import Node


def mock_write(self, message):
    """Mocks the client write command."""

    command_id = int(message.split()[0])

    for reply in self.replies:
        message = json.dumps(
            {
                "header": {
                    "message_code": reply[0],
                    "sender": self.name,
                    "command_id": command_id,
                },
                "data": reply[1],
            }
        )
        asyncio.create_task(self.process_message(message))


@pytest.fixture(autouse=True)
def mock_docker(mocker):
    """Mock the docker Python module."""

    mocker.patch.object(asyncio, "sleep")
    mocker.patch.object(fliswarm.actor.FlicameraDevice, "start")

    docker_mock = mocker.patch("fliswarm.node.DockerClient")

    docker_client = mocker.MagicMock()
    docker_mock.return_value = docker_client

    volume = mocker.MagicMock()
    volume.name = "data"
    volume.attrs = {"Options": {"device": ":/data"}}

    container = mocker.MagicMock()
    container.name = "flicamera-gfa1"
    container.short_id = "abcd"

    docker_client.volumes.list.return_value = [volume]
    docker_client.volumes.create.return_value = volume

    docker_client.containers.list.return_value = [container]
    docker_client.containers.run.return_value = container

    yield docker_mock


@pytest.fixture(autouse=True)
def mock_ping(mocker):
    """Mock the docker Python module."""

    yield mocker.patch.object(Node, "ping")


@pytest.fixture(autouse=True)
def mock_asyncio_server(mocker):
    """Mock the docker Python module."""

    mocker.patch("asyncio.start_server")

    mocker.patch.object(fliswarm.actor.FlicameraDevice, "write", new=mock_write)
    mocker.patch.object(
        fliswarm.actor.FlicameraDevice, "is_connected", return_value=True
    )
    fliswarm.actor.FlicameraDevice.replies = []  # type: ignore

    yield


@pytest.fixture()
async def actor():

    _actor = FLISwarmActor.from_config(os.path.dirname(__file__) + "/fliswarm.yaml")
    _actor.timed_commands.pop()
    await _actor.start()

    _actor = await setup_test_actor(_actor)  # type: ignore

    yield _actor

    # Clear replies in preparation for next test.
    _actor.mock_replies.clear()


@pytest.fixture
async def command(actor):

    command = TestCommand(commander_id=1, actor=actor)
    yield command
