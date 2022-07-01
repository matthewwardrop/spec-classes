# pylint: disable=bad-staticmethod-argument

import functools
import inspect
import textwrap
from collections.abc import MutableMapping, MutableSequence, MutableSet
from typing import Any, Callable, Iterable, Optional

from spec_classes.errors import FrozenInstanceError
from spec_classes.methods.scalar import WithAttrMethod
from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import (
    invalidate_attrs,
    mutate_attr,
    protect_via_deepcopy,
)

from .base import MethodDescriptor


class InitMethod(MethodDescriptor):
    """
    The default implementation of `__init__` for spec-classes.

    This init method iterates over all attributes of a spec-class and
    initializes them onto the instance (provided that a default value can be
    found). It is special in that it respects spec-class super-class
    constructors. If `__init__` has been overwritten on a super-class, and its
    attributes have not been redefined on this sub-class, then it will invoke
    the original constructor for those attributes. This makes use of the
    `owner` attribute of the `Attr` spec, which keeps track of which spec-class
    has claimed an attribute.

    Note: Attributes that have opted out of initialization (i.e. `not
    Attr.init`) will not be initialized. You can use the `__post_init__` hook
    to initialize these attributes if desired.
    """

    method_name = "__init__"

    @staticmethod
    def init(spec_cls, self, **kwargs):
        instance_metadata = self.__spec_class__

        # Unlock the class for mutation during initialization.
        is_frozen = instance_metadata.frozen
        if instance_metadata.owner is spec_cls and instance_metadata.frozen:
            instance_metadata.frozen = False

        # Initialise any non-local spec attributes via parent constructors
        if instance_metadata.owner is spec_cls:
            for parent in reversed(spec_cls.mro()[1:]):
                parent_metadata = getattr(parent, "__spec_class__", None)
                if parent_metadata:
                    parent_kwargs = {}
                    for attr in parent_metadata.attrs:
                        instance_attr_spec = instance_metadata.attrs[attr]
                        if instance_attr_spec.owner is not parent:
                            continue
                        if attr in kwargs:
                            parent_kwargs[attr] = kwargs.pop(attr)
                        else:
                            # Parent constructor may may be overridden, and not pick up
                            # subclass defaults. We pre-emptively solve this here.
                            # If the constructor was not overridden, then no harm is
                            # done (we just looked it up earlier than we had to).
                            # We don't pass missing values in case overridden constructor
                            # has defaults in the signature.
                            instance_default = instance_attr_spec.lookup_default_value(
                                self.__class__
                            )
                            if instance_default is not MISSING:
                                parent_kwargs[attr] = instance_default
                    if parent_metadata.key and parent_metadata.key not in parent_kwargs:
                        parent_kwargs[parent_metadata.key] = MISSING
                    parent.__init__(  # pylint: disable=unnecessary-dunder-call
                        self, **parent_kwargs
                    )

        # For each attribute owned by this spec_cls in `instance_metadata`,
        # initalize the attribute.
        for attr, attr_spec in instance_metadata.attrs.items():

            if (
                not attr_spec.init
                or attr_spec.owner is not spec_cls
                or attr == instance_metadata.init_overflow_attr
            ):
                continue

            value = kwargs.get(attr, MISSING)
            if value is not MISSING:
                # If owner is not spec-class, we have already looked up and
                # handled copying.
                copy_required = (
                    instance_metadata.owner is spec_cls and not attr_spec.do_not_copy
                )
            else:
                value = attr_spec.lookup_default_value(self.__class__)
                copy_required = False

            if value is not MISSING:
                if copy_required:
                    value = protect_via_deepcopy(value)
                setattr(self, attr, value)

        # Finalize initialisation by storing overflow attrs and restoring frozen
        # status.
        if instance_metadata.owner is spec_cls:

            if instance_metadata.init_overflow_attr:
                getattr(
                    self, f"with_{instance_metadata.init_overflow_attr}"
                )(  # TODO: avoid this
                    {
                        key: value
                        for key, value in kwargs.items()
                        if key not in instance_metadata.annotations
                        or key == instance_metadata.init_overflow_attr
                    },
                    _inplace=True,
                )

            if instance_metadata.post_init:
                instance_metadata.post_init(self)

            if is_frozen:
                instance_metadata.frozen = True

    def build_method(self) -> Callable:

        spec_class_key = self.spec_cls.__spec_class__.key
        key_default = inspect.Parameter.empty
        if spec_class_key:
            spec_class_key_spec = (
                self.spec_cls.__spec_class__.attrs.get(spec_class_key) or Attr()
            )
            # If the key has a default, don't require it to be set during
            # construction.
            key_default = (
                MISSING if spec_class_key_spec.has_default else inspect.Parameter.empty
            )

        return (
            MethodBuilder("__init__", functools.partial(self.init, self.spec_cls))
            .with_preamble(f"Initialise this `{self.spec_cls.__name__}` instance.")
            .with_arg(
                spec_class_key,
                desc=f"The value to use for the `{spec_class_key}` key attribute.",
                default=key_default,
                annotation=self.spec_cls.__spec_class__.annotations.get(spec_class_key),
                only_if=spec_class_key,
            )
            .with_spec_attrs_for(
                self.spec_cls,
                desc_template=f"Initial value for `{self.spec_cls.__name__}.{{}}`.",
            )
            .build()
        )


