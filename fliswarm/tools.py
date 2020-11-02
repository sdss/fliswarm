#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-01
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

__all__ = ['select_nucs', 'FakeCommand']


def select_nucs(nucs, category=None, names=None):
    """Filters the NUCs to command.

    Parameters
    ----------
    nucs : list
        A list of `.NUC` instances to be filtered.
    category : str
        A category on which to filter.
    names : str or list
        A list or comma-separated string of NUC names on which to filter.

    Returns
    -------
    `set`
        A `set` of NUCs that match the provided ``category`` or ``names``.
        If neither ``category`` or ``names`` are defined, returns all the
        ``nucs``.

    """

    if names and isinstance(names, str):
        names = list(map(lambda x: x.strip(), names.split(',')))

    valid_nucs = set()

    if names:
        valid_nucs |= set([nuc for nuc in nucs if nuc.name in names])

    if category:
        valid_nucs |= set([nuc for nuc in nucs if nuc.category in category])

    if not names and not category:
        valid_nucs |= set(nucs)

    return valid_nucs


class FakeCommand:
    """A fake `~clu.command.Command` object that doesn't do anything."""

    def __getattr__(self, item):
        def fake_method(*args, **kwargs):
            pass
        return fake_method
