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
    `AttrProxy('<attribute name>', transform=<function>)`. If you want to be
    able to modify this attribute, you must also specify the host attribute using:
    `AttrProxy('<attribute name>', host_attr='<host attribute name>')`
    """

    def __init__(self, attr: str, *, host_attr: str = None, transform: Optional[Callable[[Any], Any]] = None):
        self.attr = attr
        self.host_attr = host_attr
        self.transform = transform
        self.override_attr = f"__spec_class_attrproxy_{self.host_attr}_override"

    def __get__(self, instance: Any, owner=None):
        if instance is None:
            return self
        if self.host_attr and hasattr(instance, self.override_attr):
            return getattr(instance, self.override_attr)
        return (self.transform or (lambda x: x))(getattr(instance, self.attr))

    def __set__(self, instance, value):
        if not self.host_attr:
            raise AttributeError
        setattr(instance, self.override_attr, value)

    def __delete__(self, instance):
        delattr(instance, self.override_attr)
