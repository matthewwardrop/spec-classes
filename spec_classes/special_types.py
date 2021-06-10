from typing import Any, Callable, Optional

from spec_classes.utils.type_checking import check_type, type_label


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
    attributes are locally mutable; that is, they store local overrides when
    assigned new values. If you want mutations to be passed through to the
    proxied attribute, then you need to specify `passthrough=True`.

    A `fallback` can also be specified for whenever the host attribute has not
    been specified or results in an AttributeError when `AttrProxy` attempts to
    retrieve it.
    """

    def __init__(self, attr: str, *, passthrough=False, transform: Optional[Callable[[Any], Any]] = None, fallback=MISSING):
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

    def __set_name__(self, owner, name):
        self.host_attr = name


class spec_property:
    """
    An enriched property-like decorator for use by spec-classes (with graceful
    fallbacks for non-spec_class use-cases).

    In particular, this decorator extends the builtin `property` API offered by
    Python by:
    - Allowing properties to be overridable by default (pass `overridable=False`
        to `spec_property` during decoration to disable).
    - Allowing property getters to be cached during first invocation (pass
        `cache=True` during decoration to enable).

    Additionally, when used in conjunction with spec-class attributes, it:
    - Applies any transforms provided by `._prepare_<attr_name>()` methods to
        the output of property getters.
    - Type-checks the result of property getter invocations (after any
        transforms described above).

    Usage:
        @spec_class
        class MySpecClass:
            my_field: int
            my_field2: str

            @spec_property
            def my_field(self):
                return 10

            @spec_property(cache=True, overridable=False)
            def my_field2(self):
                return "string"
    """

    def __new__(cls, *args, **kwargs):
        if not args:
            def decorator(func):
                return spec_property(func, **kwargs)
            return decorator
        return super().__new__(cls)

    def __init__(self, fget=None, fset=None, fdel=None, doc=None, overridable=True, cache=False, invalidated_by=None, owner=None, attr_name=None):
        # Standard `property` attributes
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

        # Novel attributes
        self.overridable = overridable
        self.cache = cache
        self.invalidated_by = invalidated_by or []
        self.owner = owner
        self.attr_name = attr_name

    # Standard Python property methods to allow customization of getters, setters and deleters.

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.__doc__, self.overridable, self.cache, self.invalidated_by, self.owner, self.attr_name)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.__doc__, self.overridable, self.cache, self.invalidated_by, self.owner, self.attr_name)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.__doc__, self.overridable, self.cache, self.invalidated_by, self.owner, self.attr_name)

    # Descriptor protocol implementation

    def __set_name__(self, owner, name):
        self.owner = owner
        self.attr_name = name

    @property
    def _qualified_name(self):
        return f"{self.owner.__name__ if self.owner else ''}.{self.attr_name or ''}"

    def __get__(self, instance, owner=None):
        # If lookup occuring on owner class.
        if instance is None:
            return self

        # If value exists in cache or has been overridden
        if (self.overridable or self.cache) and self.attr_name in instance.__dict__:
            return instance.__dict__[self.attr_name]

        # If there is no assigned getter
        if self.fget is None:
            raise AttributeError(f"Property override for `{self._qualified_name}` does not have a getter method.")

        # Get value from getter
        value = self.fget(instance)

        # If attribute is annotated with a `spec_class` type, apply any
        # transforms using `_prepare_foo()` methods, and then check that the
        # attribute type is correct.
        spec_class_annotations = getattr(instance, '__spec_class_annotations__', {})
        if self.attr_name in spec_class_annotations:
            try:
                value = getattr(instance, f'_prepare_{self.attr_name}')(value)
            except AttributeError:
                pass
            attr_type = spec_class_annotations[self.attr_name]
            if not check_type(value, attr_type):
                raise ValueError(f"Property override for `{owner.__name__ if owner else ''}.{self.attr_name or ''}` returned an invalid type [got `{repr(value)}`; expecting `{type_label(attr_type)}`].")

        # Store value in cache is cache is enabled
        if self.cache:
            instance.__dict__[self.attr_name] = value

        return value

    def __set__(self, instance, value):
        if self.fset is None:
            if self.overridable:
                instance.__dict__[self.attr_name] = value
                return
            raise AttributeError(f"Property override for `{self._qualified_name}` does not have a setter and/or is not configured to be overridable.")
        self.fset(instance, value)

    def __delete__(self, instance):
        if self.fdel is None:
            if (self.overridable or self.cache) and self.attr_name in instance.__dict__:
                del instance.__dict__[self.attr_name]
                return
            raise AttributeError(f"Property override for `{self._qualified_name}` has no cache or override to delete.")
        self.fdel(instance)

    # Let spec-class know to invalidate any cache based on `.invalidate_by`
    @property
    def __spec_class_invalidated_by__(self):
        if isinstance(self.invalidated_by, str):
            return [self.invalidated_by]
        return self.invalidated_by
