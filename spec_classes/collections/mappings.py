import functools

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

from .base import ManagedCollection


class MappingCollection(ManagedCollection):
    def _extractor(self, value_or_index):
        default = MISSING
        if self.item_spec_type_is_keyed:
            if isinstance(value_or_index, self.item_spec_type):
                value_or_index = getattr(
                    value_or_index, self.item_spec_type.__spec_class_key__
                )
            default = functools.partial(
                self.item_spec_type,
                **{self.item_spec_type.__spec_class_key__: value_or_index},
            )
        return value_or_index, self.collection.get(value_or_index, default)

    def _inserter(self, index, item):
        if not check_type(item, self.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`."
            )
        if self.item_spec_type_is_keyed:
            index = getattr(item, self.item_spec_type.__spec_class_key__)
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
        self, key=None, value=None, *, attrs=None, replace=False
    ):  # pylint: disable=arguments-differ
        if self.item_spec_type_is_keyed:
            key = self._get_spec_key(self.item_spec_type, value, attrs)
            value = value if check_type(value, self.item_spec_type) else MISSING
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
        )

    def remove_item(self, key):  # pylint: disable=arguments-differ
        if self.item_spec_type_is_keyed and isinstance(key, self.item_spec_type):
            key = getattr(key, self.item_spec_type.__spec_class_key__)
        if key in self.collection:
            del self.collection[key]
        return self
