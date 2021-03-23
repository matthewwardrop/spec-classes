from ._version import __version__, __author__, __author_email__
from .errors import FrozenInstanceError
from .spec_class import spec_class
from .special_types import MISSING, AttrProxy, spec_property


__all__ = [
    "__version__",
    "__author__",
    "__author_email__",

    "spec_class",

    "FrozenInstanceError",
    "MISSING",
    "AttrProxy",
    "spec_property",
]
