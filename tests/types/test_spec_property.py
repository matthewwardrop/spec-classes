import re

import pytest

from spec_classes import spec_class, spec_property, classproperty
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

            @spec_property(warn_on_override=True)
            def set_triggers_generic_warning(self):
                return 1

            @spec_property(warn_on_override=DeprecationWarning("Custom warning."))
            def set_triggers_custom_warning(self):
                return 1

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

    def test_warnings(self, spec_cls):
        with pytest.warns(
            UserWarning,
            match=re.escape(
                "Property `MySpecClass.set_triggers_generic_warning` is now overridden and will not update based on instance state."
            ),
        ):
            spec_cls.set_triggers_generic_warning = 10
        with pytest.warns(DeprecationWarning, match=re.escape("Custom warning.")):
            spec_cls.set_triggers_custom_warning = 10


class TestSpecClassProperty:
    def test_basic_usage(self):
        class A:
            @classproperty(overridable=True)
            def a(cls):
                return 1

            @classproperty(cache=True, overridable=True)
            def b(cls):
                return 1

            @classproperty(cache=True, cache_per_subclass=True, overridable=True)
            def c(cls):
                return 1

        class B(A):
            pass

        a = A()
        b = A()
        c = B()

        assert A.a == a.a
        assert a.a == b.a
        assert a.b == b.b
        assert a.c == c.c
        assert A.__dict__["a"]._cache == {}
        assert A.__dict__["b"]._cache == {None: 1}
        assert A.__dict__["c"]._cache == {A: 1, B: 1}

        with pytest.raises(AttributeError):
            del a.a
        del a.b
        del a.c
        assert A.__dict__["a"]._cache == {}
        assert A.__dict__["b"]._cache == {}
        assert A.__dict__["c"]._cache == {B: 1}

        a.a = 10
        a.b = 10
        a.c = 10
        assert A.__dict__["a"]._cache == {None: 10}
        assert A.__dict__["b"]._cache == {None: 10}
        assert A.__dict__["c"]._cache == {A: 10, B: 1}

    def test_spec_class(self):
        @spec_class
        class MySpec:
            a: int

            @classproperty
            def a(cls):
                return "Hello!"

        with pytest.raises(TypeError):
            MySpec().a

    def test_manual_funcs(self):
        class A:
            @classproperty
            def a(cls):
                return 1

            @a.setter
            def a(cls, value):
                return

            @a.deleter
            def a(cls):
                return

        assert A.a == 1
        assert A().a == 1

        A().a = 10
        del A().a

    def test_immutable(self):
        class A:
            @classproperty
            def a(cls):
                return 1

        assert A().a == 1

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Class property for `A.a` does not have a setter and/or is not configured to be overridable."
            ),
        ):
            A().a = 10

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Class property for `A.a` has no cache or override to delete."
            ),
        ):
            del A().a

    def test_edge_cases(self):
        class A:
            no_methods = classproperty(None, overridable=False)

            @classproperty
            def raises_attribute_error(cls):
                raise AttributeError("I will be swallowed!")

            @classproperty(allow_attribute_error=False)
            def suppresses_attribute_error(cls):
                raise AttributeError("I will be swallowed!")

            def __getattr__(self, name):
                if name == "raises_attribute_error":
                    raise AttributeError(
                        "I swallowed the attribute error raised by `raises_attribute_error`."
                    )
                return object.__getattribute__(self, name)

        with pytest.raises(
            AttributeError,
            match=re.escape(
                "Class property for `A.no_methods` does not have a getter method."
            ),
        ):
            A().no_methods

        with pytest.raises(
            AttributeError,
            match="I swallowed the attribute error raised by `raises_attribute_error`.",
        ):
            A().raises_attribute_error

        with pytest.raises(
            NestedAttributeError, match=re.escape("I will be swallowed!")
        ):
            A().suppresses_attribute_error

    def test_warnings(self):
        class A:
            @classproperty(overridable=True, warn_on_override=True)
            def set_triggers_generic_warning(self):
                return 1

            @classproperty(
                overridable=True, warn_on_override=DeprecationWarning("Custom warning.")
            )
            def set_triggers_custom_warning(self):
                return 1

        with pytest.warns(
            UserWarning,
            match=re.escape(
                "Class property `A.set_triggers_generic_warning` is now overridden and will not update based on class state."
            ),
        ):
            A().set_triggers_generic_warning = 10
        with pytest.warns(DeprecationWarning, match=re.escape("Custom warning.")):
            A().set_triggers_custom_warning = 10