class GetAttrMethod(MethodDescriptor):
    """
    The default implementation of `__getattr__` for spec-classes.

    This method allows for spec-class attributes to be missing, which case an
    `AttributeError` instance is raised explaining that the attribute has not
    been assigned a value. Non spec-class attributes fall back to standard Python
    behavior.
    """

    method_name = "__getattr__"

    def build_method(self) -> Callable:
        def __getattr__(self, attr):
            attr_spec = self.__spec_class__.attrs.get(attr)
            if attr_spec and not attr_spec.is_masked:
                raise AttributeError(
                    f"`{self.__class__.__name__}.{attr}` has not yet been assigned a value."
                )
            return self.__getattr__.__raw__(self, attr)

        # Add reference to original __getattr__ method.
        if hasattr(self.spec_cls, "__getattr__"):
            __getattr__.__raw__ = getattr(
                self.spec_cls.__getattr__, "__raw__", self.spec_cls.__getattr__
            )
        else:
            __getattr__.__raw__ = self.spec_cls.__getattribute__

        return __getattr__


class SetAttrMethod(MethodDescriptor):
    """
    The default implementation of `__setattr__` for spec-classes.

    This implementation guarantees that calling `a.x = blah` is equivalent to
    `a.with_x(blah, _inplace=True)`. Attributes not managed by spec-classes fall
    back to standard python behavior, but are passed through `mutate_attr` in
    order that standard checks (e.g. whether the class is "frozen") are
    performed. This implementation also hooks into `invalidate_attrs`, which
    allows attributes to specify when their caches/values should be reset when
    other attributes are mutated.
    """

    method_name = "__setattr__"

    def build_method(self) -> Callable:
        def __setattr__(self, attr, value, force=False):
            attr_spec = self.__spec_class__.attrs.get(attr)
            if attr_spec:
                WithAttrMethod.with_attr(attr_spec, self, value, _inplace=True)
                return
            mutate_attr(self, attr=attr, value=value, inplace=True, force=force)

        # Add reference to original __setattr__.
        __setattr__.__raw__ = getattr(
            self.spec_cls.__setattr__, "__raw__", self.spec_cls.__setattr__
        )

        return __setattr__


class DelAttrMethod(MethodDescriptor):
    """
    The default implementation of `__delattr__` for spec-classes.

    This implementation ensures that deleting an attribute from a spec-class
    is equivalent to resetting it to the default provided by the class (this is
    equivalent to standard Python behavior except that class attributes are
    copied onto the spec-class instances to protect them from mutations).
    This implementation also hooks into `invalidate_attrs`, which allows
    attributes to specify when their caches/values should be reset when other
    attributes are mutated.
    """

    method_name = "__delattr__"

    def build_method(self) -> Callable:
        def __delattr__(self, attr, force=False):
            if self.__spec_class__.frozen:
                raise FrozenInstanceError(
                    f"Cannot mutate attribute `{attr}` of frozen spec class `{self.__class__.__name__}`."
                )

            attr_spec = self.__spec_class__.attrs.get(attr)

            if (
                force
                or not attr_spec
                or attr_spec.default is MISSING
                or attr_spec.is_masked
            ):
                self.__delattr__.__raw__(self, attr)
                invalidate_attrs(self, attr)
                return None

            return mutate_attr(
                obj=self,
                attr=attr,
                value=protect_via_deepcopy(attr_spec.default),  # handle default factory
                inplace=True,
                force=True,
            )

        # Add reference to original __delattr__
        __delattr__.__raw__ = getattr(
            self.spec_cls.__delattr__, "__raw__", self.spec_cls.__delattr__
        )

        return __delattr__


