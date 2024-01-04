import warnings

from .alias import Alias


class AttrProxy(Alias):
    """
    A deprecated alias of `Alias`.
    """

    def __init__(self, attr, **kwargs):
        warnings.warn(
            "`AttrProxy` is deprecated. Please use `Alias` instead. `AttrProxy` will be removed in spec-classes 2.0.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(attr, **kwargs)
