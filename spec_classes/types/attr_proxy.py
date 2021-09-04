from typing import Any, Callable, Optional

from .missing import MISSING


class AttrProxy:
    """
    Allows one attribute to act as a proxy for another.

    This is especially useful if you have changed the name of an attribute and
    need to provide backwards compatibility for an indefinite period; or if one
    attribute is supposed to mirror another attribute unless overwritten (e.g.
    the label of a class might be the "key" unless overwritten). This
    functionality could obviously be implemented directly using property, which
    may be advisable if readability is more important than concision.

    When a class attribute is assigned a value of `AttrProxy('<attribute
    name>')`, that attribute will proxy/mirror the value of '<attribute name>'
    instead. If some transform is required to satisfy (e.g.) types, then you can
    also optionally specify a unary transform using `AttrProxy('<attribute
    name>', transform=<function>)`. By default, proxied attributes are locally
    mutable; that is, they store local overrides when assigned new values. If
    you want mutations to be passed through to the proxied attribute, then you
    need to specify `passthrough=True`.

    A `fallback` can also be specified for whenever the host attribute has not
    been specified or results in an AttributeError when `AttrProxy` attempts to
    retrieve it.

    Attributes:
        attr: The name of the attribute to be proxied.
        passthrough: Whether to pass through mutations of the `AttrProxy`
            attribute through to the proxied attribute. (default: False)
        transform: An optional unary transform to apply to the value of the
            proxied attribute before returning it as the value of this
            attribute.
        fallback: An optional default value to return if the attribute being
            proxied does not yet have a value (otherwise any errors retrieving
            the underlying proxied attribute value are passed through).
        host_attr (private): The name of the attribute to which this `AttrProxy`
            instance has been assigned.
    """

    def __init__(
        self,
        attr: str,
        *,
        passthrough=False,
        transform: Optional[Callable[[Any], Any]] = None,
        fallback=MISSING,
    ):
        self.attr = attr
        self.transform = transform
        self.passthrough = passthrough
        self.fallback = fallback

        self.host_attr = None

    @property
    def override_attr(self):
        if not self.host_attr and not self.passthrough:
            return None
        return (
            self.attr
            if self.passthrough
            else f"__spec_classes_attrproxy_{self.host_attr}_override"
        )

    def __get__(self, instance: Any, owner=None):
        if instance is None:
            return self
        if self.host_attr and hasattr(instance, self.override_attr):
            return getattr(instance, self.override_attr)
        try:
            return (self.transform or (lambda x: x))(getattr(instance, self.attr))
        except AttributeError:
            if self.fallback is not MISSING:
                return self.fallback
            raise
        except RecursionError as e:
            raise ValueError(
                f"AttrProxy for `{instance.__class__.__name__}.{self.attr}` appears "
                "to be self-referential. Please change the `attr` argument to point "
                "to a different attribute."
            ) from e

    def __set__(self, instance, value):
        if not self.override_attr:
            raise RuntimeError(
                "Attempting to set the value of an `AttrProxy` instance that is not properly associated with a class."
            )
        setattr(instance, self.override_attr, value)

    def __delete__(self, instance):
        delattr(instance, self.override_attr)

    def __set_name__(self, owner, name):
        self.host_attr = name
