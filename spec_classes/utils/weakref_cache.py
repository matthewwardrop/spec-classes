import weakref
from collections.abc import MutableMapping
from typing import Any


class WeakRef:
    def __init__(self, obj: Any):
        self._ref = weakref.ref(obj)

    def __hash__(self):
        return id(self._ref)

    def __eq__(self, other):
        return self._ref is other._ref


class WeakRefCache(MutableMapping):
    def __init__(self):
        self.index = weakref.WeakValueDictionary()
        self.values = weakref.WeakKeyDictionary()

    def __getitem__(self, obj):
        return self.values[WeakRef(obj)]

    def __setitem__(self, obj, value):
        ref = WeakRef(obj)
        self.index[ref] = obj
        self.values[ref] = value

    def __delitem__(self, obj):
        ref = WeakRef(obj)
        del self.values[ref]
        del self.index[ref]

    def __iter__(self):
        return self.index.values()

    def __len__(self):
        return len(self.index)
