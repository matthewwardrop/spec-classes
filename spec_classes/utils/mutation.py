import builtins
import copy
import copyreg
import functools
import inspect
from contextlib import contextmanager
from types import ModuleType
from typing import Any, Callable, Dict, Optional, Set, Type, Union

from lazy_object_proxy import Proxy

from spec_classes.errors import FrozenInstanceError
from spec_classes.types import Attr, MISSING

from .type_checking import check_type, type_label


def protect_via_deepcopy(obj: Any, memo: Any = None) -> Any:
    """
    Protect the incoming `obj` from subsequent mutations by returning an
    identical copy of that object.

    Args:
        obj: The object to protect.
        memo: An (optional) memo object to pass down through `copy.deepcopy`.

    Returns:
        A mutate-safe copy of the incoming object.

    Notes:
      - For base immutable types copying is not required to ensure object
        protection, and so such objects are returned as is.
      - Modules are not copyable, and so are also returned as is.
    """
    if isinstance(obj, (bool, int, float, str, bytes, type, ModuleType)):
        return obj
    with _modules_copyable():
        return copy.deepcopy(obj, memo)


@contextmanager
def _modules_copyable():
    module_reductor = copyreg.dispatch_table.get(ModuleType, MISSING)
    if module_reductor is MISSING:
        copyreg.dispatch_table[ModuleType] = lambda module: "passthrough"
    yield
    if module_reductor is MISSING:
        del copyreg.dispatch_table[ModuleType]


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
        if e.args in (  # Let's make this error less obtuse.
            ("can't set attribute",),  # Python <3.10
            ("can't set attribute 'x'",),  # Python >=3.10
        ):
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
    prepare: Callable[[Any], Any] = None,
    attrs: Dict[str, Any] = None,
    constructor: Union[Type, Callable] = None,
    expected_type: Type = None,
    transform: Callable = None,
    attr_transforms: Dict[str, Callable] = None,
    inplace: bool = False,
) -> Any:
    """
    Mutates an existing value according to the following procedure:

    1) If `new_value` is not `MISSING` (or `replace` is `True`), set it as
        the current value; otherwise take `old_value`.
    2) If a `prepare` callable is provided, and the `new_value` above was chose,
        run the value through the `prepare` method.
    3) If `constructor` and `expected_type` are both provided and `value` is not
        of the type expected and is a dictionary, interpret `value` as a
        dictionary of arguments to pass to the constructor.
    4) If the value is `MISSING`, use the provided constructor to build a new
        instance (using as many of the `attrs` as is possible).
    5) Set any remaining attributes on current value.
    6) Transform the value under `transform`, if provided.
    7) Transform the attributes of the current value with the transforms
        provided in `attr_transforms`.
    8) Return whatever value results from the above steps.

    Note: `old_value` is never mutated in place, and will be copied if necessary
    to prevent such mutation unless `inplace` is `True`.

    Args:
        old_value: The existing value (pass `MISSING` to start from scratch).
        new_value: The new value to use (if present).
        replace: If `new_value` is not provided, whether to attempt to update the
            existing value (False) or start from scratch using the constructor
            (True).
        attrs: A mapping of attribute names to target values.
        prepare: An optional callable that is called before the constructor to
            populate the value (e.g. from a lookup table). Attributes are not
            passed to this `prepare` method.
        constructor: A constructor for building a new object if needed.
        transform: A transform to apply to the value before returning it.
        attr_transforms: A mapping of attribute names to transforms to apply
            to the attributes of the value before returning it (applied after
            `transform` above).

    Returns:
        The mutated object.
    """
    mutate_safe = inplace
    used_attrs = set()

    # If `new_value` is not `MISSING`, use it; otherwise use `old_value` if not
    # `replace`; otherwise use MISSING.
    if new_value is not MISSING:
        value = new_value
    elif not replace:
        value = old_value
        prepare = None  # Old values have already been prepared, so we suppress further preparation.
    else:
        value = MISSING

    if isinstance(value, Proxy):
        value = value.__wrapped__

    # Run the value through the (optional) preparer.
    if prepare is not None:
        value = prepare(value)

    # Check whether value should be interpreted as constructor arguments, and
    # construct objects if so.
    # Note: We do not merge this into the below because this construction is
    # more strict (all attributes must be handled by the constructor).
    if (
        constructor
        and expected_type
        and isinstance(value, dict)
        and not check_type(value, expected_type)
    ):
        value = constructor(
            **{
                **(attrs or {}),
                **value,
            }
        )

    # If `value` is `MISSING`, or `replace` is True, and we have a
    # constructor, create a new instance with existing attrs. Any attrs not
    # found in the constructor will be assigned later.
    elif value is MISSING and constructor is not None:
        mutate_safe = True
        while hasattr(constructor, "__origin__"):
            constructor = constructor.__origin__
        if attrs:
            constructor_args = _get_function_args(constructor, attrs)
            used_attrs.update(constructor_args)
            value = constructor(
                **{
                    attr: value
                    for attr, value in attrs.items()
                    if attr in constructor_args and value is not MISSING
                }
            )
        else:
            value = constructor()

    # If there are any left-over attributes to apply to our value, we do so here.
    if value is not None and value is not MISSING and attrs:
        if not mutate_safe:
            value = protect_via_deepcopy(value)
            mutate_safe = True
        for attr, attr_value in attrs.items():
            if attr in used_attrs:
                continue
            if attr_value is not MISSING:
                setattr(value, attr, attr_value)
    elif attrs:
        raise ValueError("Cannot use attrs on a missing value without a constructor.")

    # If `transform` is provided, transform `value`
    if transform:
        value = transform(value)

    # If `attr_transforms` is provided, transform attributes
    if attr_transforms:
        if not mutate_safe:
            value = protect_via_deepcopy(value)
        for attr, attr_transform in attr_transforms.items():
            transformed_value = attr_transform(getattr(value, attr, MISSING))
            if transformed_value is not MISSING:
                setattr(value, attr, transformed_value)

    return value


