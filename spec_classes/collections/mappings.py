from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

from .base import ManagedCollection


class MappingCollection(ManagedCollection):
    def _extractor(self, value_or_index, raise_if_missing=False):
        if raise_if_missing and value_or_index not in self.collection:
            raise KeyError(f"Key `{repr(value_or_index)}` not in `{self.name}`.")
        return value_or_index, self.collection.get(value_or_index, MISSING)

    def _inserter(self, index, item):
        if not check_type(item, self.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`."
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
            self.item_spec_type_is_keyed
            and value is not MISSING
            and not check_type(value, self.item_type)
            and check_type(value, self.item_spec_key_type)
        ):
            value = self.item_spec_type(value)
        return self._mutate_collection(
            value_or_index=key,
            extractor=self._extractor,
            inserter=self._inserter,
            new_item=value,
            attrs=attrs,
            replace=replace,
        )

    def add_items(self, items, preparer=None):
        preparer = preparer or (lambda k, v: (k, v))
        if isinstance(items, dict):
            for k, v in items.items():
                self.add_item(*preparer(k, v))
        elif self.item_spec_type_is_keyed:
            for item in items:
                self.add_item(value=preparer(None, item)[1])
        else:
            raise TypeError("Unrecognised items type.")
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
        if self.item_spec_type_is_keyed and isinstance(key, self.item_spec_type):
            key = getattr(key, self.item_spec_type.__spec_class_key__)
        if key in self.collection:
            del self.collection[key]
        return self
