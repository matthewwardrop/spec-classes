import functools

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

from .base import IndexedItem, ManagedCollection


class SequenceCollection(ManagedCollection):
    def _extractor(  # pylint: disable=arguments-differ
        self,
        value_or_index,
        raise_if_missing=False,
        by_index=MISSING,
    ) -> IndexedItem:
        if self.collection is MISSING or value_or_index is MISSING:
            return None, MISSING

        if by_index is MISSING:
            by_index = not check_type(value_or_index, self.item_type)

        if by_index:
            try:
                return (value_or_index, self.collection[value_or_index])
            except IndexError:
                if raise_if_missing:
                    raise IndexError(
                        f"Index `{repr(value_or_index)}` not found in collection `{self.name}`."
                    ) from None
                return (value_or_index, MISSING)

        try:
            value_index = self.collection.index(value_or_index)
        except ValueError:
            value_index = None

        if raise_if_missing and value_index is None:
            raise ValueError(
                f"Item `{repr(value_or_index)}` not found in collection `{self.name}`."
            )
        return (value_index, value_or_index)

    def _inserter(self, index, item, insert=False):  # pylint: disable=arguments-differ
        if not check_type(item, self.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`."
            )
        if index is None:
            self.collection.append(item)
        elif insert:
            self.collection.insert(index, item)
        else:
            self.collection[index] = item

    def get_item(
        self,
        value_or_index=MISSING,
        *,
        attr_filters=None,
        by_index=False,
        all_matches=False,
        raise_if_missing=True,
    ):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=functools.partial(self._extractor, by_index=by_index),
            value_or_index=value_or_index,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(
        self, item=MISSING, *, attrs=None, index=MISSING, insert=False, replace=True
    ):  # pylint: disable=arguments-differ
        if (
            self.item_spec_type_is_keyed
            and item is not MISSING
            and not check_type(item, self.item_type)
            and check_type(item, self.item_spec_key_type)
        ):
            item = self.item_spec_type(item)
        return self._mutate_collection(
            value_or_index=index,
            extractor=functools.partial(self._extractor, by_index=True),
            inserter=functools.partial(self._inserter, insert=insert),
            new_item=item,
            attrs=attrs,
            replace=replace,
        )

    def add_items(self, items, preparer=None):
        preparer = preparer or (lambda x: x)
        for item in items:
            self.add_item(preparer(item))
        return self

    def transform_item(
        self, value_or_index, transform, *, by_index=MISSING, attr_transforms=None
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=value_or_index,
            extractor=functools.partial(self._extractor, by_index=by_index),
            inserter=self._inserter,
            transform=transform,
            attr_transforms=attr_transforms,
            require_pre_existent=True,
        )

    def remove_item(
        self, value_or_index, *, by_index=MISSING
    ):  # pylint: disable=arguments-differ
        index, _ = self._extractor(value_or_index, by_index=by_index)
        if index is not None:
            del self.collection[index]
        return self
