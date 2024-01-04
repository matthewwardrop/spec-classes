import warnings
from typing import Any, Callable, Optional, Type

from .missing import MISSING


class Alias:
    """
    Allows one attribute to act as a alias/proxy for another.

    This is especially useful if you have changed the name of an attribute and
    need to provide backwards compatibility for an indefinite period; or if one
    attribute is supposed to mirror another attribute unless overwritten (e.g.
    the label of a class might be the "key" unless overwritten).

    When a class attribute is assigned a value of `Alias('<attribute name>')`,
    that attribute will proxy/mirror the value of '<attribute name>' instead. If
    some transform is required to satisfy (e.g.) types, then you can also
    optionally specify a unary transform using `Alias('<attribute name>',
    transform=<function>)`. By default, aliased attributes are locally mutable;
    that is, they store local overrides when assigned new values. If you want
    mutations to be passed through to the aliased attribute, then you need to
    specify `passthrough=True`.

    A `fallback` can also be specified for whenever the host attribute has not
    been specified or results in an AttributeError when `Alias` attempts to
    retrieve it.

    Attributes:
        attr: The name of the attribute to be aliased.
        passthrough: Whether to pass through mutations of the `Alias`
            attribute through to the aliased attribute. (default: False)
        transform: An optional unary transform to apply to the value of the
            aliased attribute before returning it as the value of this
            attribute.
        fallback: An optional default value to return if the attribute being
            aliased does not yet have a value (otherwise any errors retrieving
            the underlying aliased attribute value are passed through).
    """

    def __init__(
        self,
        attr: str,
        *,
        passthrough: bool = False,
        transform: Optional[Callable[[Any], Any]] = None,
        fallback: Any = MISSING,
    ):
        self.attr = attr
        self.transform = transform
        self.passthrough = passthrough
        self.fallback = fallback

        self._owner = None
        self._owner_attr = None

    @property
    def override_attr(self):
        if not self._owner_attr and not self.passthrough:
            return None
        return (
            self.attr
            if self.passthrough
            else f"__spec_classes_Alias_{self._owner_attr}_override"
        )

    def __get__(self, instance: Any, owner=None):
        if instance is None:
            return self
        if self._owner_attr and hasattr(instance, self.override_attr):
            return getattr(instance, self.override_attr)
        try:
            return (self.transform or (lambda x: x))(getattr(instance, self.attr))
        except AttributeError:
            if self.fallback is not MISSING:
                return self.fallback
            raise
        except RecursionError as e:
            raise ValueError(
                f"{self.__class__.__name__} for `{instance.__class__.__name__}.{self.attr}` "
                "appears to be self-referential. Please change the `attr` argument to point "
                "to a different attribute."
            ) from e

    def __set__(self, instance, value):
        if not self.override_attr:
            raise RuntimeError(
                f"Attempting to set the value of an `{self.__class__.__name__}` "
                "instance that is not properly associated with a class."
            )
        setattr(instance, self.override_attr, value)

    def __delete__(self, instance):
        delattr(instance, self.override_attr)

    def __set_name__(self, owner, name):
        self._owner = owner
        self._owner_attr = name


class DeprecatedAlias(Alias):
    """
    A subclass of `Alias` that emits deprecation warnings upon interactions.

    Note that `passthrough` is enabled by default for these aliases, since most
    of the time these will be used for backwards compatibility and need to be
    kept in sync with the new attribute values.
    """

    def __init__(
        self,
        attr: str,
        *,
        passthrough: bool = True,
        transform: Optional[Callable[[Any], Any]] = None,
        fallback: Any = MISSING,
        as_of: Optional[str] = None,
        until: Optional[str] = None,
        warning_cls: Type[Warning] = DeprecationWarning,
    ):
        """
        Args:
            attr: The attribute to proxy.
            passthrough: Whether to pass through mutations of the `Alias`
                attribute through to the aliased attribute. (default: True)
            transform: An optional unary transform to apply to the value of the
                aliased attribute before returning it as the value of this
                attribute.
            fallback: An optional default value to return if the attribute being
                aliased does not yet have a value (otherwise any errors retrieving
                the underlying aliased attribute value are passed through).
            as_of: The version as of which the attribute was deprecated.
            until: The version after which this alias will be removed.
            warning_cls: The warning class to use when emitting warnings.
        """
        super().__init__(
            attr, passthrough=passthrough, transform=transform, fallback=fallback
        )
        self.as_of = as_of
        self.until = until
        self.warning_cls = warning_cls

    def __warn(self):
        msg = []
        if self.as_of:
            msg.append(
                f"`{self._owner.__name__}.{self._owner_attr}` was deprecated in version {self.as_of}."
            )
        else:
            msg.append(
                f"`{self._owner.__name__}.{self._owner_attr}` has been deprecated."
            )
        msg.append(f"Please use `{self._owner.__name__}.{self.attr}` instead.")
        if self.until:
            msg.append(
                f"This deprecated alias will be removed in version {self.until}."
            )
        warnings.warn(" ".join(msg), self.warning_cls, stacklevel=3)

    def __get__(self, instance, owner=None):
        self.__warn()
        return super().__get__(instance, owner)

    def __set__(self, instance, value):
        self.__warn()
        super().__set__(instance, value)

    def __delete__(self, instance):
        self.__warn()
        super().__delete__(instance)
