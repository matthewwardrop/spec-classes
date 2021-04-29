from __future__ import annotations

import copy
import functools
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Any, Callable, Dict, Type, Union

from spec_classes.special_types import MISSING

from .mutation import mutate_value
from .type_checking import check_type, get_collection_item_type, get_spec_class_for_type, type_match


IndexedItem = namedtuple('IndexedItem', ('index', 'item'))


class ManagedCollection(metaclass=ABCMeta):

    def __init__(self, collection_type: Union[Type, Callable], collection: Any = MISSING, name=None, inplace=True):
        self.collection_type = collection_type
        self.collection = collection if inplace else copy.deepcopy(collection)
        self.name = name or "collection"

        self.item_type = get_collection_item_type(collection_type)
        self.item_spec_type = get_spec_class_for_type(self.item_type)
        self.item_spec_type_is_keyed = self.item_spec_type and self.item_spec_type.__spec_class_key__ is not None

    def _mutate_collection(self,
            value_or_index: Any, extractor: Callable, inserter: Callable, *,
            new_item: Any = MISSING, transform: Callable = None,
            attrs: Dict[str, Any] = None, attr_transforms: Dict[str, Callable] = None, replace: bool = False, inplace: bool = False
    ) -> Any:
        """
        General strategy for mutation elements within a collection, which wraps
        `cls._get_updated_value`. Extraction and insertion are handled by the
        functions passed in as `extractor` and `inserter` functions respectively.

        Extractor functions must have a signature of: `(collection, value_or_index)`,
        and output the index and value of existing items in the collection.

        Inserter functions must have a signature of: `(collection, index, new_item)`,
        and insert the given item into the collection appropriately. `index` will
        be the same `index` as that output by the extractor, and is not otherwise
        interpreted.
        """
        if self.collection is MISSING:
            self.collection = self._create_collection()
        index, old_item = extractor(value_or_index)
        new_item = mutate_value(
            old_value=old_item, new_value=new_item, constructor=self.item_type,
            transform=transform, attrs=attrs, attr_transforms=attr_transforms,
            replace=replace
        )
        inserter(index, new_item)
        return self

    def _get_items_from_collection(
            self, extractor, *,
            value_or_index=MISSING, attr_filters=MISSING, all_matches=False, raise_if_missing=True
    ):
        assert not (value_or_index and attr_filters), "You may only specific a key *or* attribute filters, not both."
        assert not (value_or_index and all_matches), "You may only use `_all=True` with attribute filters, not with keys/indices."

        # Attempt to look up by key/index
        if value_or_index:
            if self.collection:
                index, value = extractor(value_or_index)
                item = MISSING if (self.collection is MISSING or index is None or value is MISSING) else value
            else:
                item = MISSING
            if raise_if_missing and item is MISSING:
                raise AttributeError(f"No item by key/index `{repr(value_or_index)}` found in `{self.name}`.")
            return item

        # Find all items satisfying nominated filters
        if self.collection is MISSING:
            self.collection = []
        filtered = [
            item
            for item in (self.collection.values() if isinstance(self.collection, dict) else self.collection)
            if all(
                getattr(item, field) == value
                for field, value in attr_filters.items()
            )
        ]

        if all_matches:
            return filtered
        if not filtered and raise_if_missing:
            raise AttributeError(f"No items with nominated attribute filters found in `{self.name}`.")
        if not filtered:
            return MISSING
        return filtered[0]

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.collection}>"  # pragma: no cover

    @classmethod
    def _get_spec_key(cls, spec_cls, item, attrs=None):
        """
        Get the key associated with a spec class isntance or from attrs.
        """
        assert hasattr(spec_cls, '__spec_class_key__'), f"`{spec_cls}` is not a keyed spec class instance."
        if isinstance(item, spec_cls):
            return getattr(item, spec_cls.__spec_class_key__, MISSING)
        if check_type(item, spec_cls.__spec_class_annotations__[spec_cls.__spec_class_key__]):
            return item
        return (attrs or {}).get(spec_cls.__spec_class_key__, MISSING)

    @abstractmethod
    def _create_collection(self):
        ...  # pragma: no cover

    @abstractmethod
    def _extractor(self, value_or_index) -> IndexedItem:
        ...  # pragma: no cover

    @abstractmethod
    def _inserter(self, index, item):
        ...  # pragma: no cover

    @abstractmethod
    def get_item(self, value_or_index):
        ...  # pragma: no cover

    @abstractmethod
    def add_item(self, item):
        ...  # pragma: no cover

    @abstractmethod
    def transform_item(self, value_or_index, transform):
        ...  # pragma: no cover

    @abstractmethod
    def remove_item(self, value_or_index):
        ...  # pragma: no cover


