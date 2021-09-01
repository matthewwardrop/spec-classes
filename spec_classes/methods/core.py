# pylint: disable=bad-staticmethod-argument

import copy
from inspect import Parameter
import inspect
import functools

from collections.abc import MutableSequence, MutableMapping, MutableSet
from spec_classes.errors import FrozenInstanceError
from spec_classes.methods.scalar import WithAttrMethod
import textwrap

from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import invalidate_attrs, mutate_attr
from spec_classes.types import MISSING

from .base import MethodDescriptor


class InitMethod(MethodDescriptor):

    name = "__init__"

    @staticmethod
    def init(spec_cls, self, **kwargs):
        instance_metadata = self.__spec_class__

        # Initialise any non-local spec attributes via parent constructors
        for parent in spec_cls.__bases__:
            parent_metadata = getattr(parent, "__spec_class__", None)
            if parent_metadata:
                parent_kwargs = {
                    attr: kwargs.pop(attr)
                    for attr in list(kwargs)
                    if attr in parent_metadata.attrs
                    and instance_metadata.attrs[attr].owner is parent
                }
                if parent_metadata.key and parent_metadata.key not in parent_kwargs:
                    parent_kwargs[parent_metadata.key] = MISSING
                parent.__init__(self, **parent_kwargs)

        is_frozen = instance_metadata.frozen
        instance_metadata.frozen = False

        get_attr_default = getattr(self, "__spec_class_get_attr_default__", None)

        for attr, attr_spec in instance_metadata.attrs.items():

            if not attr_spec.owner is spec_cls:
                continue

            if attr == instance_metadata.init_overflow_attr:
                continue

            # Attempt to lookup in kwargs
            while True:
                value = kwargs.get(attr, MISSING)
                if value is not MISSING:
                    copy_required = not attr_spec.shallow_copy
                    break

                # Attempt to lookup from class default getter
                if get_attr_default:
                    value = get_attr_default(attr)
                    if value is not MISSING:
                        copy_required = True
                        break

                # Attempt to lookup from class attr
                value = getattr(self.__class__, attr, MISSING)
                copy_required=True
                break
            if not (
                value is MISSING
                or inspect.isfunction(value)
                or inspect.isdatadescriptor(value)
            ):
                if copy_required and not isinstance(value, (int, str, tuple)):
                    value = copy.deepcopy(value)
                setattr(self, attr, value)

        if instance_metadata.init_overflow_attr:
            getattr(self, f"with_{instance_metadata.init_overflow_attr}")(  # TODO: avoid this
                {
                    key: value
                    for key, value in kwargs.items()
                    if key not in instance_metadata.annotations
                    or key == instance_metadata.init_overflow_attr
                },
                _inplace=True,
            )

        if is_frozen:
            instance_metadata.frozen = True

    def build_method(self):

        spec_class_key = self.spec_cls.__spec_class__.key
        key_default = Parameter.empty
        if spec_class_key:
            key_default = (
                MISSING if hasattr(self.spec_cls, spec_class_key) else Parameter.empty
            )
            if inspect.isfunction(key_default) or inspect.isdatadescriptor(key_default):
                spec_class_key = None

        return (
            MethodBuilder("__init__", functools.partial(self.init, self.spec_cls))
            .with_preamble(f"Initialise this `{self.spec_cls.__name__}` instance.")
            .with_arg(
                spec_class_key,
                f"The value to use for the `{spec_class_key}` key attribute.",
                default=key_default,
                annotation=self.spec_cls.__spec_class__.annotations.get(spec_class_key),
                only_if=spec_class_key,
            )
            .with_spec_attrs_for(self.spec_cls, defaults=False)
            .build()
        )

