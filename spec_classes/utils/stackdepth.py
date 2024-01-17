import sys


def get_spec_classes_depth():
    """
    The recursion depth of the caller into spec-classes from first
    non-spec-classes frame.

    Args:
        offset: An offset to apply the calculated depth. An `offset` of 1 aligns
            the depth with that of the caller.
    """
    stacklevel = 0
    f = sys._getframe()
    while f.f_back and (
        "spec_classes" in f.f_code.co_filename or f.f_code.co_filename == "<string>"
    ):
        f = f.f_back
        stacklevel += 1
    return stacklevel
