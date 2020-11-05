#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-04
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest


@pytest.fixture(autouse=True)
def mock_docker(mocker):
    """Mock the docker Python module."""

    yield mocker.patch('fliswarm.nuc.DockerClient')
