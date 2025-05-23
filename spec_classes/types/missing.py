# Sentinel for unset inputs to spec_class methods


class _MissingType(type):
    """
    This metaclass is used to create singleton falsey classes for use as missing
    and/or sentinel placeholder values.
    """

    def __repr__(cls):
        return cls.__name__

    def __bool__(cls):
        return False

    def __call__(cls):
        return cls

    def __hash__(cls):
        return id(cls)

    def __eq__(cls, other):
        return cls is other


class MISSING(metaclass=_MissingType):
    """
    Used to represent attributes that have not yet been assigned a value.
    """


class EMPTY(metaclass=_MissingType):
    """
    Used to represent empty arguments in methods/etc, which is useful when it is
    important to distinguish between empty and "MISSING" values.
    """


class SENTINEL(metaclass=_MissingType):
    """
    A generic sentinel that can be used to check fallthrough conditions.
    """


class UNCHANGED(metaclass=_MissingType):
    """
    Can be passed in by user to indicate that whatever value is currently set
    should remain unchanged.
    """