def prepare_attr_value(
    attr_spec: Attr, instance: Any, value: Any, attrs: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Prepare an incoming `value` for assignment to the attribute associated with
    `attr_spec`. This can be called independently, such as in `spec_property`,
    to ensure that dynamically generated values are consistent with the
    operations of `with_<attr>`.

    Args:
        attr_spec: The attribute specification for which the value is being
            prepared.
        instance: The spec-class instance for which the value is being prepared.
        value: The value to be prepared.
        attrs: Optional arguments to pass to the constructor/set on the value in
            `mutate_value`.

    Returns:
        The prepared value.
    """
    value = mutate_value(
        old_value=MISSING,
        new_value=value,
        prepare=(
            functools.partial(attr_spec.prepare, instance)
            if attr_spec.prepare
            else None
        ),
        constructor=attr_spec.constructor,
        expected_type=attr_spec.type,
        attrs=attrs,
    )
    if attr_spec.is_collection:
        value = (
            attr_spec.get_collection_mutator(instance=instance, collection=value)
            .prepare()
            .collection
        )
    return value


def _get_function_args(function, attrs):
    # If this is a built-in type, no attrs should be passed to the constructor.
    if hasattr(function, "__name__") and function is getattr(
        builtins, function.__name__, None
    ):
        return set()
    function = getattr(function, "__init__", function)
    if function is object.__init__:
        return set()
    # Otherwise, lookup signature and annotate function with args.
    if not hasattr(function, "__spec_class_args__"):
        try:
            parameters = function.__signature__.parameters
        except AttributeError:
            try:
                parameters = inspect.signature(function).parameters
            except ValueError:  # pragma: no cover; Python 3.7 and newer raise a ValueError for C functions
                parameters = {}
        if (
            parameters
            and list(parameters.values())[-1].kind is inspect.Parameter.VAR_KEYWORD
        ):
            return set(attrs or {})
        try:
            function.__spec_class_args__ = set(parameters)
        except AttributeError:  # pragma: no cover; this is a *very* rare edge-case affecting functions defined in C.
            return set(parameters)
    return function.__spec_class_args__
