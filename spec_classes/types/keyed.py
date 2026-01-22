import sys
from collections.abc import MutableSequence, MutableSet, Sequence
from typing import Any, Callable, Generic, Iterable, Optional, Tuple, Type, TypeVar

from spec_classes.errors import BaseTypeError
from spec_classes.utils.type_checking import check_type, type_label

ItemType = TypeVar("ItemType")
KeyType = TypeVar("KeyType")


class KeyedBase(Generic[ItemType, KeyType]):
    def __init__(self, key: Optional[Callable[[ItemType], Any]] = None):
        self._key = key
        self._type = self.__class__
        self._type_item, self._type_key = (
            self._type.__args__ if hasattr(self._type, "__args__") else (Any, Any)
        )

    def key(self, item: ItemType) -> KeyType:
        """
        Look up the key for a nominated item.
        """
        if self._key:
            return self._key(item)
        return self.__get_item_key(item)

    # Helpers

    def _is_valid_key(self, key: Any) -> bool:
        return check_type(key, self._type_key)

    def _is_valid_item(self, item: Any) -> bool:
        return check_type(item, self._type_item)

    def _validate_item(self, item: ItemType) -> Tuple[ItemType, KeyType]:
        key = self.key(item)
        if hasattr(self._type, "__args__"):  # Skip type checking if untyped
            if not self._is_valid_item(item):
                raise TypeError(
                    f"Invalid item type. Got: `{repr(item)}`; Expected instance of: `{type_label(self._type_item)}`."
                )
            if not self._is_valid_key(key):
                raise TypeError(
                    f"Invalid key type. Got: `{repr(key)}`; Expected instance of: `{type_label(self._type_key)}`."
                )
        return item, key

    def __get_item_key(self, item):
        """
        Default implementation of `KeyedList.key`.
        """
        if getattr(item, "__spec_class__", None):
            key = item.__spec_class__.key
            if key:
                return getattr(item, key)
        try:
            hash(item)
            return item
        except TypeError:
            raise TypeError(
                f"Key extractor for `{type_label(item.__class__)}` instances must "
                "be provided if not using keyed spec-classes and/or instances are "
                "not hashable."
            ) from None

    # Hooks

    @property
    def __orig_class__(self):
        """
        This is set after construction by the `Generic` constructor wrapper if
        there were any type vars set.
        """
        return self._type  # pragma: no cover

    @__orig_class__.setter
    def __orig_class__(self, type_):
        self._type = type_
        self._type_item, self._type_key = (
            self._type.__args__ if hasattr(self._type, "__args__") else (Any, Any)
        )
        if getattr(self._type, "__args__", None):
            try:
                for item in self:
                    self._validate_item(item)
            except Exception as e:
                if sys.version_info >= (3, 11):
                    # Python 3.11+ suppresses errors associated with setting
                    # __orig_class__. We bypass this because we want to enforce
                    # typing at runtime.
                    raise BaseTypeError(*e.args) from e
                raise

    @classmethod
    def __spec_class_check_type__(cls, instance: Any, type_: Type) -> bool:
        """
        Returns `True` if this instance is a valid instance of `type_` and this
        class.
        """
        if not isinstance(instance, cls):
            return False

        if hasattr(type_, "__args__"):
            item_type, key_type = type_.__args__

            for (
                key,
                value,
            ) in instance._dict.items():  # pylint: disable=protected-access
                if not check_type(key, key_type):
                    return False
                if not check_type(value, item_type):
                    return False
        return True


# ruff: noqa: PLW1641
class KeyedList(KeyedBase[ItemType, KeyType], MutableSequence):  # pylint: disable=too-many-ancestors
    """
    A list-like object that can also look up items by key. The computational
    complexity for list-like operations is the same as the base `list` class,
    with additional dict-like operations with complexity as follows:
    - O(1) lookups by key
    - O(n) replacement by key
    - O(n) deletes by key

    Under the hood this is implemented by keeping both a list and dictionary
    representation of the objects stored in this container. As such, references
    to objects are stored twice, but not copied (and so memory overhead should
    be minimal).

    Args:
        sequence: An optional sequence to populate the new `KeyedList` instance.
        key: An optional callable that extracts the key to use for each item. By
            default, the key is taken to be the spec-class key (if the items are
            spec-classes) or the hash of the object (if hashable). If both fail,
            then an `TypeError` exception will be thrown.
    """

    def __init__(
        self,
        sequence: Optional[Iterable[ItemType]] = None,
        key: Optional[Callable[[ItemType], Any]] = None,
    ):
        super().__init__(key=key)
        self._list = []
        self._dict = {}

        for item in sequence or []:
            self.insert(len(self._list), item)

    # Implement MutableSequence

    def __getitem__(self, index_or_key):
        if isinstance(index_or_key, slice):
            return type(self)(self._list[index_or_key], self.key)
        if isinstance(index_or_key, int):
            return self._list[index_or_key]
        return self._dict[index_or_key]

    def __setitem__(self, index_or_key, value):
        if isinstance(index_or_key, slice):
            raise RuntimeError("Cannot assign multiple values at a time.")
        if isinstance(index_or_key, int):
            self.__delitem__(index_or_key)
            self.insert(index_or_key, value)
            return

        index = self.index_for_key(index_or_key)
        self.__setitem__(index, value)

    def __delitem__(self, index_or_key):
        if isinstance(index_or_key, slice):
            raise RuntimeError("Cannot delete multiple values at a time.")
        if isinstance(index_or_key, int):
            value = self._list.pop(index_or_key)
            del self._dict[self.key(value)]
            return

        index = self.index_for_key(index_or_key)
        self.__delitem__(index)

    def __len__(self):
        return len(self._list)

    def insert(self, index, value):
        item, key = self._validate_item(value)
        if key in self._dict:
            raise ValueError(
                f"Item with key `{repr(key)}` already in `{type_label(self._type)}`."
            )
        self._list.insert(index, item)
        self._dict[key] = item

    def __contains__(self, value):
        if self._is_valid_key(value):
            try:
                if value in self._dict:
                    return True
            except TypeError:
                pass
        if self._is_valid_item(value):
            key = self.key(value)
            if self._is_valid_key(key):
                return key in self._dict and self._dict[key] == value
        return False

    # Implement dict-like lookups by key

    def keys(self):
        return self._dict.keys()

    def items(self):
        return self._dict.items()

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def index_for_key(self, key):
        if key in self._dict:
            for i, el in enumerate(self._list):
                if self.key(el) == key:
                    return i
        raise KeyError(key)

    # Other magic methods

    def __eq__(self, other):
        if isinstance(other, KeyedList):
            other = other._list
        if isinstance(other, list):
            return self._list == other
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, Sequence):
            return type(self)([*self._list, *other])
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, Sequence):
            return type(self)([*other, *self._list])
        return NotImplemented

    def __repr__(self):
        return f"{type_label(self._type)}({repr(self._list)})"


