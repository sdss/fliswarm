# !usr/bin/env python
# -*- coding: utf-8 -*-
#
# Licensed under a 3-clause BSD license.
#
# @Author: Brian Cherinka
# @Date:   2017-12-05 12:01:21
# @Last modified by:   Brian Cherinka
# @Last Modified time: 2017-12-05 12:19:32

from __future__ import print_function, division, absolute_import


class FliswarmError(Exception):
    """A custom core Fliswarm exception"""

    def __init__(self, message=None):

        message = 'There has been an error' \
            if not message else message

        super(FliswarmError, self).__init__(message)


class FliswarmNotImplemented(FliswarmError):
    """A custom exception for not yet implemented features."""

    def __init__(self, message=None):

        message = 'This feature is not implemented yet.' \
            if not message else message

        super(FliswarmNotImplemented, self).__init__(message)


class FliswarmAPIError(FliswarmError):
    """A custom exception for API errors"""

    def __init__(self, message=None):
        if not message:
            message = 'Error with Http Response from Fliswarm API'
        else:
            message = 'Http response error from Fliswarm API. {0}'.format(message)

        super(FliswarmAPIError, self).__init__(message)


class FliswarmApiAuthError(FliswarmAPIError):
    """A custom exception for API authentication errors"""
    pass


class FliswarmMissingDependency(FliswarmError):
    """A custom exception for missing dependencies."""
    pass


class FliswarmWarning(Warning):
    """Base warning for Fliswarm."""


class FliswarmUserWarning(UserWarning, FliswarmWarning):
    """The primary warning class."""
    pass


class FliswarmSkippedTestWarning(FliswarmUserWarning):
    """A warning for when a test is skipped."""
    pass


class FliswarmDeprecationWarning(FliswarmUserWarning):
    """A warning for deprecated features."""
    pass
