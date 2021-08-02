import functools

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

from .base import ManagedCollection


class SetCollection(ManagedCollection):
    def _extractor(self, value_or_index):
        return (
            value_or_index,
            value_or_index if value_or_index in self.collection else MISSING,
        )

    def _inserter(self, index, item, replace=False):  # pylint: disable=arguments-differ
        if not check_type(item, self.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`."
            )
        if replace:
            self.collection.discard(index)
        self.collection.add(item)

    def get_item(
        self,
        item=MISSING,
        *,
        all_matches=False,
        raise_if_missing=True,
        attr_filters=None,
    ):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=self._extractor,
            value_or_index=item,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(
        self, item, *, replace=False, attrs=None
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=item,
            extractor=self._extractor,
            inserter=self._inserter,
            new_item=item,
            attrs=attrs,
            replace=replace,
        )

    def add_items(self, items, preparer=None):
        preparer = preparer or (lambda item: item)
        for item in items:
            self.add_item(preparer(item))
        return self

    def transform_item(
        self, item, transform, *, attr_transforms=None
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=item,
            extractor=self._extractor,
            inserter=functools.partial(self._inserter, replace=True),
            transform=transform,
            attr_transforms=attr_transforms,
        )

    def remove_item(self, item):  # pylint: disable=arguments-differ
        if item in self.collection:
            self.collection.discard(item)
        return self
