class FrozenInstanceError(RuntimeError):
    """
    Raised when an attempt is made to mutate a frozen instance.
    """


class NestedAttributeError(RuntimeError):
    """
    Can be raised when an `AttributeError` is raised inside of `property`
    that should be reported rather than swallowed.
    """
