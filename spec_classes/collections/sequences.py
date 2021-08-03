import functools

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type

from .base import IndexedItem, ManagedCollection


class SequenceCollection(ManagedCollection):
    def _extractor(  # pylint: disable=arguments-differ
        self, value_or_index, by_index=MISSING
    ) -> IndexedItem:
        if self.collection is MISSING or value_or_index is MISSING:
            return None, MISSING

        if by_index is MISSING:
            by_index = isinstance(value_or_index, int) and not (
                check_type(value_or_index, self.item_type)
                or self.item_spec_type_is_keyed
                and check_type(value_or_index, self.item_spec_key_type)
            )

        if by_index:
            try:
                return (value_or_index, self.collection[value_or_index])
            except IndexError:
                return (value_or_index, MISSING)

        if check_type(value_or_index, self.item_type):
            return (
                self.collection.index(value_or_index)
                if value_or_index in self.collection
                else None,
                value_or_index,
            )

        if self.item_spec_type_is_keyed and check_type(
            value_or_index, self.item_spec_key_type
        ):
            for i, item in enumerate(self.collection):
                if (
                    isinstance(item, self.item_spec_type)
                    and getattr(item, self.item_spec_type.__spec_class_key__)
                    == value_or_index
                ):
                    return i, item
            return None, functools.partial(
                self.item_spec_type,
                **{self.item_spec_type.__spec_class_key__: value_or_index},
            )

        raise ValueError(
            f"Cannot lookup item from collection `{self.name}` with unrecognized type: `{repr(type(value_or_index))}`."
        )

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
        self, item=MISSING, *, attrs=None, index=MISSING, insert=False, replace=False
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
            require_existing=True,
        )

    def remove_item(
        self, value_or_index, *, by_index=MISSING
    ):  # pylint: disable=arguments-differ
        index, _ = self._extractor(value_or_index, by_index=by_index)
        if index is not None:
            del self.collection[index]
        return self