class EqMethod(MethodDescriptor):
    """
    The default implementation of `__eq__` for spec-classes.

    By default, all spec-class attributes are compared. Any attribute with `not
    Attr.compare` will be skipped.
    """

    method_name = "__eq__"

    @staticmethod
    def eq(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        for attr, attr_spec in self.__spec_class__.attrs.items():
            if not attr_spec.compare:
                continue
            value_self = getattr(self, attr, MISSING)
            value_other = getattr(other, attr, MISSING)
            if inspect.ismethod(value_self) and inspect.ismethod(value_other):
                return value_self.__func__ is value_other.__func__
            if value_self != value_other:
                return False
        return True

    def build_method(self) -> Callable:
        return self.eq


class ReprMethod(MethodDescriptor):
    """
    The default implementation of `__repr__` for spec-classes.

    By default, all spec-class attributes are rendered. Any attribute with `not
    Attr.repr` will be skipped. You can also specify attributes to
    include/exclude when manually calling this method.
    """

    method_name = "__init__"

    @staticmethod
    def repr(
        self,
        include_attrs: Iterable[str] = None,
        exclude_attrs: Iterable[str] = None,
        indent: Optional[bool] = None,
        indent_threshold: int = 100,
        compact: bool = False,
        compact_children: bool = True,
    ) -> str:
        """
        Args:
            include_attrs: An ordered iterable of attrs to include in the
                representation.
            exclude_attrs: An iterable of attrs to exclude from the
                representation.
            indent: Whether to indent. If `True`, indenting is always
                performed. If `False`, indenting is never performed. If
                `None`, indenting is performed when output otherwise exceeds
                `indent_threshold` characters. (default: None)
            indent_threshold: The threshold at which to switch to indented
                representations (see above).
        """
        if compact:
            attrs = ""
            if self.__spec_class__.key:
                attrs = f"{self.__spec_class__.key}={repr(getattr(self, self.__spec_class__.key, MISSING))}, "
            return f"{self.__class__.__name__}({attrs}...)"

        ambiguous_attrs = set(include_attrs or []).intersection(exclude_attrs or [])
        if ambiguous_attrs:
            raise ValueError(
                f"Some attributes were both included and excluded: {ambiguous_attrs}."
            )

        include_attrs = include_attrs or list(
            attr
            for attr, attr_spec in self.__spec_class__.attrs.items()
            if attr_spec.repr
        )
        exclude_attrs = set(exclude_attrs or [])

        # We often re-render things twice to provide the compact
        # representation where possible, and otherwise the long-form. If we
        # have to re-render to indented form, it is cheaper for property
        # methods to have stored the value in this cache rather than have to
        # look it up again.
        attr_values = {
            attr: getattr(self, attr, MISSING)
            for attr in include_attrs
            if attr not in exclude_attrs
        }

        def object_repr(obj, indent=False):
            if obj is self:
                return "<self>"
            if inspect.ismethod(obj):
                obj_parent_name = (
                    "self" if obj.__self__ is self else object_repr(obj.__self__)
                )
                return f"<bound method {obj.__name__} of {obj_parent_name}>"
            if hasattr(obj, "__repr__"):
                try:
                    return obj.__repr__(  # pylint: disable=unnecessary-dunder-call
                        indent=indent, compact=compact_children
                    )
                except TypeError:
                    pass

            if indent:
                if isinstance(obj, MutableSequence):
                    if not obj:
                        return "[]"
                    items_repr = textwrap.indent(
                        ",\n".join([object_repr(item, indent=indent) for item in obj]),
                        "    ",
                    )
                    return f"[\n{items_repr}\n]"
                if isinstance(obj, MutableMapping):
                    if not obj:
                        return "{}"
                    items_repr = textwrap.indent(
                        ",\n".join(
                            [
                                f"{repr(key)}: {object_repr(item, indent=indent)}"
                                for key, item in obj.items()
                            ]
                        ),
                        "    ",
                    )
                    return f"{{\n{items_repr}\n}}"
                if isinstance(obj, MutableSet):
                    if not obj:
                        return "set()"
                    items_repr = textwrap.indent(
                        ",\n".join([object_repr(item, indent=indent) for item in obj]),
                        "    ",
                    )
                    return f"{{\n{items_repr}\n}}"

            return repr(obj)

        # Collect unindented representations
        if not indent:
            unindented_attrs = ", ".join(
                [f"{attr}={object_repr(value)}" for attr, value in attr_values.items()]
            )
            unindented_repr = f"{self.__class__.__name__}({unindented_attrs})"
            if indent is False or (
                len(unindented_repr) <= indent_threshold
                and not any("\n" in attr_repr for attr_repr in unindented_attrs)
            ):
                return unindented_repr

        # Collected indented representation
        indented_attrs = textwrap.indent(
            ",\n".join(
                [
                    f"{attr}={object_repr(value, indent=True)}"
                    for attr, value in attr_values.items()
                ]
            ),
            "    ",
        )
        return f"{self.__class__.__name__}(\n{indented_attrs}\n)"

    def build_method(self):
        return self.repr


class DeepCopyMethod(MethodDescriptor):
    """
    The default implementation of `__deepcopy__` for spec-classes.

    This overrides the behavior of `copy.deepcopy` on spec-classes, to respect
    the shallow-copying preferences of attributes.
    """

    method_name = "__deepcopy__"

    @staticmethod
    def deepcopy(self, memo):
        if self.__spec_class__.frozen or self.__spec_class__.do_not_copy:
            return self
        new = self.__class__.__new__(self.__class__)
        for attr, value in self.__dict__.items():
            if inspect.ismethod(value) and value.__self__ is self:
                continue
            attr_spec = self.__spec_class__.attrs.get(attr)
            if attr_spec and attr_spec.do_not_copy:
                new.__dict__[attr] = value
            else:
                new.__dict__[attr] = protect_via_deepcopy(value, memo)
        return new

    def build_method(self) -> Callable:
        return self.deepcopy


CORE_METHODS = [
    InitMethod,
    GetAttrMethod,
    SetAttrMethod,
    DelAttrMethod,
    EqMethod,
    ReprMethod,
    DeepCopyMethod,
]
