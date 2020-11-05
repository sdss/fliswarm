#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-04
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os

import pytest

from fliswarm.actor import FLISwarmActor
from fliswarm.nuc import NUC


@pytest.fixture(autouse=True)
def mock_docker(mocker):
    """Mock the docker Python module."""

    yield mocker.patch('fliswarm.nuc.DockerClient')


@pytest.fixture(autouse=True)
def mock_ping(mocker):
    """Mock the docker Python module."""

    yield mocker.patch.object(NUC, 'ping')


@pytest.fixture()
async def actor():

    _actor = FLISwarmActor.from_config(os.path.dirname(__file__) +
                                       '/fliswarm.yaml')
    await _actor.start()

    yield _actor
