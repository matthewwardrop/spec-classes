import copy
import functools
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Any, Callable, Dict, List, Type

from spec_classes.methods.base import AttrMethodDescriptor
from spec_classes.types import Attr, MISSING
from spec_classes.utils.mutation import mutate_value
from spec_classes.utils.type_checking import (
    check_type,
    type_instantiate,
)

MISSING_COLLECTION = object()
IndexedItem = namedtuple("IndexedItem", ("index", "item"))


class CollectionAttrMutator(metaclass=ABCMeta):
    """
    Provides a consistent API by which collections can be mutated by spec-class
    helpers.

    While the logic in these classes could be directly (and perhaps more simply)
    encoded into the collection methods, this abstraction makes it easier to
    keep collection mutations consistent with one another and with the mutation
    logic used by scalar methods.

    Class Attributes:
        COLLECTION_FAMILY: The base type of collection managed by the
            `CollectionAttrMutator` subclass (e.g. `Sequence` ).
        HELPER_METHODS: The method descriptors from the `spec_classes.methods`
            submodule that should be attached to spec-classes in order to manage
            collections of this type.

    Attributes:
        Set via constructor:
            attr_spec: The attribute specification for which the collection should
                be managed.
            instance: The instance for which the collection attribute is being
                mutated.
            collection: The collection object to be managed. If not provided
                the collection will be lifted off of the `instance` attribute
                associated with `attr_spec`.
            inplace: Whether to mutate the existing collection object, or to
                copy it before doing any mutations.

        Derived attributes:
            prepare_item: An (optional) callable that should be called on all
                items as the are added to the collection. This is derived from
                `attr_spec` and `instance`.
    """

    COLLECTION_FAMILY: Type = MISSING
    HELPER_METHODS: List[AttrMethodDescriptor] = []

    def __init__(
        self,
        attr_spec: Attr,
        instance: Any,
        *,
        collection: Any = MISSING_COLLECTION,
        inplace: bool = True,
    ):
        self.attr_spec = attr_spec
        self.prepare_item = self.attr_spec.prepare_item
        if self.prepare_item:
            self.prepare_item = functools.partial(self.prepare_item, instance)

        if collection is MISSING_COLLECTION:
            collection = getattr(instance, self.attr_spec.name, MISSING)
        if collection is not MISSING and not inplace:
            collection = copy.deepcopy(collection)
        self.collection = collection

    def _mutate_collection(
        self,
        value_or_index: Any,
        extractor: Callable,
        inserter: Callable,
        *,
        require_pre_existent: bool = False,
        new_item: Any = MISSING,
        transform: Callable = None,
        attrs: Dict[str, Any] = None,
        attr_transforms: Dict[str, Callable] = None,
        replace: bool = False,
        inplace: bool = False,
    ) -> Any:
        """
        General strategy for mutation elements within a collection, which wraps
        `cls._get_updated_value`. Extraction and insertion are handled by the
        functions passed in as `extractor` and `inserter` functions respectively.

        Extractor functions must have a signature of: `(collection, value_or_index)`,
        and output the index and value of existing items in the collection.

        Inserter functions must have a signature of: `(collection, index, new_item)`,
        and insert the given item into the collection appropriately. `index` will
        be the same `index` as that output by the extractor, and is not otherwise
        interpreted.
        """
        if self.collection is MISSING:
            self.collection = self._create_collection()
        index, old_item = extractor(
            value_or_index, raise_if_missing=require_pre_existent
        )
        new_item = mutate_value(
            old_value=old_item,
            new_value=new_item,
            constructor=self.attr_spec.item_type,
            transform=transform,
            attrs=attrs,
            attr_transforms=attr_transforms,
            replace=replace,
        )
        if self.prepare_item:
            new_item = self.prepare_item(new_item)
        inserter(index, new_item)
        return self

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.collection}>"  # pragma: no cover

    def _create_collection(self):
        return type_instantiate(self.attr_spec.type)

    def prepare(self):
        if self.collection in (MISSING, None):
            self.collection = self._create_collection()
        if not check_type(self.collection, self.attr_spec.type):
            items = self.collection
            self.collection = self._create_collection()
            self.add_items(items)
            return self
        if self.collection and self.prepare_item:
            self._prepare_items()
        return self

    @abstractmethod
    def _prepare_items(self):
        ...  # pragma: no cover

    @abstractmethod
    def _extractor(self, value_or_index, raise_if_missing=False) -> IndexedItem:
        ...  # pragma: no cover

    @abstractmethod
    def _inserter(self, index, item):
        ...  # pragma: no cover

    @abstractmethod
    def add_item(self, item):
        ...  # pragma: no cover

    @abstractmethod
    def transform_item(self, value_or_index, transform):
        ...  # pragma: no cover

    @abstractmethod
    def remove_item(self, value_or_index):
        ...  # pragma: no cover
