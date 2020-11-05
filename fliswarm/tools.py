#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-01
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

__all__ = ['select_nucs', 'FakeCommand', 'IDPool']


def select_nucs(nucs, category=None, names=None):
    """Filters the NUCs to command.

    Parameters
    ----------
    nucs : dict
        A dictionary of `.NUC` instances to be filtered, keyed by NUC name.
    category : str
        A category on which to filter.
    names : str or list
        A list or comma-separated string of NUC names on which to filter.

    Returns
    -------
    `set`
        A `set` of enabled `.NUC` instances that match the provided
        ``category`` or ``names``. If neither ``category`` or ``names``
        are defined, returns all the ``nucs``.

    """

    if names and isinstance(names, str):
        names = list(map(lambda x: x.strip(), names.split(',')))

    valid_nucs = set()

    if names:
        valid_nucs |= set([nuc for nuc in nucs.values()
                           if nuc.name in names])

    if category:
        valid_nucs |= set([nuc for nuc in nucs.values()
                           if nuc.category in category])

    if not names and not category:
        valid_nucs |= set(nucs.values())

    enabled_nucs = set([nuc for nuc in valid_nucs if nuc.enabled])

    return enabled_nucs


class FakeCommand:
    """A fake `~clu.command.Command` object that doesn't do anything."""

    def __getattr__(self, item):
        def fake_method(*args, **kwargs):
            pass
        return fake_method


class IDPool:
    """An ID pool that allows to return values to be reused."""

    def __init__(self):

        self.emitted = set()
        self.returned = set()

    def get(self):
        """Returns an ID."""

        if len(self.returned) > 0:
            id = min(self.returned)
            self.returned.remove(id)
            return id

        if len(self.emitted) == 0:
            id = 1
        else:
            id = max(self.emitted) + 1

        self.returned.add(id)
        return id

    def put(self, id):
        """Returns an ID to the pool."""

        self.returned.add(id)
