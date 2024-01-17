import inspect
import warnings
from abc import abstractmethod
from typing import Tuple

from cached_property import cached_property

from spec_classes.errors import NestedAttributeError
from spec_classes.utils.mutation import prepare_attr_value
from spec_classes.utils.stackdepth import get_spec_classes_depth
from spec_classes.utils.type_checking import check_type, type_label


class _spec_property_base:
    """
    Basic abstract implementation of the the descriptor protocol for properties.
    """

    ALLOWED_ATTRS: Tuple[str, ...] = ()

    def __new__(cls, *args, **kwargs):
        if not args:

            def decorator(func):
                return cls(func, **kwargs)

            return decorator
        return super().__new__(cls)

    def __init__(
        self,
        fget=None,
        fset=None,
        fdel=None,
        *,
        doc=None,
        overridable=True,
        warn_on_override=False,
        cache=False,
        allow_attribute_error=True,
        owner=None,
        attr_name=None,
        **attrs,
    ):
        """
        Args:
            fget: The getter function.
            fset: The setter function.
            fdel: The deleter function.
            doc: An override for attribute docstrings (otherwise it is lifted
                from the getter function).
            overridable: Whether the property value should be overridable by
                users (in which case the override is stored as a cache).
            warn_on_override: Whether to warn the user when the property getter
                is overridden. Can be a boolean, string, or `Warning` instance.
                If non-boolean, then it is treated as the message to present to
                the user using `warnings.warn`.
            cache: Whether to cache attribute results whenever a cache does not
                already exist.
            allow_attribute_error: Whether to allow functions to raise an
                `AttributeError`. If `False`, such errors will be caught and
                reraised as `NestedAttributeErrors`, which makes it easier to
                debug when property methods are failing due to attribute errors.
            owner: The class that owns this property.
            attr_name: The attribute of the property on `owner`.
        """
        # Standard `property` attributes
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

        # Novel attributes
        self.overridable = overridable
        self.warn_on_override = warn_on_override
        self.cache = cache
        self.allow_attribute_error = allow_attribute_error
        self.owner = owner
        self.attr_name = attr_name
        self.attrs = attrs

    # Standard Python property methods to allow customization of getters, setters and deleters.

    def getter(self, fget):
        return type(self)(
            fget,
            self.fset,
            self.fdel,
            doc=self.__doc__,
            overridable=self.overridable,
            cache=self.cache,
            allow_attribute_error=self.allow_attribute_error,
            owner=self.owner,
            attr_name=self.attr_name,
            **self.attrs,
        )

    def setter(self, fset):
        return type(self)(
            self.fget,
            fset,
            self.fdel,
            doc=self.__doc__,
            overridable=self.overridable,
            cache=self.cache,
            allow_attribute_error=self.allow_attribute_error,
            owner=self.owner,
            attr_name=self.attr_name,
            **self.attrs,
        )

    def deleter(self, fdel):
        return type(self)(
            self.fget,
            self.fset,
            fdel,
            doc=self.__doc__,
            overridable=self.overridable,
            cache=self.cache,
            allow_attribute_error=self.allow_attribute_error,
            owner=self.owner,
            attr_name=self.attr_name,
            **self.attrs,
        )

    # Descriptor protocol implementation

    def __set_name__(self, owner, name):
        self.owner = owner
        self.attr_name = name

    @property
    def _qualified_name(self):
        return f"{self.owner.__name__ if self.owner else ''}.{self.attr_name or ''}"

    @abstractmethod
    def __get__(self, obj, objtype=None):
        ...  # pragma: no cover

    @abstractmethod
    def __set__(self, obj, value):
        ...  # pragma: no cover

    @abstractmethod
    def __delete__(self, obj):
        ...  # pragma: no cover


