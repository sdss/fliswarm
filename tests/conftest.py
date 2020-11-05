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
from fliswarm.nuc import NUC


def mock_write(self, message):
    """Mocks the client write command."""

    command_id = int(message.split()[0])

    for reply in self.replies:
        message = json.dumps({'header': {'message_code': reply[0],
                                         'sender': self.name,
                                         'command_id': command_id},
                              'data': reply[1]})
        asyncio.create_task(self.process_message(message))


@pytest.fixture(autouse=True)
def mock_docker(mocker):
    """Mock the docker Python module."""

    yield mocker.patch('fliswarm.nuc.DockerClient')


@pytest.fixture(autouse=True)
def mock_ping(mocker):
    """Mock the docker Python module."""

    yield mocker.patch.object(NUC, 'ping')


@pytest.fixture(autouse=True)
def mock_asyncio_server(mocker):
    """Mock the docker Python module."""

    mocker.patch('asyncio.start_server')

    mocker.patch.object(fliswarm.actor.FlicameraDevice, 'write', new=mock_write)
    mocker.patch.object(fliswarm.actor.FlicameraDevice, 'is_connected',
                        return_value=True)
    fliswarm.actor.FlicameraDevice.replies = []

    yield


@pytest.fixture()
async def actor():

    _actor = FLISwarmActor.from_config(os.path.dirname(__file__) +
                                       '/fliswarm.yaml')
    await _actor.start()

    _actor = await setup_test_actor(_actor)

    yield _actor

    # Clear replies in preparation for next test.
    _actor.mock_replies.clear()


@pytest.fixture
async def command(actor):

    command = TestCommand(commander_id=1, actor=actor)
    yield command
