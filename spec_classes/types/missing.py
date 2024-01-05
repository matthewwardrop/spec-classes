# Sentinel for unset inputs to spec_class methods
class _MissingType:
    __instances__ = {}

    def __new__(cls, name="MISSING"):
        if name not in cls.__instances__:
            cls.__instances__[name] = super(_MissingType, cls).__new__(cls)
        return cls.__instances__[name]

    def __init__(self, name="MISSING"):
        self.name = name

    def __bool__(self):
        return False

    def __repr__(self):
        return self.name

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


MISSING = _MissingType()
UNSPECIFIED = _MissingType("UNSPECIFIED")