class GetAttrMethod(MethodDescriptor):

    name = "__getattr__"

    def build_method(self):

        def __getattr__(self, attr):
            if (
                attr in self.__spec_class__.annotations
                and attr not in self.__dict__
                and not inspect.isdatadescriptor(getattr(self.__class__, attr, None))
            ):
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

    name = "__setattr__"

    def build_method(self):

        def __setattr__(self, attr, value, force=False):
            attr_spec = self.__spec_class__.attrs.get(attr)
            if attr_spec:
                WithAttrMethod.with_attr(attr_spec, self, value, _inplace=True)
                return
            mutate_attr(self, attr=attr, value=value, inplace=True, type_check=True, force=force)

        # Add reference to original __setattr__.
        __setattr__.__raw__ = getattr(
            self.spec_cls.__setattr__, "__raw__", self.spec_cls.__setattr__
        )

        return __setattr__

class DelAttrMethod(MethodDescriptor):

    name = "__delattr__"

    def build_method(self):

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
                or inspect.isfunction(attr_spec.default)
                or inspect.isdatadescriptor(attr_spec.default)
            ):
                self.__delattr__.__raw__(self, attr)
                invalidate_attrs(self, attr)
                return None

            return mutate_attr(
                obj=self,
                attr=attr,
                value=copy.deepcopy(attr_spec.default),  # handle default factory
                inplace=True,
                force=True,
            )

        # Add reference to original __delattr__
        __delattr__.__raw__ = getattr(
            self.spec_cls.__delattr__, "__raw__", self.spec_cls.__delattr__
        )

        return __delattr__


class EqMethod(MethodDescriptor):

    name = "__eq__"

    @staticmethod
    def eq(self, other):
        if not isinstance(other, self.__class__):
            return False
        for attr in self.__spec_class__.annotations:
            value_self = getattr(self, attr, MISSING)
            value_other = getattr(other, attr, MISSING)
            if inspect.ismethod(value_self) and inspect.ismethod(value_other):
                return value_self.__func__ is value_other.__func__
            if value_self != value_other:
                return False
        return True

    def build_method(self):
        return self.eq

class ReprMethod(MethodDescriptor):

    name = "__init__"

    @staticmethod
    def repr(
        self,
        include_attrs=None,
        exclude_attrs=None,
        indent=None,
        indent_threshold=100,
    ):
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
        ambiguous_attrs = set(include_attrs or []).intersection(exclude_attrs or [])
        if ambiguous_attrs:
            raise ValueError(
                f"Some attributes were both included and excluded: {ambiguous_attrs}."
            )

        include_attrs = include_attrs or list(self.__spec_class__.annotations)
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
            if inspect.ismethod(obj) and obj.__self__ is self:
                return f"<bound method {obj.__name__} of self>"
            if hasattr(obj, "__repr__"):
                try:
                    return obj.__repr__(indent=indent)
                except TypeError:
                    pass

            if indent:
                if isinstance(obj, MutableSequence):
                    if not obj:
                        return "[]"
                    items_repr = textwrap.indent(
                        ",\n".join(
                            [object_repr(item, indent=indent) for item in obj]
                        ),
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
                        ",\n".join(
                            [object_repr(item, indent=indent) for item in obj]
                        ),
                        "    ",
                    )
                    return f"{{\n{items_repr}\n}}"

            return repr(obj)

        # Collect unindented representations
        if not indent:
            unindented_attrs = ", ".join(
                [
                    f"{attr}={object_repr(value)}"
                    for attr, value in attr_values.items()
                ]
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

    name = "__deepcopy__"

    @staticmethod
    def deepcopy(self, memo):
        if self.__spec_class__.frozen:
            return self
        new = self.__class__.__new__(self.__class__)
        for attr, value in self.__dict__.items():
            if inspect.ismethod(value) and value.__self__ is self:
                continue
            attr_spec = self.__spec_class__.attrs.get(attr)
            if attr_spec and attr_spec.shallow_copy:
                new.__dict__[attr] = value
            else:
                new.__dict__[attr] = copy.deepcopy(value, memo)
        return new

    def build_method(self):
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
