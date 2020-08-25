
# Sentinel for unset inputs to spec_class methods
class _MissingType:

    def __bool__(self):
        return False

    def __repr__(self):
        return "MISSING"


MISSING = _MissingType()
