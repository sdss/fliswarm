#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-11-01
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

from typing import Any, Dict, List, Optional, Set, Union

import fliswarm.node


__all__ = ["select_nodes", "FakeCommand", "IDPool", "subprocess_run_async"]


def select_nodes(
    nodes: Dict[str, Any],
    category: Optional[str] = None,
    names: Optional[Union[str, List[str]]] = None,
) -> Set["fliswarm.node.Node"]:
    """Filters the nodes to command.

    Parameters
    ----------
    nodes
        A dictionary of `.Node` instances to be filtered, keyed by node name.
    category
        A category on which to filter.
    names
        A list or comma-separated string of node names on which to filter.

    Returns
    -------
    :
        A `set` of enabled `.Node` instances that match the provided
        ``category`` or ``names``. If neither ``category`` or ``names``
        are defined, returns all the ``nodes``.
    """

    if names and isinstance(names, str):
        names = list(map(lambda x: x.strip(), names.split(",")))

    valid_nodes = set()
    node_values = nodes.values()

    if names:
        valid_nodes |= set([node for node in node_values if node.name in names])

    if category:
        valid_nodes |= set([node for node in node_values if node.category in category])

    if not names and not category:
        valid_nodes |= set(node_values)

    selected_nodes = set([node for node in valid_nodes if node.enabled])

    return selected_nodes


class FakeCommand:
    """A fake `~clu.command.Command` object that doesn't do anything."""

    def __getattr__(self, item):
        def fake_method(*args, **kwargs):
            pass

        return fake_method


class IDPool:
    """An ID pool that allows to return values to be reused."""

    def __init__(self):

        self.emitted: Set[int] = set()
        self.returned: Set[int] = set()

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

        self.emitted.add(id)
        return id

    def put(self, id: int):
        """Returns an ID to the pool."""

        self.returned.add(id)


async def subprocess_run_async(*args, shell=False):
    """Runs a command asynchronously.

    If ``shell=True`` the command will be executed through the shell. In that case
    the argument must be a single string with the full command. Otherwise, must receive
    a list of program arguments. Returns the output of stdout.
    """

    if shell:
        cmd = await asyncio.create_subprocess_shell(
            args[0],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    else:
        cmd = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    await cmd.communicate()

    return cmd
