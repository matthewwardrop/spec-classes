import re

import pytest

from spec_classes import spec_class, spec_property
from spec_classes.errors import NestedAttributeError


class TestSpecProperty:
    @pytest.fixture
    def spec_cls(self):
        @spec_class
        class MySpecClass:

            overridable_int: int
            static_str: str
            cached_time: float
            bad_typecheck: int

            @spec_property
            def overridable_int(self):
                return 10

            @spec_property(overridable=False)
            def static_str(self):
                return "string"

            @spec_property(cache=True)
            def cached_time(self):
                import time

                return time.time()

            @spec_property
            def bad_typecheck(self):
                return "string"

            no_methods = spec_property(None, overridable=False)

            @spec_property
            def method_overrides(self):
                return

            @method_overrides.getter
            def method_overrides(self):
                raise RuntimeError("In `method_overrides` getter.")

            @method_overrides.setter
            def method_overrides(self, method_overrides):
                raise RuntimeError("In `method_overrides` setter.")

            @method_overrides.deleter
            def method_overrides(self):
                raise RuntimeError("In `method_overrides` deleter.")

            @spec_property(cache=True, invalidated_by=["overridable_int"])
            def invalidated_obj(self):
                return object()

            @spec_property(cache=True, invalidated_by="*")
            def always_invalidated_obj(self):
                return object()

            @spec_property(allow_attribute_error=False)
            def suppresses_attribute_error(self):
                raise AttributeError("I will be swallowed!")

            @spec_property
            def raises_attribute_error(self):
                raise AttributeError("I will not be swallowed!")

            def __getattr__(self, name):
                if name == "raises_attribute_error":
                    raise AttributeError(
                        "I swallowed the attribute error raised by `raises_attribute_error`."
                    )
                return object.__getattribute__(self, name)

        return MySpecClass()

    def test_overridable(self, spec_cls):
        assert spec_cls.overridable_int == 10
        assert spec_cls.with_overridable_int(100).overridable_int == 100
        assert "overridable_int" in spec_cls.with_overridable_int(100).__dict__
        assert spec_cls.static_str == "string"

        spec_cls.overridable_int = 100
        assert spec_cls.overridable_int == 100
        del spec_cls.overridable_int
        assert spec_cls.overridable_int == 10

        with pytest.raises(AttributeError):
            spec_cls.with_static_str("override")

    def test_cache(self, spec_cls):
        assert spec_cls.cached_time == spec_cls.cached_time
        assert spec_cls.__dict__["cached_time"] == spec_cls.cached_time
        assert spec_cls.with_cached_time(10.2).cached_time == 10.2

    def test_type_checking(self, spec_cls):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "Property override for `MySpecClass.bad_typecheck` returned an invalid type [got `'string'`; expecting `int`]."
            ),
        ):
            spec_cls.bad_typecheck

    def test_no_methods(self, spec_cls):
        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Property override for `MySpecClass.no_methods` does not have a getter method."
            ),
        ):
            spec_cls.no_methods

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Property override for `MySpecClass.no_methods` does not have a setter and/or is not configured to be overridable."
            ),
        ):
            spec_cls.no_methods = 10

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Property override for `MySpecClass.no_methods` has no cache or override to delete."
            ),
        ):
            del spec_cls.no_methods

    def test_method_overrides(self, spec_cls):
        with pytest.raises(
            RuntimeError, match=re.escape("In `method_overrides` getter.")
        ):
            spec_cls.method_overrides

        with pytest.raises(
            RuntimeError, match=re.escape("In `method_overrides` setter.")
        ):
            spec_cls.method_overrides = 10

        with pytest.raises(
            RuntimeError, match=re.escape("In `method_overrides` deleter.")
        ):
            del spec_cls.method_overrides

    def test_invalidation(self, spec_cls):
        obj = spec_cls.invalidated_obj
        aobj = spec_cls.always_invalidated_obj
        assert spec_cls.invalidated_obj is obj
        assert spec_cls.always_invalidated_obj is aobj

        spec_cls.cached_time = 10.2
        assert spec_cls.invalidated_obj is obj
        assert spec_cls.always_invalidated_obj is not aobj

        spec_cls.overridable_int = 1
        assert spec_cls.invalidated_obj is not obj
        assert spec_cls.always_invalidated_obj is not aobj

        obj = spec_cls.invalidated_obj
        aobj = spec_cls.always_invalidated_obj
        del spec_cls.overridable_int
        assert spec_cls.invalidated_obj is not obj
        assert spec_cls.always_invalidated_obj is not aobj

        obj = spec_cls.invalidated_obj
        aobj = spec_cls.always_invalidated_obj
        spec_cls.with_overridable_int(10, _inplace=True)
        assert spec_cls.invalidated_obj is not obj
        assert spec_cls.always_invalidated_obj is not aobj

    def test_attribute_error_handling(self, spec_cls):

        with pytest.raises(
            NestedAttributeError, match=re.escape("I will be swallowed!")
        ):
            spec_cls.suppresses_attribute_error

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "I swallowed the attribute error raised by `raises_attribute_error`."
            ),
        ):
            spec_cls.raises_attribute_error
