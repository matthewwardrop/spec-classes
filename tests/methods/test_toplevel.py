import pytest


class TestToplevelMethods:
    def test_update(self, spec_cls):
        spec = spec_cls()
        assert spec.update() is spec
        assert spec.update(scalar=3) is not spec
        assert spec.update(1) == 1
        assert spec.update(scalar=3).scalar == 3
        assert spec.update(scalar=3, _inplace=True) is spec
        assert spec.update(scalar=10, _if=False).scalar == 3

    def test_transform(self, spec_cls):
        spec = spec_cls()
        assert spec.transform() is spec
        assert spec.transform(scalar=lambda scalar: 3) is not spec
        assert spec.transform(lambda spec: 1) == 1
        assert spec.transform(scalar=lambda scalar: 3).scalar == 3
        assert spec.transform(scalar=lambda scalar: 3, _inplace=True) is spec
        assert spec.transform(scalar=10, _if=False).scalar == 3

    def test_reset(self, spec_cls):
        spec = spec_cls(scalar=10)
        assert spec.scalar == 10
        with pytest.raises(AttributeError):
            spec.reset().scalar
        assert spec.scalar == 10
        assert spec.reset(_if=False).scalar == 10
        assert spec.reset() is not spec
        assert spec.reset(_inplace=True) is spec
