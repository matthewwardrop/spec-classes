from typing import Union

import pytest

from spec_classes.types import ValidatedType, bounded, validated


class TestValidatedType:
    def test_subclassing(self):
        class MyType(ValidatedType):
            @classmethod
            def validate(cls, obj):
                return obj == 1

        assert isinstance(1, MyType)
        assert not isinstance(2, MyType)
        assert not isinstance("hi", MyType)

        with pytest.raises(
            RuntimeError,
            match=r"`MyType` is intended to be used as a type annotation, and should not be instantiated\.",
        ):
            MyType()

    def test_validated(self):
        v = validated(lambda obj: obj == "str", name="validated_string")

        assert isinstance("str", v)
        assert not isinstance(1, v)
        assert not isinstance("hi", v)
        assert v.__name__ == "validated_string"
        assert repr(v) == "<class 'abc.validated_string'>"

    def test_bounded(self):
        b1 = bounded(int, ge=1, le=2)
        assert isinstance(1, b1)
        assert isinstance(2, b1)
        assert not isinstance(1.5, b1)
        assert not isinstance(0, b1)
        assert not isinstance(5, b1)
        assert b1.__name__ == "int∊[1,2]"

        b2 = bounded(float, gt=1, le=2)
        assert not isinstance(1.0, b2)
        assert isinstance(2.0, b2)
        assert isinstance(1.5, b2)
        assert not isinstance(2, b2)
        assert not isinstance(0.0, b2)
        assert not isinstance(5, b2)
        assert b2.__name__ == "float∊(1,2]"

        b3 = bounded(Union[float, int], gt=1, lt=3)
        assert not isinstance(1.0, b3)
        assert not isinstance(3.0, b3)
        assert isinstance(2, b3)
        assert isinstance(1.5, b3)
        assert not isinstance(0, b3)
        assert not isinstance(5, b3)
        assert b3.__name__ == "Union[float, int]∊(1,3)"

        with pytest.raises(
            ValueError, match=r"Can only specify at most one of `gt` or `ge`\."
        ):
            bounded(int, gt=1, ge=1)
        with pytest.raises(
            ValueError, match=r"Can only specify at most one of `lt` or `le`\."
        ):
            bounded(int, lt=1, le=1)
