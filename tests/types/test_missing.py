import copy

from spec_classes.types.missing import EMPTY, MISSING, SENTINEL


def test_missing():
    assert MISSING != EMPTY
    assert MISSING != SENTINEL
    assert bool(MISSING) is False
    assert repr(MISSING) == "MISSING"
    assert copy.copy(MISSING) is MISSING
    assert copy.deepcopy(MISSING) is MISSING
    assert MISSING() is MISSING
