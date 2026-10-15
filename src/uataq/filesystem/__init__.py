"""
Access to the UATAQ filesystem through ``DataFile`` and ``GroupSpace`` objects.

The UATAQ subpackage operates on the idea that instrument data is collected
differently by each research group, despite potentially being from the same
site or instrument. Furthermore, the format in which data is written, and
therefore read, is dependent on the system that logged the data rather than the
instrument itself. To address this, UATAQ introduces a ``filesystem`` module
which consists of :class:`~uataq.filesystem.core.GroupSpace` and
:class:`~uataq.filesystem.core.DataFile` objects. The
:class:`~uataq.filesystem.core.GroupSpace` objects provide group-specific
methods for working with data from that group, while the
:class:`~uataq.filesystem.core.DataFile` objects handle the actual parsing of
the data files.

Each research group has its own module in ``groupspaces`` where group-specific
code is stored. Each group module must contain a subclass of
:class:`~uataq.filesystem.core.GroupSpace` and define
:class:`~uataq.filesystem.core.DataFile` subclasses for each file format that
the group uses.

All :class:`~uataq.filesystem.core.GroupSpace` objects are stored in the
:data:`~uataq.filesystem.groups` dictionary with the group name as the key.

The default research group can be changed at runtime via
:data:`uataq.filesystem.DEFAULT_GROUP` or *permanently* (until the next update)
by changing its line in ``uataq/filesystem/__init__.py``.
"""

from . import groupspaces
from .core import (
    DataFile,
    GroupSpace,
    cpu_count,
    filter_datafiles,
    groups,
    list_files,
    lvls,
    parse_datafiles,
)

#: Default group to read data from.
DEFAULT_GROUP: str = "lin"

#: Groups dictionary to store GroupSpace objects.
groups: dict

#: Levels of data processing.
lvls: dict


def get_group(group: str | None) -> str:
    """
    Get the group name.

    Parameters
    ----------
    group : str
        The group name.

    Returns
    -------
    str
        The group name.
    """
    if group is None:
        return DEFAULT_GROUP
    elif group not in groups:
        raise ValueError(f"Invalid group: {group}")
    else:
        return group


__all__ = [
    "groupspaces",
    "DataFile",
    "GroupSpace",
    "cpu_count",
    "groups",
    "lvls",
    "list_files",
    "filter_datafiles",
    "parse_datafiles",
]