class spec_property(_spec_property_base):
    """
    An enriched property-like decorator for use by spec-classes (with graceful
    fallbacks for non-spec_class use-cases).

    In particular, this decorator extends the builtin `property` API offered by
    Python by allowing for:
    - properties to be overridable by default (pass `overridable=False`
        to `spec_property` during decoration to disable).
    - property getters to be cached during first invocation (pass
        `cache=True` during decoration to enable).
    - spec-classes attribute invalidation (pass `invalidated_by=['attr', ...]`).
    - suppression of nested `AttributeErrors`, which can make life difficult
      during debugging (pass `allow_attribute_error=False`).

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

    ALLOWED_ATTRS = ("invalidated_by",)

    def __init__(
        self,
        fget=None,
        fset=None,
        fdel=None,
        *,
        doc=None,
        overridable=True,
        warn_on_override=False,
        cache=False,
        invalidated_by=None,
        allow_attribute_error=True,
        owner=None,
        attr_name=None,
    ):
        """
        Args:
            fget: The getter function.
            fset: The setter function.
            fdel: The deleter function.
            doc: An override for attribute docstrings (otherwise it is lifted
                from the getter function).
            overridable: Whether the property value should be overridable by
                users (in which case the override is stored as a cache).
            warn_on_override: Whether to warn the user when the property getter
                is overridden. Can be a boolean, string, or `Warning` instance.
                If non-boolean, then it is treated as the message to present to
                the user using `warnings.warn`.
            cache: Whether to cache attribute results whenever a cache does not
                already exist.
            invalidated_by: When attached to a spec-class, attributes that
                should trigger the cache to be invalidated.
            allow_attribute_error: Whether to allow functions to raise an
                `AttributeError`. If `False`, such errors will be caught and
                reraised as `NestedAttributeErrors`, which makes it easier to
                debug when property methods are failing due to attribute errors.
            owner: The class that owns this property.
            attr_name: The attribute of the property on `owner`.
        """
        super().__init__(
            fget=fget,
            fset=fset,
            fdel=fdel,
            doc=doc,
            overridable=overridable,
            warn_on_override=warn_on_override,
            cache=cache,
            owner=owner,
            attr_name=attr_name,
            allow_attribute_error=allow_attribute_error,
            invalidated_by=invalidated_by,
        )

    @property
    def invalidated_by(self):
        return self.attrs.get("invalidated_by") or ()

    def __get__(self, instance, owner=None):
        # If lookup occuring on owner class.
        if instance is None:
            return self

        # If value exists in cache or has been overridden
        if (self.overridable or self.cache) and self.attr_name in instance.__dict__:
            return instance.__dict__[self.attr_name]

        # If there is no assigned getter
        if self.fget is None:
            raise AttributeError(
                f"Property override for `{self._qualified_name}` does not have a getter method."
            )

        # Get value from getter
        try:
            value = self.fget(instance)
        except AttributeError as e:
            if self.allow_attribute_error:
                raise
            raise NestedAttributeError(e) from e

        # If attribute is annotated with a `spec_class` type, apply any
        # transforms using `_prepare_foo()` methods, and then check that the
        # attribute type is correct.
        spec_metadata = getattr(instance, "__spec_class__", None)
        if spec_metadata and self.attr_name in spec_metadata.attrs:
            attr_spec = spec_metadata.attrs[self.attr_name]
            value = prepare_attr_value(attr_spec, instance, value)
            if not check_type(value, attr_spec.type):
                raise ValueError(
                    f"Property override for `{owner.__name__ if owner else ''}.{self.attr_name or ''}` returned an invalid type [got `{repr(value)}`; expecting `{type_label(attr_spec.type)}`]."
                )

        # Store value in cache is cache is enabled
        if self.cache:
            instance.__dict__[self.attr_name] = value

        return value

    def __set__(self, instance, value):
        if self.fset is None:
            if self.overridable:
                instance.__dict__[self.attr_name] = value
                if self.warn_on_override:
                    warnings.warn(
                        f"Property `{self._qualified_name}` is now overridden and will not update based on instance state."
                        if isinstance(self.warn_on_override, bool)
                        else self.warn_on_override,
                        stacklevel=get_spec_classes_depth(),
                    )
                return
            raise AttributeError(
                f"Property override for `{self._qualified_name}` does not have a setter and/or is not configured to be overridable."
            )
        self.fset(instance, value)

    def __delete__(self, instance):
        if self.fdel is None:
            if (self.overridable or self.cache) and self.attr_name in instance.__dict__:
                del instance.__dict__[self.attr_name]
                return
            raise AttributeError(
                f"Property override for `{self._qualified_name}` has no cache or override to delete."
            )
        self.fdel(instance)

    # Let spec-class know to invalidate any cache based on `.invalidate_by`
    @property
    def __spec_class_invalidated_by__(self):
        if isinstance(self.invalidated_by, str):
            return [self.invalidated_by]
        return self.invalidated_by


class classproperty(_spec_property_base):
    """
    An analog of `property` for classmethods. It has the same API, but acts on
    methods which take the class as the first argument. Note, though, that class
    properties have no access to spec-class state, and invalidation does not
    make sense and will not occur.

    Methods decorated with this class are transformed into class properties.
    Just like with regular properties, you can override the property setters and
    deleters, but note that only getters will be invoked when interacting with
    the classproperty directly on classes (as compared to instances). If you
    need these to work for direct class interactions too please explore
    metaclasses.

    This is primarily useful when it is useful to cache expensive lookups once
    per class (rather than per-instance).
    """

    ALLOWED_ATTRS = ("cache_per_subclass",)

    def __init__(
        self,
        fget=None,
        fset=None,
        fdel=None,
        *,
        doc=None,
        overridable=False,  # Note: different from spec_property
        warn_on_override=False,
        cache=False,
        cache_per_subclass=False,
        allow_attribute_error=True,
        owner=None,
        attr_name=None,
        **attrs,
    ):
        """
        Args:
            fget: The getter function.
            fset: The setter function.
            fdel: The deleter function.
            doc: An override for attribute docstrings (otherwise it is lifted
                from the getter function).
            overridable: Whether the property value should be overridable by
                users (in which case the override is stored as a cache).
            warn_on_override: Whether to warn the user when the property getter
                is overridden. Can be a boolean, string, or `Warning` instance.
                If non-boolean, then it is treated as the message to present to
                the user using `warnings.warn`.
            cache: Whether to cache attribute results whenever a cache does not
                already exist.
            cache_per_subclass: Whether subclasses should have the property
                cached cached separately.
            allow_attribute_error: Whether to allow functions to raise an
                `AttributeError`. If `False`, such errors will be caught and
                reraised as `NestedAttributeErrors`, which makes it easier to
                debug when property methods are failing due to attribute errors.
            owner: The class that owns this property.
            attr_name: The attribute of the property on `owner`.
        """
        super().__init__(
            fget=fget,
            fset=fset,
            fdel=fdel,
            doc=doc,
            overridable=overridable,
            warn_on_override=warn_on_override,
            cache=cache,
            cache_per_subclass=cache_per_subclass,
            allow_attribute_error=allow_attribute_error,
            owner=owner,
            attr_name=attr_name,
        )

    @property
    def cache_per_subclass(self):
        return self.attrs.get("cache_per_subclass", False)

    @property
    def fget(self):
        return self._fget

    @fget.setter
    def fget(self, fget):
        if fget and not isinstance(fget, (classmethod, staticmethod)):
            fget = classmethod(fget)
        self._fget = fget

    @property
    def fset(self):
        return self._fset

    @fset.setter
    def fset(self, fset):
        if fset and not isinstance(fset, (classmethod, staticmethod)):
            fset = classmethod(fset)
        self._fset = fset

    @property
    def fdel(self):
        return self._fdel

    @fdel.setter
    def fdel(self, fdel):
        if fdel and not isinstance(fdel, (classmethod, staticmethod)):
            fdel = classmethod(fdel)
        self._fdel = fdel

    @cached_property
    def _cache(self):
        return {}

    def _cache_key(self, objtype):
        return objtype if self.cache_per_subclass else None

    def __get__(self, obj, objtype=None):
        # If value exists in cache or has been overridden
        cache_key = self._cache_key(objtype)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # If there is no assigned getter
        if self.fget is None:
            raise AttributeError(
                f"Class property for `{self._qualified_name}` does not have a getter method."
            )

        # Get value from getter
        try:
            value = self.fget.__get__(obj, objtype)()
        except AttributeError as e:
            if self.allow_attribute_error:
                raise
            raise NestedAttributeError(e) from e

        # Store value in cache is cache is enabled
        if self.cache and objtype:
            self._cache[cache_key] = value

        return value

    def __set__(self, obj, value):
        if not inspect.isclass(obj):
            obj = type(obj)
        if self.fset is None:
            if self.overridable:
                self._cache[self._cache_key(obj)] = value
                if self.warn_on_override:
                    warnings.warn(
                        f"Class property `{self._qualified_name}` is now overridden and will not update based on class state."
                        if isinstance(self.warn_on_override, bool)
                        else self.warn_on_override,
                        stacklevel=get_spec_classes_depth(),
                    )
                return
            raise AttributeError(
                f"Class property for `{self._qualified_name}` does not have a setter and/or is not configured to be overridable."
            )
        self.fset.__get__(None, obj)(value)

    def __delete__(self, obj):
        if not inspect.isclass(obj):
            obj = type(obj)
        if self.fdel is None:
            cache_key = self._cache_key(obj)
            if cache_key in self._cache:
                del self._cache[cache_key]
                return
            raise AttributeError(
                f"Class property for `{self._qualified_name}` has no cache or override to delete."
            )
        self.fdel.__get__(None, obj)()
