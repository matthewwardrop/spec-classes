import re

import pytest

from spec_classes import Alias, DeprecatedAlias, MISSING, spec_class


def test_alias():
    @spec_class
    class Item:
        x: int
        y: int = Alias("x")
        z: int = Alias("x", transform=lambda x: x**2)
        w: int = Alias("x", fallback=2)
        v: int = Alias("x", passthrough=True, fallback=2)
        u: int = Alias("u")

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
        match=r"Alias for `Item\.u` appears to be self-referential\. Please change the `attr` argument to point to a different attribute\.",
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

    assert Alias("attr").override_attr is None

    with pytest.raises(
        RuntimeError,
        match=re.escape(
            "Attempting to set the value of an `Alias` instance that is not properly associated with a class."
        ),
    ):
        Alias("attr").__set__(None, "Hi")


def test_deprecated_alias():
    @spec_class
    class Item:
        x: int
        y1: int = DeprecatedAlias("x")
        y2: int = DeprecatedAlias("x", as_of="1.0.0")
        y3: int = DeprecatedAlias("x", until="1.0.0")
        y4: int = DeprecatedAlias("x", as_of="1.0.0", until="2.0.0")
        y5: int = DeprecatedAlias(
            "x", as_of="1.0.0", until="2.0.0", warning_cls=DeprecationWarning
        )

    i = Item(x=10)

    with pytest.warns(
        DeprecationWarning,
        match=re.escape("`Item.y1` has been deprecated. Please use `Item.x` instead."),
    ):
        assert i.y1 == 10
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y2` was deprecated in version 1.0.0. Please use `Item.x` instead."
        ),
    ):
        assert i.y2 == 10
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y3` has been deprecated. Please use `Item.x` instead. This deprecated alias will be removed in version 1.0.0."
        ),
    ):
        assert i.y3 == 10
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y4` was deprecated in version 1.0.0. Please use `Item.x` instead. This deprecated alias will be removed in version 2.0.0."
        ),
    ):
        assert i.y4 == 10
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y5` was deprecated in version 1.0.0. Please use `Item.x` instead. This deprecated alias will be removed in version 2.0.0."
        ),
    ):
        assert i.y5 == 10

    # Check setting and deleting also
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y5` was deprecated in version 1.0.0. Please use `Item.x` instead. This deprecated alias will be removed in version 2.0.0."
        ),
    ):
        i.y5 = 12
    with pytest.warns(
        DeprecationWarning,
        match=re.escape(
            "`Item.y5` was deprecated in version 1.0.0. Please use `Item.x` instead. This deprecated alias will be removed in version 2.0.0."
        ),
    ):
        del i.y5
