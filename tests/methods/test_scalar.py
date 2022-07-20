import inspect
import re

import pytest

from spec_classes import MISSING


class TestScalarAttribute:
    def test_with(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(inspect.Signature.from_callable(spec.with_scalar).parameters) == {
            "_new_value",
            "_inplace",
            "_if",
        }
        assert spec.with_scalar(4) is not spec
        assert spec.with_scalar(4).scalar == 4
        assert spec.with_scalar(4, _if=False).scalar == 3

        assert spec.with_scalar(4, _inplace=True) is spec
        assert spec.scalar == 4

    def test_transform(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(
            inspect.Signature.from_callable(spec.transform_scalar).parameters
        ) == {"_transform", "_inplace", "_if"}
        assert spec.transform_scalar(lambda x: x * 2) is not spec
        assert spec.transform_scalar(lambda x: x * 2).scalar == 6
        assert spec.transform_scalar(lambda x: x * 2, _if=False).scalar == 3

        assert spec.transform_scalar(lambda x: x * 2, _inplace=True) is spec
        assert spec.scalar == 6

    def test_reset(self, spec_cls):
        spec = spec_cls(scalar=3)

        assert spec.reset_scalar(_if=False).scalar == 3

        with pytest.raises(
            AttributeError, match=r"`Spec\.scalar` has not yet been assigned a value\."
        ):
            spec.reset_scalar().scalar


class TestSpecAttribute:
    def test_get(self, spec_cls):
        spec = spec_cls()

        assert "scalar" not in spec.__dict__

        with pytest.raises(
            AttributeError, match=r"`Spec\.scalar` has not yet been assigned a value\."
        ):
            spec.scalar

    def test_with(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec).parameters) == {
            "_new_value",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec" not in spec.__dict__
        assert isinstance(spec.with_spec().spec, unkeyed_spec_cls)
        assert spec.transform_spec(lambda x: x).spec is not MISSING
        with pytest.raises(
            TypeError, match=r"Attempt to set `Spec\.spec` with an invalid type"
        ):
            spec.with_spec(None)
        assert spec.with_spec({"nested_scalar": 10}).spec.nested_scalar == 10
        assert (
            spec.with_spec_list_items([{"nested_scalar": 10}])
            .spec_list_items[0]
            .nested_scalar
            == 10
        )

        # Assignments
        nested_spec = unkeyed_spec_cls()
        assert spec.with_spec(nested_spec).spec is nested_spec

        # Nested assignments
        assert spec.with_spec(nested_scalar=2) is not spec
        assert spec.with_spec(nested_scalar=2).spec.nested_scalar == 2
        assert (
            spec.with_spec(nested_scalar2="overridden").spec.nested_scalar2
            == "overridden"
        )
        assert (
            spec.with_spec(nested_scalar2="overridden").with_spec().spec.nested_scalar2
            == "original value"
        )

        assert spec.with_spec(nested_scalar=2, _inplace=True) is spec
        assert spec.spec.nested_scalar == 2

    def test_update(self, spec_cls, unkeyed_spec_cls):
        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.update_spec).parameters) == {
            "_new_value",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        assert spec.update_spec().spec is not MISSING
        assert spec.update_spec(nested_scalar=1).spec.nested_scalar == 1

        a = unkeyed_spec_cls()
        assert spec.update_spec(a).spec is a

        with pytest.raises(AttributeError):
            spec.update_spec(_if=False).spec

    def test_transform(self, spec_cls):
        spec = spec_cls().with_spec()
        assert set(inspect.Signature.from_callable(spec.transform_spec).parameters) == {
            "_transform",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        # Direct mutation
        assert spec.transform_spec(lambda x: x.with_nested_scalar(3)) is not spec
        assert (
            spec.transform_spec(lambda x: x.with_nested_scalar(3)).spec.nested_scalar
            == 3
        )

        # Nested mutations
        assert spec.transform_spec(nested_scalar=lambda x: 3) is not spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

        # Inplace operation
        assert spec.transform_spec(nested_scalar=lambda x: 3, _inplace=True) is spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

    def test_reset(self, spec_cls):
        spec = spec_cls()
        assert not hasattr(spec.with_spec().reset_spec(), "spec")

    def test_illegal_nested_update(self, spec_cls):
        base = spec_cls()
        with pytest.raises(
            TypeError,
            match=re.escape(
                "with_spec() got unexpected keyword arguments: {'invalid'}."
            ),
        ):
            base.with_spec(invalid=10)
