from ._version import __version__, __version_tuple__
from .errors import FrozenInstanceError
from .spec_class import spec_class
from .types import (
    spec_property,
    classproperty,
    Alias,
    DeprecatedAlias,
    Attr,
    AttrProxy,
    MISSING,
    EMPTY,
    SENTINEL,
)

__author__ = "Matthew Wardrop"
__author_email__ = "mpwardrop@gmail.com"

__all__ = [
    "__version__",
    "__version_tuple__",
    "__author__",
    "__author_email__",
    "spec_class",
    "spec_property",
    "classproperty",
    "FrozenInstanceError",
    "Alias",
    "DeprecatedAlias",
    "Attr",
    "AttrProxy",
    "MISSING",
    "EMPTY",
    "SENTINEL",
]
