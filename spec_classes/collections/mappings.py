from typing import Mapping, MutableMapping

from spec_classes.methods.collections import MAPPING_METHODS
from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

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
                f"Key `{repr(value_or_index)}` not in `{self.attr_spec.qualified_name}`."
            )
        return value_or_index, self.collection.get(value_or_index, MISSING)

    def _inserter(self, index, item):
        if not check_type(item, self.attr_spec.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.attr_spec.qualified_name}`. Expected item of type `{self.attr_spec.item_type}`."
            )
        self.collection[index] = item

    def get_item(
        self,
        key=MISSING,
        *,
        all_matches=False,
        raise_if_missing=True,
        attr_filters=None,
    ):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=lambda value_or_index: (
                value_or_index,
                self.collection.get(value_or_index, MISSING),
            ),
            value_or_index=key,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(
        self, key=None, value=None, *, attrs=None, replace=True
    ):  # pylint: disable=arguments-differ
        if (
            self.attr_spec.item_spec_key_type
            and value is not MISSING
            and not check_type(value, self.attr_spec.item_type)
            and check_type(value, self.attr_spec.item_spec_key_type)
        ):
            value = self.attr_spec.item_spec_type(value)
        return self._mutate_collection(
            value_or_index=key,
            extractor=self._extractor,
            inserter=self._inserter,
            new_item=value,
            attrs=attrs,
            replace=replace,
        )

    def add_items(self, items: Mapping):
        if not check_type(items, Mapping):
            ValueError(
                f"Incoming collection for `{self.attr_spec.qualified_name}` is not a mapping."
            )
        for k, v in items.items():
            self.add_item(k, v)
        return self

    def transform_item(
        self, key, transform, attr_transforms
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=key,
            extractor=self._extractor,
            inserter=self._inserter,
            transform=transform,
            attr_transforms=attr_transforms,
            require_pre_existent=True,
        )

    def remove_item(self, key):  # pylint: disable=arguments-differ
        if self.attr_spec.item_spec_key_type and isinstance(
            key, self.attr_spec.item_spec_type
        ):
            key = getattr(key, self.attr_spec.item_spec_type.__spec_class__.key)
        if key in self.collection:
            del self.collection[key]
        return self
