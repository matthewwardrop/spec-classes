from spec_classes.utils.weakref_cache import WeakRefCache


class Object:
    pass


def test_weak_ref_cache():
    cache = WeakRefCache()
    a = Object()
    b = Object()
    c = Object()

    cache[a] = 1
    cache[b] = 2

    assert cache[a] == 1
    assert cache[b] == 2

    assert a in cache
    assert b in cache
    assert c not in cache
    assert len(cache) == 2
    assert list(cache) == [a, b]

    del cache[b]
    assert len(cache) == 1

    del a
    assert len(cache) == 0
