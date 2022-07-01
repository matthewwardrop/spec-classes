from typing import Mapping, MutableMapping

from spec_classes.methods.collections import MAPPING_METHODS
from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type, type_label

from .base import CollectionAttrMutator


class MappingMutator(CollectionAttrMutator):
    """
    The mutator subclass for mutable mappings. See `CollectionAttrMutator` for
    API details.
    """

    COLLECTION_FAMILY = MutableMapping
    HELPER_METHODS = MAPPING_METHODS

    def _prepare_items(self):
        return self.add_items(self.collection)

    def _extractor(self, value_or_index, raise_if_missing=False):
        if raise_if_missing and value_or_index not in self.collection:
            raise KeyError(
                f"Key `{repr(value_or_index)}` not found in collection `{self.attr_spec.qualified_name}`."
            )
        return value_or_index, self.collection.get(value_or_index, MISSING)

    def _inserter(self, index, item):
        if not check_type(item, self.attr_spec.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.attr_spec.qualified_name}`. Expected item of type `{type_label(self.attr_spec.item_type)}`."
            )
        self.collection[index] = item

    def add_item(
        self,
        key=None,
        value=None,
        *,
        attrs=None,
        replace=True,
        require_pre_existent=False,
    ):  # pylint: disable=arguments-renamed,arguments-differ
        return self._mutate_collection(
            value_or_index=key,
            extractor=self._extractor,
            inserter=self._inserter,
            new_item=value,
            attrs=attrs,
            replace=replace,
            require_pre_existent=require_pre_existent,
        )

    def add_items(self, items: Mapping):
        if not check_type(items, Mapping):
            raise TypeError(
                f"Incoming collection for `{self.attr_spec.qualified_name}` is not a mapping."
            )
        for k, v in items.items():
            self.add_item(k, v)
        return self

    def transform_item(
        self, key, transform, *, attr_transforms=None
    ):  # pylint: disable=arguments-renamed,arguments-differ
        return self._mutate_collection(
            value_or_index=key,
            extractor=self._extractor,
            inserter=self._inserter,
            transform=transform,
            attr_transforms=attr_transforms,
            require_pre_existent=True,
        )

    def remove_item(self, key):  # pylint: disable=arguments-renamed,arguments-differ
        key, _ = self._extractor(key, raise_if_missing=True)
        del self.collection[key]
        return self
