import copy

from spec_classes.types.missing import _MissingType, MISSING


def test_missing():
    assert MISSING is _MissingType()
    assert bool(MISSING) is False
    assert repr(MISSING) == "MISSING"
    assert copy.copy(MISSING) is MISSING
    assert copy.deepcopy(MISSING) is MISSING
