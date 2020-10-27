#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-10-26
# @Filename: exceptions.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)


class FliswarmError(Exception):
    """A custom core Fliswarm exception"""


class FliswarmWarning(Warning):
    """Base warning for Fliswarm."""


class FliswarmUserWarning(UserWarning, FliswarmWarning):
    """The primary warning class."""
    pass
