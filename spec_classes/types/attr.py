from __future__ import annotations

import copy
import dataclasses
import functools
import inspect
from collections.abc import MutableMapping, MutableSequence, MutableSet
from typing import Any, Callable, Iterable, Optional, TYPE_CHECKING, Type

from cached_property import cached_property

from spec_classes.utils.naming import get_singular_form
from spec_classes.utils.type_checking import (
    get_collection_item_type,
    get_spec_class_for_type,
    type_label,
    type_match,
)

from .missing import MISSING

if TYPE_CHECKING:  # pragma: no cover
    from spec_classes.collections.base import CollectionAttrMutator
    from spec_classes.methods.base import AttrMethodDescriptor


class Attr:
    """
    Attribute specification.

    This class stores the configuration associated with a spec-class attribute,
    and instances of this class determine how attributes are treated by
    spec-classes, including which helper methods get added and how attributes
    are initialized.

    Instances of this class are either generated entirely from class metadata,
    or lifted from the `Attr` instance provided by the user as the value of an
    attribute. Its API is intentionally 100% compatible with Pythons
    `dataclasses.field()`, with a few extra attributes specific to spec-classes.

    Attributes:
        Imitating `dataclasses.Field`:
            name: The name of the attribute.
            type: The type of the attribute.
            default: The default value to assign to the attribute (only one of
                `default` or `default_factory` can be provided).
            default_factory: A function to call to generate a default value
                (only one of `default` or `default_factory` can be provided).
            init: Whether to include this attribute in the automatically
                generated constructor.
            repr: Whether to include this attribute in the string
                representation.
            compare: Whether to include this attribute when evaluating the
                equality of two instances of the spec-class.
            hash: Whether to include this attribute when generating a hash
                (should nearly always be left as `None`; see
                https://docs.python.org/3/library/dataclasses.html#dataclasses.field
                for more details).
            metadata: Additional metadata about the attribute that is not used
                by spec-classes.

        Spec-class specific attributes settable in constructor:
            desc: A description for this attribute, which will appear in
                auto-generated documentation.
            do_not_copy: Whether this attribute should not be copied when its
                parent is copied, and instead share a reference between the old
                and new parents.
            invalidated_by: An optional sequence of the names of attributes
                which should invalidate (reset/delete) this attribute (or if it
                is a `spec_property`, its cache).

        Spec-class specific attributes auto-populated during `spec_class`
        generation:
            owner: A reference to the spec-class that originally defined this
                attribute. If a spec-class is a subclass of another spec-class,
                this may not be the same as the class of the current spec-class
                instance.
            is_masked: Whether the attribute is masked by a method or
                descriptor.
            helper_methods: The method (descriptor)s to add to the class in
                order to help manage this attribute.
            prepare: A optional callable used to cast incoming attribute values
                into the appropriate type for the attribute. This casting
                happens before type-checking.
            prepare_item: A optional callable used to cast new items into a
                collection into the appropriate type for the collection. This
                casting happens before type-checking.

        Derived attributes (cached):
            qualified_name: The name of the attribute to use in error logs,
                of form: "<spec-class>.<attr-name>". If `owner` is not set, this
                will just be "<attr-name>".
            spec_type: The spec-class associated with `type`, if we can resolve
                one, otherwise `None`.
            is_collection: Whether this attribute is a collection based on its
                `type`.
            collection_manager: The `CollectionAttrMutator` subclass to use for this
                attribute (derived from `type`).
            item_name: The singular name of this attribute (derived from
                `name`).
            item_type: The type of items contained within the collection (if it
                is a collection).
            item_spec_type: The spec-class associated with `item_type`, if we
                can resolve one, otherwise `None`.
            item_spec_key_type: The type of the key if the item type is a spec
                class and it has a key, or `None` otherwise.
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
                compare=value.compare,
                hash=value.hash,
                metadata=value.metadata,
            )
        else:
            # If attribute is a function or descriptor, we shouldn't interfere with them.
            if inspect.isfunction(value) or inspect.isdatadescriptor(value):
                kwargs["is_masked"] = True
            attr_spec = Attr(default=value)

        attr_spec.name = name
        for k, v in kwargs.items():
            setattr(attr_spec, k, v)
        return attr_spec

    def __init__(
        self,
        *,
        default: Any = MISSING,
        default_factory: Callable[[], Any] = MISSING,
        init: bool = True,
        repr: bool = True,  # pylint: disable=redefined-builtin
        compare: bool = True,
        hash: Optional[bool] = None,  # pylint: disable=redefined-builtin
        metadata: Optional[Any] = None,
        desc: Optional[str] = None,
        do_not_copy: bool = False,
        invalidated_by: Optional[Iterable[str]] = None,
    ):
        # User-specified attributes
        if default is not MISSING and default_factory is not MISSING:
            raise ValueError(
                "Only one of `default` and `default_factory` can be specified."
            )
        self.default = default
        self.default_factory = default_factory
        self.init = init
        self.repr = repr
        self.compare = compare
        self.hash = compare if hash is None else hash
        self.metadata = metadata

        # Extra attributes
        self.desc = desc
        self.do_not_copy = do_not_copy
        self.invalidated_by = invalidated_by

        # Auto-populated attributes
        self.name: str = None
        self.type: Type = None
        self.owner: Type = None
        self.is_masked: bool = False
        self.helper_methods: Optional[Iterable[AttrMethodDescriptor]] = None
        self.prepare: Optional[Callable[[Any], Any]] = None
        self.prepare_item: Optional[Callable[[Any], Any]] = None

    def __set_name__(self, owner, name):
        self.name = name
        self.type = getattr(owner, "__annotations__", {}).get(name)
        self.owner = owner

        # Pass on name to default value, if it is a descriptor.
        set_name = getattr(type(self.default), "__set_name__", None)
        if set_name:
            set_name(self.default, owner, name)

    # Derived attributes

    @cached_property
    def qualified_name(self) -> str:
        if self.owner:
            return f"{type_label(self.owner)}.{self.name}"
        return self.name

    @cached_property
    def spec_type(self) -> Optional[Type]:
        return get_spec_class_for_type(self.type)

    @cached_property
    def spec_type_polymorphic(self) -> Optional[Type]:
        return get_spec_class_for_type(self.type, allow_polymorphic=True)

    @cached_property
    def constructor(self) -> Optional[Type]:
        return self.spec_type_polymorphic or self.type

    # Collection attributes

    @cached_property
    def is_collection(self) -> bool:
        return self.collection_mutator_type is not None

    @cached_property
    def collection_mutator_type(self) -> Optional[Type[CollectionAttrMutator]]:
        from spec_classes.collections import (
            MappingMutator,
            SequenceMutator,
            SetMutator,
        )

        if type_match(self.type, MutableSequence):
            return SequenceMutator
        if type_match(self.type, MutableMapping):
            return MappingMutator
        if type_match(self.type, MutableSet):
            return SetMutator
        return None

    @cached_property
    def get_collection_mutator(self) -> Optional[Callable[..., CollectionAttrMutator]]:
        return functools.partial(self.collection_mutator_type, self)

    @cached_property
    def item_name(self) -> str:
        return get_singular_form(self.name)

    @cached_property
    def item_type(self) -> Optional[Type]:
        return get_collection_item_type(self.type)

    @cached_property
    def item_spec_type(self) -> Optional[Type]:
        return get_spec_class_for_type(self.item_type)

    @cached_property
    def item_spec_key_type(self) -> Optional[Type]:
        if self.item_spec_type and self.item_spec_type.__spec_class__.key:
            return self.item_spec_type.__spec_class__.annotations[
                self.item_spec_type.__spec_class__.key
            ]
        return None

    @cached_property
    def item_spec_type_polymorphic(self) -> Optional[Type]:
        return get_spec_class_for_type(self.item_type, allow_polymorphic=True)

    @cached_property
    def item_spec_polymorphic_key_type(self) -> Optional[Type]:
        if (
            self.item_spec_type_polymorphic
            and self.item_spec_type_polymorphic.__spec_class__.key
        ):
            return self.item_spec_type_polymorphic.__spec_class__.annotations[
                self.item_spec_type_polymorphic.__spec_class__.key
            ]
        return None

    @cached_property
    def item_constructor(self) -> Optional[Type]:
        return self.item_spec_type_polymorphic or self.item_type

    # Helpers
    def lookup_default_value(self, spec_cls: Type) -> Any:
        """
        Look up the correct default value for this attribute for `instance`.
        We cannot use `.default_value` directly here because the spec-class
        could be subclassed with being made explicitly a spec-class, and we
        need to detect any overrides. Values returned are always mutate-safe.

        Args:
            spec_cls: The class for which a default value should be looked up.

        Returns:
            The default value to use for the nominated class.
        """
        from spec_classes.utils.mutation import protect_via_deepcopy

        for cls in spec_cls.mro():
            if cls is self.owner:
                return self.default_value
            if self.name in cls.__dict__:
                value = cls.__dict__[self.name]
                if inspect.isfunction(value) or inspect.isdatadescriptor(value):
                    return MISSING  # Default is masked.
                return protect_via_deepcopy(value)
        return MISSING  # pragma: no cover; this should never happen... but you can't be too careful.

    @property
    def default_value(self) -> Any:
        """
        A default value for this `Attr` (evaluating `default_factory`) if
        necessary. It will always be mutate-safe, so you can use it without
        further copying.
        """
        from spec_classes.utils.mutation import protect_via_deepcopy

        if self.is_masked:
            return MISSING
        if self.default_factory:
            return self.default_factory()
        return protect_via_deepcopy(self.default)

    @property
    def has_default(self) -> bool:
        """
        Whether this attribute has a default value or default value factory.
        The default factory is *not* evaluated by this method.
        """
        return self.default is not MISSING or self.default_factory is not MISSING

    # Decorators

    def preparer(self, fpreparer: Optional[Callable[[Any], Any]]) -> Attr:
        self.prepare = fpreparer
        return self

    def item_preparer(self, fitem_preparer: Optional[Callable[[Any], Any]]) -> Attr:
        self.prepare_item = fitem_preparer
        return self

    # Dataclasses compatibility
    @property
    def _field_type(self):
        return dataclasses._FIELD  # pragma: no cover
