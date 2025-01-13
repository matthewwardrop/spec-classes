import inspect
import numbers
import sys
import types
from collections.abc import Sequence as SequenceMutator
from collections.abc import Set as SetMutator
from typing import (
    Any,
    Mapping,
    Sequence,
    Set,
    Type,
    TypeVar,
    Union,
    _GenericAlias,
)

# pylint: disable=protected-access
from typing_extensions import Literal as LiteralExtension

try:
    from typing import Literal
except ImportError:  # pragma: no cover
    from typing_extensions import Literal  # pylint: disable=reimported


def type_match(type_input: Type, type_reference: type) -> bool:
    """
    Check whether `type_input` matches `type_reference`, that latter of
    which is permitted to be a sequence of multiple values; but cannot be
    a parameterized generic type.
    """
    while hasattr(type_input, "__origin__"):
        type_input = type_input.__origin__
    return isinstance(type_input, type) and issubclass(type_input, type_reference)


def check_type(value: Any, attr_type: Type) -> bool:
    """
    Check whether a given object `value` matches the provided `attr_type`.
    """
    if attr_type is Any or isinstance(attr_type, TypeVar):
        return True

    if attr_type is float:
        attr_type = numbers.Real

    if sys.version_info >= (3, 10) and isinstance(attr_type, types.UnionType):
        return any(check_type(value, type_) for type_ in attr_type.__args__)

    if hasattr(attr_type, "__origin__"):  # we are dealing with a `typing` object.
        if attr_type.__origin__ is Union:
            return any(check_type(value, type_) for type_ in attr_type.__args__)

        if attr_type.__origin__ in (Literal, LiteralExtension):
            return value in attr_type.__args__

        if (
            isinstance(attr_type, _GenericAlias)
            or sys.version_info >= (3, 9)
            and isinstance(attr_type, types.GenericAlias)
        ):
            if not isinstance(value, attr_type.__origin__):
                return False
            if attr_type.__origin__ in (list, set):
                for item in value:
                    if not check_type(item, attr_type.__args__[0]):
                        return False
            elif attr_type.__origin__ == dict:
                for k, v in value.items():
                    if not check_type(k, attr_type.__args__[0]):
                        return False
                    if not check_type(v, attr_type.__args__[1]):
                        return False
            elif attr_type.__origin__ == tuple:
                if len(attr_type.__args__) == 2 and attr_type.__args__[1] is Ellipsis:
                    for item in value:
                        if not check_type(item, attr_type.__args__[0]):
                            return False
                else:
                    if len(value) != len(attr_type.__args__):
                        return False
                    for i, item in enumerate(value):
                        if not check_type(item, attr_type.__args__[i]):
                            return False
            elif attr_type.__origin__ == type:
                if not issubclass(value, attr_type.__args__[0]):
                    return False

            return True

        return isinstance(
            value, attr_type.__origin__
        )  # pragma: no cover; This is here as a fallback currently, just in case!

    return isinstance(value, attr_type)


def get_collection_item_type(container_type: Type) -> Type:
    """
    Return the type of object inside a typing container (List, Set, Dict),
    or `None` if this isn't annotated.
    """
    if not hasattr(container_type, "__args__"):  # i.e. this is not a `typing` container
        return Any

    item_type = Any
    if type_match(container_type, Mapping) and len(container_type.__args__) == 2:
        item_type = container_type.__args__[1]
    elif (
        type_match(container_type, (Sequence, Set, SequenceMutator, SetMutator))
        or len(container_type.__args__) == 1
    ):
        item_type = container_type.__args__[0]
    if isinstance(item_type, TypeVar):
        item_type = Any
    return item_type


def get_spec_class_for_type(
    attr_type: Type, allow_polymorphic=False
) -> Union[Type, None]:
    """
    Get the spec class to associated with a given attribute type. This is
    useful when `attr_type` is a polymorphic type, e.g.
    Union[SpecClass, str]. It works by finding the spec class type in the
    polymorphic type. If there is not exactly one spec class type, `None` is
    returned.
    """
    if hasattr(attr_type, "__spec_class__"):
        return attr_type
    if allow_polymorphic and getattr(attr_type, "__origin__", None) is Union:
        spec_classes = []
        for typ in attr_type.__args__:
            spec_typ = get_spec_class_for_type(typ)
            if spec_typ is not None:
                spec_classes.append(spec_typ)
        if len(spec_classes) == 1:
            return spec_classes[0]
    return None


def type_label(attr_type: Type) -> str:
    """
    Generate the label to be used to describe an `attr_type` in generated
    user documentation. Since we care about the output of this method when
    `attr_type` points to a `spec_cls` decorated type, we don't make this
    method general.
    """
    if attr_type is types.NoneType:
        return "None"
    if (
        sys.version_info >= (3, 10)
        and isinstance(attr_type, types.UnionType)
        or getattr(attr_type, "__origin__", None) is Union
    ):
        return " | ".join(type_label(arg) for arg in attr_type.__args__)
    if hasattr(attr_type, "__origin__"):  # Generics
        if str(attr_type.__origin__).rsplit(".", 1)[-1] == "Literal":
            return f"Literal[{', '.join(repr(arg) for arg in attr_type.__args__)}]"
        label = type_label(attr_type.__origin__)
        if hasattr(attr_type, "__args__") and not any(
            isinstance(arg, TypeVar) for arg in attr_type.__args__
        ):
            return (
                f"{label}[{', '.join(type_label(arg) for arg in attr_type.__args__)}]"
            )
        return label
    if str(attr_type).startswith("typing."):
        return str(attr_type).replace("typing.", "", 1)
    if not inspect.isclass(attr_type):
        if hasattr(attr_type, "__orig_class__"):
            return type_label(attr_type.__orig_class__)
        return type_label(type(attr_type))
    return attr_type.__name__


def type_instantiate(attr_type: Type, **kwargs) -> Any:
    """
    Instantiate a nominated type.
    """
    while hasattr(attr_type, "__origin__"):
        attr_type = attr_type.__origin__
    return attr_type(**kwargs)
