from .errors import FrozenInstanceError
from .spec_class import spec_class
from .types import Alias, DeprecatedAlias, Attr, AttrProxy, MISSING, spec_property

try:
    from ._version import __version__, __version_tuple__
except ImportError:
    __version__ = __version_tuple__ = None

__author__ = "Matthew Wardrop"
__author_email__ = "mpwardrop@gmail.com"

__all__ = [
    "__version__",
    "__version_tuple__",
    "__author__",
    "__author_email__",
    "spec_class",
    "FrozenInstanceError",
    "MISSING",
    "Alias",
    "DeprecatedAlias",
    "Attr",
    "AttrProxy",
    "spec_property",
]
