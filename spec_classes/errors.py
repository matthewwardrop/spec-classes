class FrozenInstanceError(RuntimeError):
    """
    Raised when an attempt is made to mutate a frozen instance.
    """


class NestedAttributeError(RuntimeError):
    """
    Can be raised when an `AttributeError` is raised inside of `property`
    that should be reported rather than swallowed.
    """


class BaseTypeError(BaseException):
    """
    A base class for type-related errors that does not derives from
    `BaseException` so we can bypass the generic `Exception` handlers (e.g. for
    typing generics that do something when `__orig_class__` is set). Where
    possible, `TypeError` should be used instead.
    """
