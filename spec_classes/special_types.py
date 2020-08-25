from typing import Any, Callable, Optional


# Sentinel for unset inputs to spec_class methods
class _MissingType:

    def __bool__(self):
        return False

    def __repr__(self):
        return "MISSING"


MISSING = _MissingType()


class AttrProxy:
    """
    When instantiated using `AttrProxy('<attribute name>')`, and set as the
    value of an attribute; that attribute will return the value of '<attribute name>'
    instead. If some transform is required to satisfy (e.g.) types, then you
    can also optionally specify a unary transform using
    `AttrProxy('<attribute name>', transform=<function>)`.
    """

    def __init__(self, attr: str, transform: Optional[Callable[[Any], Any]] = None):
        self.attr = attr
        self.transform = transform

    def __get__(self, instance: Any, owner=None):
        if instance is None:
            return self
        return (self.transform or (lambda x: x))(getattr(instance, self.attr))

    def __set__(self, instance, value):
        setattr(instance, self.attr, value)
