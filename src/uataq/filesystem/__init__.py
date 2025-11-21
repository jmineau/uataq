"""
UATAQ filesystem init file.

Provides access to the UATAQ filesystem through the use of `DataFile`
and `GroupSpace` objects.
"""

from . import groupspaces
from .core import (
    DataFile,
    GroupSpace,
    TimeRange,
    filter_datafiles,
    groups,
    list_files,
    lvls,
    parse_datafiles,
)

#: Default group to read data from.
DEFAULT_GROUP: str = "lin"
# Update lineno in docs if this changes.

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
    "TimeRange",
    "DataFile",
    "GroupSpace",
    "groups",
    "lvls",
    "list_files",
    "filter_datafiles",
    "parse_datafiles",
]
