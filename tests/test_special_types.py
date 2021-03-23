import pytest

import copy
import re

from spec_classes import spec_class
from spec_classes.special_types import MISSING, _MissingType, spec_property


def test_missing():
    assert MISSING is _MissingType()
    assert bool(MISSING) is False
    assert repr(MISSING) == 'MISSING'
    assert copy.copy(MISSING) is MISSING
    assert copy.deepcopy(MISSING) is MISSING


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

        return MySpecClass()

    def test_overridable(self, spec_cls):
        assert spec_cls.overridable_int == 10
        assert spec_cls.with_overridable_int(100).overridable_int == 100
        assert 'overridable_int' in spec_cls.with_overridable_int(100).__dict__
        assert spec_cls.static_str == "string"

        spec_cls.overridable_int = 100
        assert spec_cls.overridable_int == 100
        del spec_cls.overridable_int
        assert spec_cls.overridable_int == 10

        with pytest.raises(AttributeError):
            spec_cls.with_static_str("override")

    def test_cache(self, spec_cls):
        assert spec_cls.cached_time == spec_cls.cached_time
        assert spec_cls.__dict__['cached_time'] == spec_cls.cached_time
        assert spec_cls.with_cached_time(10.2).cached_time == 10.2

    def test_type_checking(self, spec_cls):
        with pytest.raises(ValueError, match=re.escape("Property override for `MySpecClass.bad_typecheck` returned an invalid type [got `'string'`; expecting `<class 'int'>`].")):
            spec_cls.bad_typecheck

    def test_no_methods(self, spec_cls):
        with pytest.raises(AttributeError, match=re.escape("Property override for `MySpecClass.no_methods` does not have a getter method.")):
            spec_cls.no_methods

        with pytest.raises(AttributeError, match=re.escape("Property override for `MySpecClass.no_methods` does not have a setter and/or is not configured to be overridable.")):
            spec_cls.no_methods = 10

        with pytest.raises(AttributeError, match=re.escape("Property override for `MySpecClass.no_methods` has no cache or override to delete.")):
            del spec_cls.no_methods

    def test_method_overrides(self, spec_cls):
        with pytest.raises(RuntimeError, match=re.escape("In `method_overrides` getter.")):
            spec_cls.method_overrides

        with pytest.raises(RuntimeError, match=re.escape("In `method_overrides` setter.")):
            spec_cls.method_overrides = 10

        with pytest.raises(RuntimeError, match=re.escape("In `method_overrides` deleter.")):
            del spec_cls.method_overrides
