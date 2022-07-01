import numbers
from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Type

from spec_classes.utils.type_checking import check_type, type_label


class ValidatedTypeMeta(ABCMeta):
    """
    The metaclass for `ValidatedType`.

    This metaclass just hooks into the `__instancecheck__` functionality
    provided by ABCMeta, so that `ValidatedType` can override the behaviour
    of `isinstance()`.
    """

    def __instancecheck__(cls, obj: Any) -> bool:
        return cls.validate(obj)


class ValidatedType(metaclass=ValidatedTypeMeta):
    """
    A base class representing a validated type.

    `ValidatedType` and its subclasses can be used as type annotations, and
    can be used to validate types. Whenever `isinstance(obj, ValidatedType)` is
    called, the result is `ValidatedType.validate(obj)`. `ValidatedType`
    and its subclasses should not (and cannot) be instantiated.
    """

    def __new__(cls, *args, **kwargs):
        raise RuntimeError(
            f"`{type_label(cls)}` is intended to be used as a type annotation, and should not be instantiated."
        )

    @classmethod
    @abstractmethod
    def validate(cls, obj: Any) -> bool:
        ...  # pragma: no cover


def validated(
    validator: Callable[[Any], bool], name: str = "validated"
) -> ValidatedType:
    """
    Construct a validated type based on the nominated `validator`.

    Args:
        validator: The validator to use when verifying types.
        name: The name to use when representing the `ValidatedType` subclass.
            Note that this does not need to be a valid Python identifier.
    """
    return type(
        name,
        (ValidatedType,),
        {
            "validate": validator,
        },
    )


def bounded(
    numeric_type: Type,
    *,
    ge: numbers.Number = None,
    gt: numbers.Number = None,
    le: numbers.Number = None,
    lt: numbers.Number = None,
) -> ValidatedType:
    """
    Construct a validated type that bounds a numeric type from above and/or below.

    Args:
        numeric_type: The type of number to be bounded (e.g. float, numbers.Number, etc).
        ge: The >= bound for the number.
        gt: The > bound for the number.
        le: The <= bound for the number.
        lt: The < bound for the number.

    Notes:
        - Only one of ge/gt can be specified at the same time, and same for le/lt.
    """
    # Validate input parameters
    if ge and gt:
        raise ValueError("Can only specify at most one of `gt` or `ge`.")
    if le and lt:
        raise ValueError("Can only specify at most one of `lt` or `le`.")

    # Generate name of type
    type_str = type_label(numeric_type)
    upper_bound_str = "∞)"
    lower_bound_str = "(-∞"
    if le is not None:
        upper_bound_str = f"{le}]"
    if lt is not None:
        upper_bound_str = f"{lt})"
    if ge is not None:
        lower_bound_str = f"[{ge}"
    if gt is not None:
        lower_bound_str = f"({gt}"
    name = f"{type_str}∊{lower_bound_str},{upper_bound_str}"

    # Validator
    def validator(obj):
        if not check_type(obj, numeric_type):
            return False
        if ge is not None and obj < ge:
            return False
        if gt is not None and obj <= gt:
            return False
        if le is not None and obj > le:
            return False
        if lt is not None and obj >= lt:
            return False
        return True

    return validated(validator, name=name)
