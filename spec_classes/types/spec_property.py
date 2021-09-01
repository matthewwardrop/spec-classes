from spec_classes.utils.type_checking import check_type, type_label


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

    def __init__(
        self,
        fget=None,
        fset=None,
        fdel=None,
        doc=None,
        overridable=True,
        cache=False,
        invalidated_by=None,
        owner=None,
        attr_name=None,
    ):
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
        return type(self)(
            fget,
            self.fset,
            self.fdel,
            self.__doc__,
            self.overridable,
            self.cache,
            self.invalidated_by,
            self.owner,
            self.attr_name,
        )

    def setter(self, fset):
        return type(self)(
            self.fget,
            fset,
            self.fdel,
            self.__doc__,
            self.overridable,
            self.cache,
            self.invalidated_by,
            self.owner,
            self.attr_name,
        )

    def deleter(self, fdel):
        return type(self)(
            self.fget,
            self.fset,
            fdel,
            self.__doc__,
            self.overridable,
            self.cache,
            self.invalidated_by,
            self.owner,
            self.attr_name,
        )

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
            raise AttributeError(
                f"Property override for `{self._qualified_name}` does not have a getter method."
            )

        # Get value from getter
        value = self.fget(instance)

        # If attribute is annotated with a `spec_class` type, apply any
        # transforms using `_prepare_foo()` methods, and then check that the
        # attribute type is correct.
        if hasattr(instance, "__spec_class__"):
            spec_class_annotations = instance.__spec_class__.annotations
            if self.attr_name in spec_class_annotations:
                try:
                    value = getattr(instance, f"_prepare_{self.attr_name}")(value)
                except AttributeError:
                    pass
                attr_type = spec_class_annotations[self.attr_name]
                if not check_type(value, attr_type):
                    raise ValueError(
                        f"Property override for `{owner.__name__ if owner else ''}.{self.attr_name or ''}` returned an invalid type [got `{repr(value)}`; expecting `{type_label(attr_type)}`]."
                    )

        # Store value in cache is cache is enabled
        if self.cache:
            instance.__dict__[self.attr_name] = value

        return value

    def __set__(self, instance, value):
        if self.fset is None:
            if self.overridable:
                instance.__dict__[self.attr_name] = value
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
