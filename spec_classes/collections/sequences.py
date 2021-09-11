import functools
from typing import Iterable, MutableSequence

from spec_classes.methods.collections import SEQUENCE_METHODS
from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type, type_label

from .base import CollectionAttrMutator, IndexedItem


class SequenceMutator(CollectionAttrMutator):
    """
    The mutator subclass for mutable sequences. See `CollectionAttrMutator` for
    API details.
    """

    COLLECTION_FAMILY = MutableSequence
    HELPER_METHODS = SEQUENCE_METHODS

    def _prepare_items(self):
        for index in range(len(self.collection)):
            self.transform_item(index, self.prepare_item, by_index=True)

    def _extractor(  # pylint: disable=arguments-differ
        self,
        value_or_index,
        raise_if_missing=False,
        by_index=MISSING,
    ) -> IndexedItem:
        if self.collection is MISSING or value_or_index is MISSING:
            return None, MISSING

        if by_index is MISSING:
            by_index = not check_type(value_or_index, self.attr_spec.item_type)

        if by_index:
            try:
                return (value_or_index, self.collection[value_or_index])
            except IndexError:
                if raise_if_missing:
                    raise IndexError(
                        f"Index `{repr(value_or_index)}` not found in collection `{self.attr_spec.qualified_name}`."
                    ) from None
                return (value_or_index, MISSING)

        try:
            value_index = self.collection.index(value_or_index)
        except ValueError:
            value_index = None

        if raise_if_missing and value_index is None:
            raise ValueError(
                f"Item `{repr(value_or_index)}` not found in collection `{self.attr_spec.qualified_name}`."
            )
        return (value_index, value_or_index)

    def _inserter(self, index, item, insert=False):  # pylint: disable=arguments-differ
        if not check_type(item, self.attr_spec.item_type):
            raise ValueError(
                f"Attempted to add an invalid item `{repr(item)}` to `{self.attr_spec.qualified_name}`. Expected item of type `{type_label(self.attr_spec.item_type)}`."
            )
        if index is None:
            self.collection.append(item)
        elif insert:
            self.collection.insert(index, item)
        else:
            self.collection[index] = item

    def add_item(
        self,
        item=MISSING,
        *,
        attrs=None,
        value_or_index=MISSING,
        by_index=True,
        insert=False,
        replace=True,
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=value_or_index,
            extractor=functools.partial(self._extractor, by_index=by_index),
            inserter=functools.partial(self._inserter, insert=insert),
            new_item=item,
            attrs=attrs,
            replace=replace,
            require_pre_existent=value_or_index is not MISSING and not insert,
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
        index, _ = self._extractor(
            value_or_index, by_index=by_index, raise_if_missing=True
        )
        if index is not None:
            del self.collection[index]
        return self