# ruff: noqa: PLW1641
class KeyedSet(MutableSet, KeyedBase[ItemType, KeyType]):  # pylint: disable=too-many-ancestors
    """
    A set-like object that can also look up items by key. The computational
    complexity for set-like operations is the same as the base `set` class,
    with additional dict-like operations with complexity as follows:
    - O(1) lookups by key
    - O(1) deletes by key

    Under the hood this is implemented by keeping stored items in a dictionary
    mapping keys to items.

    Args:
        sequence: An optional sequence to populate the new `KeyedSet` instance.
        key: An optional callable that extracts the key to use for each item. By
            default, the key is taken to be the spec-class key (if the items are
            spec-classes) or the hash of the object (if hashable). If both fail,
            then an `TypeError` exception will be thrown.
        enforce_item_equivalence: If keys collide, whether to explicitly check
            that the new item is equivalent to the old item (True) or to blindly
            accept the new item as equivalent (False, the default). If `True`, a
            `ValueError` will be raised whenever items are not equivalent.

    WARNING: It is not recommended to use this class when the item-type and the
    key-type are the same without careful thought, since then discard operations
    are potentially ambiguous. This is because when `.discard(<item>)` is called
    we first try to treat the item as a key, and if that fails we then try to
    extract the key from the item and try again. If the item and key types are
    the same, it is possible to have an unwanted collision.
    """

    def __init__(
        self,
        sequence: Optional[Iterable[ItemType]] = None,
        key: Optional[Callable[[ItemType], KeyType]] = None,
        enforce_item_equivalence: bool = False,
    ):
        super().__init__(key=key)
        self._dict = {}
        self.enforce_item_equivalence = enforce_item_equivalence

        if sequence is not None:
            for item in sequence:
                self.add(item)

    # MutableSet implementation

    def __contains__(self, item_or_key):
        # Check whether item_or_key exists as a key
        try:
            if item_or_key in self._dict:
                return True
        except TypeError:
            pass
        # Check whether item_or_key exists as a value
        try:
            key = self.key(item_or_key)
            if key in self._dict:
                return (
                    not self.enforce_item_equivalence
                    or self.enforce_item_equivalence
                    and item_or_key == self._dict[key]
                )
        except TypeError:
            pass
        return False

    def __iter__(self):
        return iter(self._dict.values())

    def __len__(self):
        return len(self._dict)

    def add(self, value):
        value, key = self._validate_item(value)
        if (
            self.enforce_item_equivalence
            and key in self._dict
            and self._dict[key] != value
        ):
            raise ValueError(
                f"Item for `{repr(key)}` already exists, and is not equal to the incoming item."
            )
        self._dict[key] = value

    def discard(self, value):
        # Attempt to discard value as a key
        try:
            if value in self._dict:
                del self._dict[value]
                return
        except TypeError:
            pass
        # Attempt to discard value as a value
        try:
            key = self.key(value)
            if key in self._dict and (
                not self.enforce_item_equivalence
                or self.enforce_item_equivalence
                and value == self._dict[key]
            ):
                del self._dict[key]
        except TypeError:
            pass

    # Magic methods

    def __eq__(self, other):
        # NOTE: We do not implement equality against other object types (like
        # set) because `KeyedSet` instances can store values that are
        # non-hashable (only their keys need to be hashable).
        if isinstance(other, KeyedSet):
            return self._dict == other._dict
        if isinstance(other, set):
            try:
                return set(self._dict.values()) == other
            except TypeError:
                return False
        return NotImplemented

    def __repr__(self):
        return f"{type_label(self._type)}({{{', '.join(repr(value) for value in self._dict.values())}}})"

    # Dict-like features

    def keys(self):
        return self._dict.keys()

    def items(self):
        return self._dict.items()

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def __getitem__(self, key):
        if key in self._dict:
            return self._dict[key]
        item_key = self.key(key)
        if item_key in self._dict:
            return self._dict[item_key]
        raise KeyError(key)
