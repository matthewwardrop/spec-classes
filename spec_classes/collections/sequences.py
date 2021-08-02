import functools

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import check_type, type_match

from .base import IndexedItem, ManagedCollection


class SequenceCollection(ManagedCollection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.item_spec_type_is_keyed:
            item_key_type = self.item_spec_type.__spec_class_annotations__[
                self.item_spec_type.__spec_class_key__
            ]
            if type_match(item_key_type, int):
                self._abort_due_to_integer_keys()

    def _abort_due_to_integer_keys(self):
        raise ValueError(
            "List containers do not support keyed spec classes with integral keys. Check "
            f"`{self.name}` and consider using a `Dict` container instead."
        )

    def _extractor(  # pylint: disable=arguments-differ
        self, value_or_index, by_index=False
    ) -> IndexedItem:
        if self.collection is MISSING or value_or_index is MISSING:
            return None, MISSING

        if by_index:
            if self.item_spec_type_is_keyed and not isinstance(value_or_index, int):
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
            return (
                value_or_index,
                self.collection[value_or_index]
                if value_or_index is not None and value_or_index < len(self.collection)
                else MISSING,
            )

        if self.item_spec_type_is_keyed:
            if isinstance(value_or_index, self.item_spec_type):
                value_or_index = getattr(
                    value_or_index, self.item_spec_type.__spec_class_key__
                )
            for i, item in enumerate(self.collection):
                if (
                    getattr(item, self.item_spec_type.__spec_class_key__)
                    == value_or_index
                ):
                    return i, item
            return None, functools.partial(
                self.item_spec_type,
                **{self.item_spec_type.__spec_class_key__: value_or_index},
            )
        return (
            self.collection.index(value_or_index)
            if value_or_index in self.collection
            else None,
            value_or_index,
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
        if self.item_spec_type_is_keyed and isinstance(item, self.item_spec_type):
            key = getattr(item, self.item_spec_type.__spec_class_key__)
            if (
                sum(
                    [
                        1
                        for item in self.collection
                        if isinstance(item, self.item_spec_type)
                        and getattr(item, self.item_spec_type.__spec_class_key__) == key
                    ]
                )
                > 1
            ):
                raise ValueError(
                    f"Adding {item} to list would result in more than instance with the same key: {repr(key)}."
                )

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
        if self.item_spec_type_is_keyed:
            if index is MISSING:
                index = self._get_spec_key(self.item_spec_type, item, attrs)
                if isinstance(index, int):
                    self._abort_due_to_integer_keys()
            if item is not MISSING and not isinstance(item, self.item_spec_type):
                _key = self._get_spec_key(self.item_spec_type, item, attrs)
                if _key is not MISSING:
                    item = (
                        self.item_spec_type(
                            **{self.item_spec_type.__spec_class_key__: item}
                        )
                        if self._extractor(_key, by_index=True)[0] is None
                        else MISSING
                    )
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
        self, value_or_index, transform, *, by_index=False, attr_transforms=None
    ):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=value_or_index,
            extractor=functools.partial(self._extractor, by_index=by_index),
            inserter=self._inserter,
            transform=transform,
            attr_transforms=attr_transforms,
        )

    def remove_item(
        self, value_or_index, *, by_index=False
    ):  # pylint: disable=arguments-differ
        index, _ = self._extractor(value_or_index, by_index=by_index)
        if index is not None:
            del self.collection[index]
        return self
