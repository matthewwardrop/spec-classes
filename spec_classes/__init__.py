from ._version import __author__, __author_email__, __version__
from .errors import FrozenInstanceError
from .spec_class import spec_class
from .types import Attr, AttrProxy, MISSING, spec_property

__all__ = [
    "__version__",
    "__author__",
    "__author_email__",
    "spec_class",
    "FrozenInstanceError",
    "MISSING",
    "Attr",
    "AttrProxy",
    "spec_property",
]
