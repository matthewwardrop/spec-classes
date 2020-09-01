from typing import Any, Callable, Optional


# Sentinel for unset inputs to spec_class methods
class _MissingType:
    __instance__ = None

    def __new__(cls):
        if cls.__instance__ is None:
            cls.__instance__ = super(_MissingType, cls).__new__(cls)
        return cls.__instance__

    def __bool__(self):
        return False

    def __repr__(self):
        return "MISSING"

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


MISSING = _MissingType()


class AttrProxy:
    """
    When instantiated using `AttrProxy('<attribute name>')`, and set as the
    value of an attribute; that attribute will return the value of '<attribute name>'
    instead. If some transform is required to satisfy (e.g.) types, then you
    can also optionally specify a unary transform using
    `AttrProxy('<attribute name>', transform=<function>)`. By default, proxied
    attributes are not mutable. If you want to be
    able to modify this attribute, you have two options: you can:
    (1) specify the host attribute using:
    `AttrProxy('<attribute name>', host_attr='<host attribute name>')`
    in which case mutations will be local only to this attribute. Once
    overridden, the transform will no longer be applied to the stored value.
    (2) enable the `passthrough` option, which will pass all mutation operations
    through to the proxied attribute. Note that the transform is not applied to
    these mutation operations, but will still be applied whenever the attribute
    is read.

    A `fallback` can also be specified for whenever the host attribute has not
    been specified or results in an AttributeError when `AttrProxy` attempts to
    retrieve it.
    """

    def __init__(self, attr: str, *, host_attr: str = None, passthrough=False, transform: Optional[Callable[[Any], Any]] = None, fallback=MISSING):
        self.attr = attr
        self.host_attr = host_attr
        self.transform = transform
        self.passthrough = passthrough
        self.fallback = fallback

    @property
    def override_attr(self):
        if not self.host_attr and not self.passthrough:
            return None
        return (
            self.attr
            if self.passthrough else
            f"__spec_class_attrproxy_{self.host_attr}_override"
        )

    def __get__(self, instance: Any, owner=None):
        if instance is None:
            return self
        if self.host_attr and hasattr(instance, self.override_attr):
            return getattr(instance, self.override_attr)
        try:
            return (self.transform or (lambda x: x))(getattr(instance, self.attr))
        except AttributeError as e:
            if self.fallback is not MISSING:
                return self.fallback
            raise e
        except RecursionError:
            raise ValueError(
                f"AttrProxy for `{instance.__class__.__name__}.{self.attr}` appears "
                "to be self-referential. Please change the `attr` argument to point "
                "to a different attribute."
            )

    def __set__(self, instance, value):
        if not self.override_attr:
            raise AttributeError
        setattr(instance, self.override_attr, value)

    def __delete__(self, instance):
        delattr(instance, self.override_attr)
