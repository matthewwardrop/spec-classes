import copy

from spec_classes.special_types import MISSING, _MissingType


def test_missing():
    assert MISSING is _MissingType()
    assert bool(MISSING) is False
    assert repr(MISSING) == 'MISSING'
    assert copy.copy(MISSING) is MISSING
    assert copy.deepcopy(MISSING) is MISSING
