#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-27
# @Filename: test_fliswarm.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from fliswarm.nuc import NUC


def test_nuc(mock_docker):

    nuc = NUC('test-nuc', 'fake-ip')
    nuc.connect()

    assert nuc.client is not None
    assert mock_docker.called_once()


def test_actor(actor):

    assert actor is not None
    assert len(actor.nucs) > 0

    assert actor.nucs['gfa1'].connected
