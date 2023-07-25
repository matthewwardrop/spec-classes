from ._version import __version__, __version_tuple__
from .errors import FrozenInstanceError
from .spec_class import spec_class
from .types import Attr, AttrProxy, MISSING, spec_property

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
    "Attr",
    "AttrProxy",
    "spec_property",
]