class ListCollection(ManagedCollection):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.item_spec_type_is_keyed:
            item_key_type = self.item_spec_type.__spec_class_annotations__[self.item_spec_type.__spec_class_key__]
            if type_match(item_key_type, int):
                self._abort_due_to_integer_keys()

    def _create_collection(self):
        return []

    def _abort_due_to_integer_keys(self):
        raise ValueError(
            "List containers do not support keyed spec classes with integral keys. Check "
            f"`{self.name}` and consider using a `Dict` container instead."
        )

    def _extractor(self, value_or_index, by_index=False) -> IndexedItem:  # pylint: disable=arguments-differ
        if self.collection is MISSING or value_or_index is MISSING:
            return None, MISSING

        if by_index:
            if self.item_spec_type_is_keyed and not isinstance(value_or_index, int):
                for i, item in enumerate(self.collection):
                    if isinstance(item, self.item_spec_type) and getattr(item, self.item_spec_type.__spec_class_key__) == value_or_index:
                        return i, item
                return None, functools.partial(self.item_spec_type, **{self.item_spec_type.__spec_class_key__: value_or_index})
            return value_or_index, self.collection[value_or_index] if value_or_index is not None and value_or_index < len(self.collection) else MISSING

        if self.item_spec_type_is_keyed:
            if isinstance(value_or_index, self.item_spec_type):
                value_or_index = getattr(value_or_index, self.item_spec_type.__spec_class_key__)
            for i, item in enumerate(self.collection):
                if getattr(item, self.item_spec_type.__spec_class_key__) == value_or_index:
                    return i, item
            return None, functools.partial(self.item_spec_type, **{self.item_spec_type.__spec_class_key__: value_or_index})
        return self.collection.index(value_or_index) if value_or_index in self.collection else None, value_or_index

    def _inserter(self, index, item, insert=False):  # pylint: disable=arguments-differ
        if not check_type(item, self.item_type):
            raise ValueError(f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`.")
        if index is None:
            self.collection.append(item)
        elif insert:
            self.collection.insert(index, item)
        else:
            self.collection[index] = item
        if self.item_spec_type_is_keyed and isinstance(item, self.item_spec_type):
            key = getattr(item, self.item_spec_type.__spec_class_key__)
            if sum([1 for item in self.collection if isinstance(item, self.item_spec_type) and getattr(item, self.item_spec_type.__spec_class_key__) == key]) > 1:
                raise ValueError(f"Adding {item} to list would result in more than instance with the same key: {repr(key)}.")

    def get_item(self, value_or_index=MISSING, *, attr_filters=None, by_index=False, all_matches=False, raise_if_missing=True):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=functools.partial(self._extractor, by_index=by_index),
            value_or_index=value_or_index,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(self, item=MISSING, *, attrs=None, index=MISSING, insert=False, replace=False):  # pylint: disable=arguments-differ
        if self.item_spec_type_is_keyed:
            if index is MISSING:
                index = self._get_spec_key(self.item_spec_type, item, attrs)
                if isinstance(index, int):
                    self._abort_due_to_integer_keys()
            if item is not MISSING and not isinstance(item, self.item_spec_type):
                _key = self._get_spec_key(self.item_spec_type, item, attrs)
                if _key is not MISSING:
                    item = (
                        self.item_spec_type(**{self.item_spec_type.__spec_class_key__: item})
                        if self._extractor(_key, by_index=True)[0] is None else
                        MISSING
                    )
        return self._mutate_collection(
            value_or_index=index, extractor=functools.partial(self._extractor, by_index=True), inserter=functools.partial(self._inserter, insert=insert),
            new_item=item, attrs=attrs, replace=replace
        )

    def add_items(self, items, preparer=None):
        preparer = preparer or (lambda x: x)
        for item in items:
            self.add_item(preparer(item))
        return self

    def transform_item(self, value_or_index, transform, *, by_index=False, attr_transforms=None):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=value_or_index, extractor=functools.partial(self._extractor, by_index=by_index), inserter=self._inserter,
            transform=transform, attr_transforms=attr_transforms
        )

    def remove_item(self, value_or_index, *, by_index=False):  # pylint: disable=arguments-differ
        index, _ = self._extractor(value_or_index, by_index=by_index)
        if index is not None:
            del self.collection[index]
        return self


class DictCollection(ManagedCollection):

    def _create_collection(self):
        return {}

    def _extractor(self, value_or_index):
        default = MISSING
        if self.item_spec_type_is_keyed:
            if isinstance(value_or_index, self.item_spec_type):
                value_or_index = getattr(value_or_index, self.item_spec_type.__spec_class_key__)
            default = functools.partial(self.item_spec_type, **{self.item_spec_type.__spec_class_key__: value_or_index})
        return value_or_index, self.collection.get(value_or_index, default)

    def _inserter(self, index, item):
        if not check_type(item, self.item_type):
            raise ValueError(f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`.")
        if self.item_spec_type_is_keyed:
            index = getattr(item, self.item_spec_type.__spec_class_key__)
        self.collection[index] = item

    def get_item(self, key=MISSING, *, all_matches=False, raise_if_missing=True, attr_filters=None):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=lambda value_or_index: (value_or_index, self.collection.get(value_or_index, MISSING)),
            value_or_index=key,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(self, key=None, value=None, *, attrs=None, replace=False):  # pylint: disable=arguments-differ
        if self.item_spec_type_is_keyed:
            key = self._get_spec_key(self.item_spec_type, value, attrs)
            value = value if check_type(value, self.item_spec_type) else MISSING
        return self._mutate_collection(
            value_or_index=key, extractor=self._extractor, inserter=self._inserter,
            new_item=value, attrs=attrs, replace=replace
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

    def transform_item(self, key, transform, attr_transforms):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=key, extractor=self._extractor, inserter=self._inserter,
            transform=transform, attr_transforms=attr_transforms
        )

    def remove_item(self, key):  # pylint: disable=arguments-differ
        if self.item_spec_type_is_keyed and isinstance(key, self.item_spec_type):
            key = getattr(key, self.item_spec_type.__spec_class_key__)
        if key in self.collection:
            del self.collection[key]
        return self


class SetCollection(ManagedCollection):

    def _create_collection(self):
        return set()

    def _extractor(self, value_or_index):
        return value_or_index, value_or_index if value_or_index in self.collection else MISSING

    def _inserter(self, index, item, replace=False):  # pylint: disable=arguments-differ
        if not check_type(item, self.item_type):
            raise ValueError(f"Attempted to add an invalid item `{repr(item)}` to `{self.name}`. Expected item of type `{self.item_type}`.")
        if replace:
            self.collection.discard(index)
        self.collection.add(item)

    def get_item(self, item=MISSING, *, all_matches=False, raise_if_missing=True, attr_filters=None):  # pylint: disable=arguments-differ
        return self._get_items_from_collection(
            extractor=self._extractor,
            value_or_index=item,
            attr_filters=attr_filters,
            all_matches=all_matches,
            raise_if_missing=raise_if_missing,
        )

    def add_item(self, item, *, replace=False, attrs=None):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=item, extractor=self._extractor, inserter=self._inserter,
            new_item=item, attrs=attrs, replace=replace
        )

    def add_items(self, items, preparer=None):
        preparer = preparer or (lambda item: item)
        for item in items:
            self.add_item(preparer(item))
        return self

    def transform_item(self, item, transform, *, attr_transforms=None):  # pylint: disable=arguments-differ
        return self._mutate_collection(
            value_or_index=item, extractor=self._extractor, inserter=functools.partial(self._inserter, replace=True),
            transform=transform, attr_transforms=attr_transforms
        )

    def remove_item(self, item):  # pylint: disable=arguments-differ
        if item in self.collection:
            self.collection.discard(item)
        return self
