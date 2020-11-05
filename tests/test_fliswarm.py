#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-27
# @Filename: test_fliswarm.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from fliswarm.nuc import NUC


def test_nuc(mock_docker):

    nuc = NUC('test-nuc', '127.0.0.1')
    nuc.connect()

    assert nuc.client is not None
    assert mock_docker.called_once()
