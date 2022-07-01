import functools
from typing import Iterable, MutableSet

from spec_classes.methods.collections import SET_METHODS
from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type, type_label

from .base import CollectionAttrMutator


class SetMutator(CollectionAttrMutator):
    """
    The mutator subclass for mutable sets. See `CollectionAttrMutator` for
    API details.
    """

    COLLECTION_FAMILY = MutableSet
    HELPER_METHODS = SET_METHODS

    def _prepare_items(self):
        for value in set(self.collection):
            self.transform_item(value, self.prepare_item)

    def _extractor(self, value_or_index, raise_if_missing=False):
        if raise_if_missing and value_or_index not in self.collection:
            raise ValueError(
                f"Value `{repr(value_or_index)}` not found in collection `{self.attr_spec.qualified_name}`."
            )
        if value_or_index not in self.collection:
            return (value_or_index, MISSING)
        try:  # If set supports lookup, try that first (e.g. KeyedSet)
            return (value_or_index, self.collection[value_or_index])
        except TypeError:
            return (
                value_or_index,
                value_or_index,
            )

    def _inserter(self, index, item, replace=True):  # pylint: disable=arguments-differ
        if not check_type(item, self.attr_spec.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.attr_spec.qualified_name}`. Expected item of type `{type_label(self.attr_spec.item_type)}`."
            )
        if index and replace:
            self.collection.discard(index)
        self.collection.add(item)

    def add_item(
        self, item, *, value_or_index=MISSING, replace=True, attrs=None
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=value_or_index,
            extractor=self._extractor,
            inserter=self._inserter,
            new_item=item,
            attrs=attrs,
            replace=replace,
            require_pre_existent=value_or_index is not MISSING,
        )

    def add_items(self, items: Iterable):
        if not check_type(items, Iterable):
            raise TypeError(
                f"Incoming collection for `{self.attr_spec.qualified_name}` is not iterable."
            )
        for item in items:
            self.add_item(item)
        return self

    def transform_item(
        self, item, transform, *, attr_transforms=None
    ):  # pylint: disable=arguments-renamed,arguments-differ
        return self._mutate_collection(
            value_or_index=item,
            extractor=self._extractor,
            inserter=functools.partial(self._inserter, replace=True),
            transform=transform,
            attr_transforms=attr_transforms,
            require_pre_existent=True,
        )

    def remove_item(self, item):  # pylint: disable=arguments-renamed,arguments-differ
        key, _ = self._extractor(item, raise_if_missing=True)
        self.collection.remove(key)
        return self
