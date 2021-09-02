import builtins
import copy
import functools
import inspect
from typing import Any, Callable, Dict, Set, Type, Union

from lazy_object_proxy import Proxy

from spec_classes.errors import FrozenInstanceError
from spec_classes.types import MISSING

from .type_checking import check_type, type_label


def mutate_attr(
    obj: Any,
    attr: str,
    value: Any,
    inplace: bool = False,
    type_check: bool = True,
    force: bool = False,
) -> Any:
    """
    Set attribute `attr` of `obj` to `value`, and return the mutated
    instance. If `inplace` is `False`, copy the instance before assigning
    the new attribute value.
    """
    if value is MISSING:
        return obj

    metadata = getattr(obj, "__spec_class__", None)

    if metadata:

        # Abort if class is frozen.
        if not force and inplace and metadata.frozen:
            raise FrozenInstanceError(
                f"Cannot mutate attribute `{attr}` of frozen spec class `{obj.__class__.__name__}`."
            )

        # If attribute is managed by spec classes, prepare it and check the type
        attr_spec = metadata.attrs.get(attr)
        if attr_spec and type_check and not check_type(value, attr_spec.type):
            raise TypeError(
                f"Attempt to set `{obj.__class__.__name__}.{attr}` with an invalid type [got `{repr(value)}`; expecting `{type_label(attr_spec.type)}`]."
            )

    # If not inplace, copy before writing new value for attribute
    if not (inplace or metadata and metadata.do_not_copy):
        obj = copy.deepcopy(obj)

    # Perform actual mutation
    try:
        getattr(obj.__setattr__, "__raw__", setattr)(obj, attr, value)
    except AttributeError as e:
        if e.args == ("can't set attribute",):  # Let's make this error less obtuse.
            raise AttributeError(
                f"Cannot set `{obj.__class__.__name__}.{attr}` to `{value}`. Is this a property without a setter?"
            ) from e
        raise

    # Invalidate any caches depending on this attribute
    if metadata and metadata.invalidation_map and not metadata.frozen:
        invalidate_attrs(obj, attr, metadata.invalidation_map)

    return obj


def invalidate_attrs(obj: Any, attr: str, invalidation_map: Dict[str, Set[str]] = None):
    if invalidation_map is None:
        invalidation_map = obj.__spec_class__.invalidation_map
    if not invalidation_map:
        return

    # Handle invalidation
    for invalidatee in invalidation_map.get(attr, set()) | invalidation_map.get(
        "*", set()
    ):
        try:
            delattr(obj, invalidatee)
        except AttributeError:
            pass


def mutate_value(
    old_value: Any,
    *,
    new_value: Any = MISSING,
    replace: bool = False,
    constructor: Union[Type, Callable] = None,
    attrs: Dict[str, Any] = None,
    transform: Callable = None,
    attr_transforms: Dict[str, Callable] = None,
) -> Any:
    """
    Mutates an existing value according to the following procedure:

    1) If `new_value` is provided, set as current value; otherwise if `patch` is
        `True`, use the old value; otherwise construct a new value via the
        `constructor`.
    2) Update the attributes of the current value with the provided attributes.
    3) Transform the value under `transform`, if provided.
    4) Transform the attributes of the current value with the transforms
        provided in `attr_transforms`.
    5) Return whatever value results from the above steps.

    Note: `old_value` is never mutated in place, and will be copied if necessary
    to prevent such mutation.

    Args:
        old_value: The existing value (pass `MISSING` to start from scratch).
        new_value: The new value to use (if present).
        replace: If `new_value` is not provided, whether to attempt to update the
            existing value (False) or start from scratch using the constructor
            (True).
        constructor: A constructor for building a new object if needed.
        attrs: A mapping of attribute names to target values.
        transform: A transform to apply to the value before returning it.
        attr_transforms: A mapping of attribute names to transforms to apply
            to the attributes of the value before returning it (applied after
            `transform` above).

    Returns:
        The mutated object.
    """
    mutate_safe = False

    # If `new_value` is not `MISSING`, use it; otherwise use `old_value` if not
    # `replace`; otherwise use MISSING.
    if new_value is not MISSING:
        value = new_value
    elif not replace:
        value = old_value
    else:
        value = MISSING

    if isinstance(value, Proxy):
        value = value.__wrapped__

    # If value is a partially executed constructor, hydrate it.
    if isinstance(value, functools.partial):
        value = value()

    # Clean up attrs
    attrs = {
        attr: value for attr, value in (attrs or {}).items() if value is not MISSING
    }

    # If `value` is `MISSING`, or `replace` is True, and we have a
    # constructor, create a new instance with existing attrs. Any attrs not
    # found in the constructor will be assigned later.
    if value is MISSING and constructor is not None:
        mutate_safe = True
        while hasattr(constructor, "__origin__"):
            constructor = constructor.__origin__
        constructor_args = _get_function_args(constructor, attrs)
        value = constructor(
            **{
                attr: value
                for attr, value in (attrs or {}).items()
                if attr in constructor_args
            }
        )

    # If there are any attributes to apply to our value, we do so here,
    # special casing any spec classes.
    if value is not None and value is not MISSING and attrs:
        if not mutate_safe:
            value = copy.deepcopy(value)
            mutate_safe = True
        if hasattr(value, "__spec_class__"):
            for attr, attr_value in attrs.items():
                if attr not in value.__spec_class__.annotations:
                    raise TypeError(
                        f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`."
                    )
                setter = getattr(value, f"with_{attr}", None)
                if setter is None:
                    setattr(
                        value, attr, attr_value
                    )  # pragma: no cover; This should never happen, but it is here just in case!
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
        if hasattr(value, "__spec_class__"):
            for attr, attr_transform in attr_transforms.items():
                if attr not in value.__spec_class__.annotations:
                    raise TypeError(
                        f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`."
                    )
                transformer = getattr(value, f"transform_{attr}", None)
                if (
                    transformer is None
                ):  # pragma: no cover; This should never happen, but it is here just in case!
                    setattr(value, attr, attr_transform(getattr(value, attr)))
                else:
                    value = transformer(attr_transform, _inplace=True)
        else:
            for attr, attr_transform in attr_transforms.items():
                setattr(value, attr, attr_transform(getattr(value, attr)))

    return value


def _get_function_args(function, attrs):
    if hasattr(function, "__name__") and function is getattr(
        builtins, function.__name__, None
    ):
        return set()
    if getattr(function, "__spec_class__.init_overflow_attr", None):
        return set(attrs)
    if not hasattr(function, "__spec_class_args__"):
        # If this "function" is a spec-class, look up its __init__ method for arguments.
        if hasattr(function, "__spec_class_bootstrap__"):
            function.__spec_class_bootstrap__()
            function = function.__init__
        parameters = inspect.Signature.from_callable(function).parameters
        if (
            parameters
            and list(parameters.values())[-1].kind is inspect.Parameter.VAR_KEYWORD
        ):
            return set(attrs or {})
        function.__spec_class_args__ = set(parameters)
    return function.__spec_class_args__
