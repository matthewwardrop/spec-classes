import copy
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from typing import Any, Callable, Dict, Optional, Type, Union

from spec_classes.types.missing import MISSING
from spec_classes.utils.mutation import mutate_value
from spec_classes.utils.type_checking import (
    check_type,
    get_collection_item_type,
    get_spec_class_for_type,
)

IndexedItem = namedtuple("IndexedItem", ("index", "item"))


class ManagedCollection(metaclass=ABCMeta):

    HELPER_METHODS = []

    def __init__(
        self,
        collection_type: Union[Type, Callable],
        collection: Any = MISSING,
        item_preparer: Optional[Callable[[Any], Any]] = MISSING,
        name=None,
        inplace=True,
    ):
        self.collection_type = collection_type
        self.collection = collection if inplace else copy.deepcopy(collection)
        self.name = name or "collection"

        self.item_preparer = item_preparer
        self.item_type = get_collection_item_type(collection_type)
        self.item_spec_type = get_spec_class_for_type(self.item_type)
        self.item_spec_type_is_keyed = (
            self.item_spec_type and self.item_spec_type.__spec_class__.key is not None
        )
        self.item_spec_key_type = (
            self.item_spec_type.__spec_class__.annotations[
                self.item_spec_type.__spec_class__.key
            ]
            if self.item_spec_type_is_keyed
            else None
        )

    def _mutate_collection(
        self,
        value_or_index: Any,
        extractor: Callable,
        inserter: Callable,
        *,
        require_pre_existent: bool = False,
        new_item: Any = MISSING,
        transform: Callable = None,
        attrs: Dict[str, Any] = None,
        attr_transforms: Dict[str, Callable] = None,
        replace: bool = False,
        inplace: bool = False,
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
        index, old_item = extractor(
            value_or_index, raise_if_missing=require_pre_existent
        )
        new_item = mutate_value(
            old_value=old_item,
            new_value=new_item,
            constructor=self.item_type,
            transform=transform,
            attrs=attrs,
            attr_transforms=attr_transforms,
            replace=replace,
        )
        if self.item_preparer:
            new_item = self.item_preparer(new_item)
        inserter(index, new_item)
        return self

    def _get_items_from_collection(
        self,
        extractor,
        *,
        value_or_index=MISSING,
        attr_filters=MISSING,
        all_matches=False,
        raise_if_missing=True,
    ):
        assert not (
            value_or_index and attr_filters
        ), "You may only specific a key *or* attribute filters, not both."
        assert not (
            value_or_index and all_matches
        ), "You may only use `_all=True` with attribute filters, not with keys/indices."

        # Attempt to look up by key/index
        if value_or_index:
            if self.collection:
                index, value = extractor(value_or_index)
                item = (
                    MISSING
                    if (self.collection is MISSING or index is None or value is MISSING)
                    else value
                )
            else:
                item = MISSING
            if raise_if_missing and item is MISSING:
                raise AttributeError(
                    f"No item by key/index `{repr(value_or_index)}` found in `{self.name}`."
                )
            return item

        # Find all items satisfying nominated filters
        if self.collection is MISSING:
            self.collection = []
        filtered = [
            item
            for item in (
                self.collection.values()
                if isinstance(self.collection, dict)
                else self.collection
            )
            if all(
                getattr(item, field) == value for field, value in attr_filters.items()
            )
        ]

        if all_matches:
            return filtered
        if not filtered and raise_if_missing:
            raise AttributeError(
                f"No items with nominated attribute filters found in `{self.name}`."
            )
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
        assert (
            spec_cls.__spec_class__.key
        ), f"`{spec_cls}` is not a keyed spec class instance."
        if isinstance(item, spec_cls):
            return getattr(item, spec_cls.__spec_class__.key, MISSING)
        if check_type(
            item, spec_cls.__spec_class__.annotations[spec_cls.__spec_class__.key]
        ):
            return item
        return (attrs or {}).get(spec_cls.__spec_class__.key, MISSING)

    def _create_collection(self):
        if hasattr(self.collection_type, "__origin__"):
            return self.collection_type.__origin__()
        return self.collection_type()

    def prepare(self):
        if self.collection in (MISSING, None):
            self.collection = self._create_collection()
        if not check_type(self.collection, self.collection_type):
            items = self.collection
            self.collection = self._create_collection()
            self.add_items(items)
            return self
        if self.collection and self.item_preparer:
            self._prepare_items()
        return self

    @abstractmethod
    def _prepare_items(self):
        ...

    @abstractmethod
    def _extractor(self, value_or_index, raise_if_missing=False) -> IndexedItem:
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
