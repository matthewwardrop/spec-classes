import builtins
import copy
import functools
import inspect
from typing import Any, Callable, Dict, Set, Type, Union

from lazy_object_proxy import Proxy

from spec_classes.errors import FrozenInstanceError
from spec_classes.special_types import MISSING

from .type_checking import check_type, type_label


def mutate_attr(obj: Any, attr: str, value: Any, inplace: bool = False, type_check: bool = True, force: bool = False) -> Any:
    """
    Set attribute `attr` of `obj` to `value`, and return the mutated
    instance. If `inplace` is `False`, copy the instance before assigning
    the new attribute value.
    """
    if value is MISSING:
        return obj
    if not force and inplace and getattr(obj, '__spec_class_frozen__', False):
        raise FrozenInstanceError(f"Cannot mutate attribute `{attr}` of frozen spec class `{obj.__class__.__name__}`.")
    if type_check:
        attr_type = obj.__spec_class_annotations__[attr]
        if not check_type(value, attr_type):
            raise TypeError(f"Attempt to set `{obj.__class__.__name__}.{attr}` with an invalid type [got `{repr(value)}`; expecting `{type_label(attr_type)}`].")
    if not inplace:
        obj = copy.deepcopy(obj)
    try:
        if hasattr(obj.__setattr__, '__raw__'):
            obj.__setattr__.__raw__(obj, attr, value)
        else:
            setattr(obj, attr, value)  # pragma: no cover
    except AttributeError as e:
        raise AttributeError(f"Cannot set `{obj.__class__.__name__}.{attr}` to `{value}`. Is this a property without a setter?") from e
    invalidate_attrs(obj, attr)
    return obj


def invalidate_attrs(obj: Any, attr: str, invalidation_map: Dict[str, Set[str]] = None):
    if getattr(obj, '__spec_class_frozen__', False):
        return

    if invalidation_map is None:
        invalidation_map = getattr(obj, '__spec_class_invalidation_map__', {})

    # Handle invalidation
    for invalidatee in invalidation_map.get(attr, set()) | invalidation_map.get('*', set()):
        try:
            delattr(obj, invalidatee)
        except AttributeError:
            pass


def mutate_value(
        old_value: Any, *, new_value: Any = MISSING, constructor: Union[Type, Callable] = None, transform: Callable = None,
        attrs: Dict[str, Any] = None, attr_transforms: Dict[str, Callable] = None, replace: bool = False
) -> Any:
    """
    General strategy for generating an updated value from an old value, and
    either a new value or a combination of new attribute values and/or
    transforms.
    """
    mutate_safe = False

    # If `new_value` is not `MISSING`, use it, otherwise use `old_value`.
    if new_value is not MISSING:
        value = new_value
    else:
        value = old_value

    if isinstance(value, Proxy):
        value = value.__wrapped__

    # If value is a partially executed constructor, hydrate it.
    if isinstance(value, functools.partial):
        value = value()

    # If `value` is `MISSING`, or `replace` is True, and we have a
    # constructor, create a new instance with existing attrs. Any attrs not
    # found in the constructor will be assigned later.
    if (value is MISSING or replace) and constructor is not None:
        mutate_safe = True
        while hasattr(constructor, '__origin__'):
            constructor = constructor.__origin__
        constructor_args = _get_function_args(constructor)
        value = constructor(**{attr: value for attr, value in (attrs or {}).items() if attr in constructor_args})
        attrs = {
            attr: value
            for attr, value in (attrs or {}).items()
            if attr not in constructor_args
        }

    # If there are any attributes to apply to our value, we do so here,
    # special casing any spec classes.
    if value is not None and value is not MISSING and attrs:
        if not mutate_safe:
            value = copy.deepcopy(value)
            mutate_safe = True
        if getattr(value, '__is_spec_class__', False):
            for attr, attr_value in attrs.items():
                if attr not in value.__spec_class_annotations__:
                    raise TypeError(f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`.")
                setter = getattr(value, f'with_{attr}', None)
                if setter is None:
                    setattr(value, attr, attr_value)  # pragma: no cover; This should never happen, but it is here just in case!
                else:
                    value = setter(attr_value, _inplace=True)
        else:
            for attr, attr_value in attrs.items():
                setattr(value, attr, attr_value)
    elif attrs:
        raise ValueError("Cannot use attrs on a missing value without a constructor.")

    # If `transform` is provided, transform `value`
    if transform:
        value = transform(value)

    # If `attr_transforms` is provided, transform attributes
    if attr_transforms:
        if not mutate_safe:
            value = copy.deepcopy(value)
        if getattr(value, '__is_spec_class__', False):
            for attr, attr_transform in attr_transforms.items():
                if attr not in value.__spec_class_annotations__:
                    raise TypeError(f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`.")
                transformer = getattr(value, f'transform_{attr}', None)
                if transformer is None:  # pragma: no cover; This should never happen, but it is here just in case!
                    setattr(value, attr, attr_transform(getattr(value, attr)))
                else:
                    value = transformer(attr_transform, _inplace=True)
        else:
            for attr, attr_transform in attr_transforms.items():
                setattr(value, attr, attr_transform(getattr(value, attr)))

    return value


def _get_function_args(function):
    if function is getattr(builtins, function.__name__, None):
        return set()
    if not hasattr(function, '__spec_class_args__'):
        # If this "function" is a spec-class, look up its __init__ method for arguments.
        if getattr(function, '__is_spec_class__', False):
            function.__spec_class_bootstrap__()
            function = function.__init__
        function.__spec_class_args__ = set(inspect.Signature.from_callable(function).parameters)
    return function.__spec_class_args__
