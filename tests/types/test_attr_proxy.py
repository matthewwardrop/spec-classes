import re

import pytest

from spec_classes import AttrProxy, MISSING, spec_class


def test_attr_proxy():
    @spec_class
    class Item:
        x: int
        y: int = AttrProxy("x")
        z: int = AttrProxy("x", transform=lambda x: x**2)
        w: int = AttrProxy("x", fallback=2)
        v: int = AttrProxy("x", passthrough=True, fallback=2)
        u: int = AttrProxy("u")

    assert Item(x=2).y == 2
    assert Item(x=2).z == 4
    assert Item().w == 2
    assert Item(x=4).w == 4
    assert Item().v == 2
    assert Item(x=4).v == 4

    item = Item()
    # Test passthrough mutation
    item.v = 1
    assert item.v == 1
    assert item.x == 1
    # Test local override
    item.w = 10
    assert item.w == 10
    assert item.x == 1

    assert Item(x=1, z=10).z == 10

    with pytest.raises(
        AttributeError, match=r"`Item\.x` has not yet been assigned a value\."
    ):
        Item(x=MISSING).x

    with pytest.raises(
        ValueError,
        match=r"AttrProxy for `Item\.u` appears to be self-referential\. Please change the `attr` argument to point to a different attribute\.",
    ):
        Item().u

    assert Item(x=1, y=10).x == 1
    assert Item(x=1, y=10).y == 10

    i = Item(x=2, y=10)
    assert i.y == 10
    del i.y
    assert i.y == 2

    with pytest.raises(
        AttributeError, match=r"`Item\.x` has not yet been assigned a value\."
    ):
        Item().y

    assert AttrProxy("attr").override_attr is None

    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "Attempting to set the value of an `AttrProxy` instance that is not properly associated with a class."
        ),
    ):
        AttrProxy("attr").__set__(None, "Hi")
