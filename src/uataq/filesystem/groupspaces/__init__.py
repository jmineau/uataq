"""
Group space adapters, each describing one research group's on-disk layout.

Every non-underscore module in this package is imported on package import so
that it registers itself in ``uataq.filesystem.groups``. Only put group space
modules here -- anything else would be imported as one.
"""

from os import listdir
from os.path import dirname, isfile, join

groupspaces = dirname(__file__)
__all__ = [
    f[:-3]
    for f in listdir(groupspaces)
    if isfile(join(groupspaces, f)) and not f.startswith("_")
]

# E402/F403: the star import must follow __all__, which is built above from
# the directory listing -- that is how each group space self-registers.
from . import *  # noqa: E402,F403
