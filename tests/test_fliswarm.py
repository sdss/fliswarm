#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-27
# @Filename: test_fliswarm.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest

from fliswarm.node import Node


pytestmark = [pytest.mark.asyncio]


def test_node(mock_docker):

    node = Node("test-node", "fake-ip")
    node.connect()

    assert node.client is not None
    assert mock_docker.called_once()


def test_actor(actor):

    assert actor is not None
    assert len(actor.nodes) > 0

    assert actor.nodes["gfa1"].connected


async def test_disable_enable(actor):

    command = await actor.invoke_mock_command("disable gfa1")
    assert command.status.did_succeed
    assert actor.nodes["gfa1"].enabled is False
    assert len(actor.mock_replies) == 2

    command = await actor.invoke_mock_command("disable --all")
    assert len([node for node in actor.nodes.values() if node.enabled]) == 0

    command = await actor.invoke_mock_command("enable gfa1")
    assert actor.nodes["gfa1"].enabled is True

    command = await actor.invoke_mock_command("enable --all")
    assert len([node for node in actor.nodes.values() if node.enabled]) == 7


async def test_disable_bad_name(actor):

    command = await actor.invoke_mock_command("disable bad_camera_name")
    assert command.status.did_succeed

    assert actor.mock_replies[1]["text"] == '"Cannot find node/camera bad_camera_name."'


async def test_enable_bad_name(actor):

    command = await actor.invoke_mock_command("enable bad_camera_name")
    assert command.status.did_succeed

    assert actor.mock_replies[1]["text"] == '"Cannot find node/camera bad_camera_name."'


async def test_talk_status(actor):

    actor.flicameras["gfa1"].replies.append((":", {"text": "Camera not connected"}))

    command = await actor.invoke_mock_command("talk -n gfa1 status")
    assert command.status.did_succeed

    assert len(actor.mock_replies) == 3
    assert actor.mock_replies[1].flag == "i"
    assert actor.mock_replies[1]["text"] == 'gfa1,"Camera not connected"'


async def test_reconnect(actor):

    command = await actor.invoke_mock_command("reconnect --force")
    assert command.status.did_succeed


async def test_status(actor):

    await actor.invoke_mock_command("disable --all")
    await actor.invoke_mock_command("enable gfa1")

    actor.mock_replies.clear()

    command = await actor.invoke_mock_command("status")
    assert command.status.did_succeed

    assert len(actor.mock_replies) == 6
    assert actor.mock_replies[2]["node"] == "gfa1,sdss-gfa1,tcp://sdss-gfa1:2375,T,T"
