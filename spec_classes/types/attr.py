from __future__ import annotations
import copy

import dataclasses
from cached_property import cached_property
from collections.abc import MutableMapping, MutableSequence, MutableSet
from typing import Callable, Iterable, Optional, Union, TYPE_CHECKING

from spec_classes.utils.naming import get_singular_form
from spec_classes.utils.type_checking import (
    get_collection_item_type,
    get_spec_class_for_type,
    type_match,
)

from .missing import MISSING

if TYPE_CHECKING:
    from spec_classes.methods.base import MethodDescriptor


class Attr:
    """
    Configuration for an attribute in a spec-class.

    Instances of this class determine how attributes are treated by
    spec-classes, including which helper methods get added and how attributes
    are initialized. It provides a superset of the functionality available in
    `dataclasses.field/Field`, and can be bootstrapped from a
    `dataclasses.Field` instance.

    Attributes:
        Inherited from dataclasses.Field:
            name
            type
            default=MISSING,
            default_factory=MISSING,
            init=True,
            repr=True,
            hash=None,
            compare=True,
            metadata=None,

        New attributes for spec-class specific behavior


    Attributes u
    """

    @classmethod
    def from_attr_value(cls, name, value, **kwargs):
        if isinstance(value, Attr):
            attr_spec = copy.deepcopy(value)
        elif isinstance(value, dataclasses.Field):
            attr_spec = Attr(
                default=MISSING
                if value.default == dataclasses.MISSING
                else value.default,
                default_factory=MISSING
                if value.default_factory == dataclasses.MISSING
                else value.default_factory,
                init=value.init,
                repr=value.repr,
                hash=value.hash,
                compare=value.compare,
                metadata=value.metadata,
            )
        else:
            attr_spec = Attr(default=value)

        attr_spec.name = name
        for k, v in kwargs.items():
            setattr(attr_spec, k, v)
        return attr_spec

    def __init__(
        self,
        *,
        default=MISSING,
        default_factory=MISSING,
        init=True,
        repr=True,
        hash=None,
        compare=True,
        metadata=None,
        shallow_copy=False,
        invalidated_by=None,
    ):
        # User-specified attributes
        if default is not MISSING and default_factory is not MISSING:
            raise ValueError("cannot specify both default and default_factory")
        self.default = default
        self.default_factory = default_factory
        self.init = init
        self.repr = repr
        self.hash = hash
        self.compare = compare
        self.metadata = metadata

        # Extra attributes
        self.shallow_copy: bool = shallow_copy
        self.invalidated_by: Optional[Iterable[str]] = invalidated_by

        # Auto-populated attributes
        self.name = None
        self.type = None
        self.owner = None
        self.helper_methods: Optional[Iterable[MethodDescriptor]] = None
        self.prepare: Union[Callable] = (
            lambda instance, *obj, **attrs: tuple(obj) if len(obj) > 1 else obj[0]
        )
        self.prepare_item: Union[Callable] = (
            lambda instance, *obj, **attrs: tuple(obj) if len(obj) > 1 else obj[0]
        )

    def __set_name__(self, owner, name):
        self.name = name
        self.type = getattr(owner, "__annotations__", {}).get(name)
        self.owner = owner

        func = getattr(type(self.default), "__set_name__", None)
        if func:
            # There is a __set_name__ method on the descriptor, call
            # it.
            func(self.default, owner, name)

    # Derived attributes

    @cached_property
    def spec_type(self):
        return get_spec_class_for_type(self.type)

    # Collection attributes

    @cached_property
    def is_collection(self) -> bool:
        return self.collection_manager is not None

    @cached_property
    def collection_manager(self):
        from spec_classes.collections import MappingCollection, SequenceCollection, SetCollection

        if type_match(self.type, MutableSequence):
            return SequenceCollection
        elif type_match(self.type, MutableMapping):
            return MappingCollection
        elif type_match(self.type, MutableSet):
            return SetCollection
        else:
            return None

    def get_collection(self, instance, inplace=False):
        return self.collection_manager(
            collection_type=self.type,
            collection=getattr(instance, self.name, MISSING),
            name=f"{instance.__class__.__name__}.{self.name}",
            inplace=inplace,
        )

    @cached_property
    def item_name(self):
        return get_singular_form(self.name)

    @cached_property
    def item_type(self):
        return get_collection_item_type(self.type)

    @cached_property
    def item_spec_type(self):
        return get_spec_class_for_type(self.item_type)

    # Decorators

    def preparer(self, fpreparer: Callable):
        self.prepare = fpreparer
        return self

    def item_preparer(self, fitem_preparer: Callable):
        self.prepare_item = fitem_preparer
        return self
