"""Mypy plugin for spec-classes.

Provides accurate type information for @spec_class decorated classes, including:
- Corrected __init__ signature (all non-key args are keyword-only and optional)
- Dynamically generated methods: with_<attr>, update_<attr>, transform_<attr>, reset_<attr>
- Collection item methods: with_<item>, update_<item>, transform_<item>, without_<item>
- Top-level methods: update(), transform(), reset()

Usage in mypy.ini or pyproject.toml:
    [mypy]
    plugins = spec_classes.mypy_plugin

    [tool.mypy]
    plugins = ["spec_classes.mypy_plugin"]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import inflect
from mypy.nodes import (
    ARG_NAMED_OPT,
    ARG_OPT,
    ARG_POS,
    ARG_STAR2,
    MDEF,
    Argument,
    AssignmentStmt,
    CallExpr,
    Decorator,
    EllipsisExpr,
    FuncDef,
    NameExpr,
    OverloadedFuncDef,
    PlaceholderNode,
    RefExpr,
    StrExpr,
    SymbolTableNode,
    TempNode,
    TypeAlias,
    TypeVarExpr,
    Var,
)
from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_method_to_class, deserialize_and_fixup_type
from mypy.server.trigger import make_wildcard_trigger
from mypy.subtypes import is_subtype
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    NoneType,
    TypeOfAny,
    TypeVarId,
    TypeVarType,
    UnionType,
    get_proper_type,
)
from mypy.typevars import fill_typevars

if TYPE_CHECKING:
    from mypy.nodes import Node, TypeInfo
    from mypy.types import Type

SPEC_CLASS_FULLNAMES: Final = frozenset(
    {
        "spec_classes.spec_class.spec_class",
        "spec_classes.spec_class",
    }
)
ATTR_FULLNAMES: Final = frozenset(
    {
        "spec_classes.types.attr.Attr",
        "spec_classes.types.Attr",
        "spec_classes.Attr",
    }
)

_SEQUENCE_ORIGINS: Final = frozenset(
    {
        "builtins.list",
        "collections.abc.MutableSequence",
        "typing.List",
        "spec_classes.types.keyed.KeyedList",
    }
)
_MAPPING_ORIGINS: Final = frozenset(
    {
        "builtins.dict",
        "collections.abc.MutableMapping",
        "typing.Dict",
    }
)
_SET_ORIGINS: Final = frozenset(
    {
        "builtins.set",
        "collections.abc.MutableSet",
        "typing.Set",
        "spec_classes.types.keyed.KeyedSet",
    }
)

SELF_TVAR_NAME: Final = "_SC"

_INFLECT = inflect.engine()
_INFLECT_CACHE: dict[str, str] = {}


def plugin(version: str) -> type[Plugin]:
    return SpecClassPlugin


class SpecClassPlugin(Plugin):
    def get_class_decorator_hook_2(self, fullname: str):
        if fullname in SPEC_CLASS_FULLNAMES:
            return spec_class_hook
        return None


# ---------------------------------------------------------------------------
# Attribute metadata
# ---------------------------------------------------------------------------


@dataclass
class SpecAttrInfo:
    name: str
    type: Type
    is_in_init: bool
    has_default: bool
    collection_kind: str | None  # "list", "dict", "set", or None
    key_type: Type | None  # dict key type
    item_type: Type | None  # list/set/dict value type
    item_name: str | None  # singular form for collection methods
    # Not serialised - only meaningful for current-class method generation.
    has_attr_preparer: bool = False  # _prepare_<attr> exists
    has_item_preparer: bool = False  # _prepare_<item_name> exists (collections only)

    def serialize(self) -> dict:
        result: dict = {
            "name": self.name,
            "type": self.type.serialize(),
            "is_in_init": self.is_in_init,
            "has_default": self.has_default,
            "collection_kind": self.collection_kind,
            "item_name": self.item_name,
        }
        if self.key_type is not None:
            result["key_type"] = self.key_type.serialize()
        if self.item_type is not None:
            result["item_type"] = self.item_type.serialize()
        return result

    @classmethod
    def deserialize(cls, data: dict, api) -> SpecAttrInfo:
        typ = deserialize_and_fixup_type(data["type"], api)
        key_type = (
            deserialize_and_fixup_type(data["key_type"], api)
            if data.get("key_type")
            else None
        )
        item_type = (
            deserialize_and_fixup_type(data["item_type"], api)
            if data.get("item_type")
            else None
        )
        return cls(
            name=data["name"],
            type=typ,
            is_in_init=data["is_in_init"],
            has_default=data["has_default"],
            collection_kind=data["collection_kind"],
            key_type=key_type,
            item_type=item_type,
            item_name=data["item_name"],
        )


# ---------------------------------------------------------------------------
# Main hook
# ---------------------------------------------------------------------------


def spec_class_hook(ctx: ClassDefContext) -> bool:
    """Process a @spec_class decorated class."""
    api = ctx.api
    info = ctx.cls.info

    # Step 1: Parse decorator arguments
    reason = ctx.reason
    key = _get_str_arg(reason, "key")
    init_overflow_attr = _get_str_arg(reason, "init_overflow_attr")
    generate_init = _get_bool_arg(reason, "init", default=True, api=api)

    # Step 2: Collect attributes from MRO ancestors
    # We track which attrs are inherited vs. defined on this class.
    # Per-attr helper methods are only generated for current-class attrs;
    # inherited attrs get their methods via the parent and TypeVar unification.
    # Top-level methods (update/transform/reset) are only generated for the
    # root spec-class in the hierarchy to avoid LSP override conflicts.
    attrs: dict[str, SpecAttrInfo] = {}
    has_spec_parent = False
    for ancestor_info in reversed(info.mro[1:-1]):
        if (
            "spec_class_tag" in ancestor_info.metadata
            and "spec_class" not in ancestor_info.metadata
        ):
            return False  # Ancestor not yet fully processed; request another pass
        if "spec_class" not in ancestor_info.metadata:
            continue
        has_spec_parent = True
        api.add_plugin_dependency(make_wildcard_trigger(ancestor_info.fullname))
        for attr_data in ancestor_info.metadata["spec_class"]["attrs"]:
            try:
                attrs[attr_data["name"]] = SpecAttrInfo.deserialize(attr_data, api)
            except Exception:
                return False

    # Capture inherited attr names before we add current-class attrs to the dict.
    # Per-attr methods are only generated for current-class attrs (not inherited).
    inherited_names = set(attrs.keys())

    # Step 3: Collect attributes from the current class body
    for stmt in ctx.cls.defs.body:
        if not isinstance(stmt, AssignmentStmt) or not stmt.new_syntax:
            continue
        lhs = stmt.lvalues[0]
        if not isinstance(lhs, NameExpr):
            continue

        sym = info.names.get(lhs.name)
        if sym is None:
            continue

        node = sym.node
        if isinstance(node, PlaceholderNode):
            return False
        if isinstance(node, (Decorator, OverloadedFuncDef, TypeAlias)):
            continue  # Skip properties / methods / type aliases
        if not isinstance(node, Var):
            continue
        if node.is_classvar:
            continue
        if node.type is None:
            return False  # Type not yet resolved

        is_in_init, has_default = _parse_attr_call(stmt.rvalue, api)
        collection_kind, key_type, item_type = _detect_collection(node.type)
        item_name = _get_item_name(lhs.name) if collection_kind else None

        attrs[lhs.name] = SpecAttrInfo(
            name=lhs.name,
            type=node.type,
            is_in_init=is_in_init,
            has_default=has_default,
            collection_kind=collection_kind,
            key_type=key_type,
            item_type=item_type,
            item_name=item_name,
        )

    attr_list = list(attrs.values())

    # Step 3b: Detect _prepare_* methods for current-class attrs and validate their
    # return types.  Inherited attrs are skipped - the parent already handled them.
    for attr in attr_list:
        if attr.name in inherited_names:
            continue
        attr_preparer, attr_preparer_node = _get_prepare_sym(
            info, f"_prepare_{attr.name}"
        )
        if attr_preparer is not None:
            attr.has_attr_preparer = True
            _check_preparer_return(
                ctx, attr_preparer, attr_preparer_node, attr.type, attr.name
            )
        if attr.collection_kind and attr.item_name and attr.item_type is not None:
            item_preparer, item_preparer_node = _get_prepare_sym(
                info, f"_prepare_{attr.item_name}"
            )
            if item_preparer is not None:
                attr.has_item_preparer = True
                _check_preparer_return(
                    ctx, item_preparer, item_preparer_node, attr.item_type, attr.name
                )

    # Mark early so other classes can detect this class is in progress
    info.metadata["spec_class_tag"] = {}

    # Step 4: Ensure nested spec-class types are ready (defer if not)
    for attr in attr_list:
        check_type = attr.item_type if attr.collection_kind else attr.type
        if check_type is not None:
            nested = _get_spec_class_info(check_type)
            if (
                nested is not None
                and "spec_class_tag" in nested.metadata
                and "spec_class" not in nested.metadata
            ):
                return False

    # Step 5: Build the TypeVar used for Self return types
    tvd = _make_base_self_tvar(ctx)

    # Step 6: Generate __init__ (always includes all attrs including inherited)
    if generate_init:
        _add_init(ctx, attr_list, key, init_overflow_attr)

    # Step 7: Top-level methods - only on the root spec-class.
    # Subclasses inherit these; TypeVar unification narrows the return type.
    # Regenerating them on subclasses would cause LSP override errors because
    # the Self TypeVar changes with each class.
    if not has_spec_parent:
        _add_toplevel_methods(ctx, tvd)

    # Step 8: Per-attribute methods - only for attrs defined on THIS class.
    # Inherited attrs keep their parent-generated methods; TypeVar unification
    # correctly narrows return types when called on subclass instances.
    for attr in attr_list:
        if attr.name in inherited_names:
            continue
        _add_scalar_methods(ctx, attr, tvd)
        if attr.collection_kind:
            _add_collection_methods(ctx, attr, tvd)

    # Step 9: Store metadata for incremental mode and nested expansion
    info.metadata["spec_class"] = {
        "key": key,
        "init_overflow_attr": init_overflow_attr,
        "attrs": [a.serialize() for a in attr_list],
    }

    return True


# ---------------------------------------------------------------------------
# Decorator argument parsing
# ---------------------------------------------------------------------------


def _get_str_arg(reason, name: str) -> str | None:
    if not isinstance(reason, CallExpr):
        return None
    for arg_name, arg_val in zip(reason.arg_names, reason.args):
        if arg_name == name:
            if isinstance(arg_val, StrExpr):
                return arg_val.value
    return None


def _get_bool_arg(reason, name: str, default: bool, api) -> bool:
    if not isinstance(reason, CallExpr):
        return default
    for arg_name, arg_val in zip(reason.arg_names, reason.args):
        if arg_name == name:
            result = api.parse_bool(arg_val)
            return result if result is not None else default
    return default


# ---------------------------------------------------------------------------
# Attribute introspection
# ---------------------------------------------------------------------------


def _parse_attr_call(rvalue, api) -> tuple[bool, bool]:
    """Return (is_in_init, has_default) by inspecting the rvalue."""
    if not isinstance(rvalue, CallExpr):
        return True, not isinstance(rvalue, TempNode)

    callee = rvalue.callee
    if not isinstance(callee, RefExpr):
        return True, True

    fullname = callee.fullname or ""
    # Also accept bare name "Attr" in case fullname isn't resolved yet
    callee_name = callee.name if isinstance(callee, NameExpr) else ""
    if fullname not in ATTR_FULLNAMES and callee_name != "Attr":
        return True, True  # Not an Attr() call; treat as a regular default value

    is_in_init = True
    has_default = False
    for arg_name, arg_val in zip(rvalue.arg_names, rvalue.args):
        if arg_name == "init":
            result = api.parse_bool(arg_val)
            if result is not None:
                is_in_init = result
        elif arg_name in ("default", "default_factory"):
            has_default = True

    return is_in_init, has_default


def _detect_collection(typ: Type) -> tuple[str | None, Type | None, Type | None]:
    """Return (kind, key_type, item_type) for recognised collection types."""
    proper = get_proper_type(typ)
    if not isinstance(proper, Instance):
        return None, None, None

    fullname = proper.type.fullname
    args = proper.args

    if fullname in _SEQUENCE_ORIGINS:
        item = args[0] if args else AnyType(TypeOfAny.unannotated)
        return "list", None, item

    if fullname in _MAPPING_ORIGINS:
        key = args[0] if args else AnyType(TypeOfAny.unannotated)
        val = args[1] if len(args) > 1 else AnyType(TypeOfAny.unannotated)
        return "dict", key, val

    if fullname in _SET_ORIGINS:
        item = args[0] if args else AnyType(TypeOfAny.unannotated)
        return "set", None, item

    return None, None, None


def _get_spec_class_info(typ: Type) -> TypeInfo | None:
    proper = get_proper_type(typ)
    if isinstance(proper, Instance) and "spec_class" in proper.type.metadata:
        return proper.type
    return None


def _get_item_name(attr_name: str) -> str:
    if attr_name not in _INFLECT_CACHE:
        s = _INFLECT.singular_noun(attr_name)
        _INFLECT_CACHE[attr_name] = s if s and s != attr_name else f"{attr_name}_item"
    return _INFLECT_CACHE[attr_name]


def _get_prepare_sym(
    info: TypeInfo, method_name: str
) -> tuple[CallableType | None, Node | None]:
    """Return (CallableType, node) for a _prepare_* method visible on the class, or (None, None)."""
    sym = info.get(method_name)  # MRO-aware: also finds inherited prepare methods
    if sym is None:
        return None, None
    node = sym.node
    if isinstance(node, Decorator):
        node = node.func
    if isinstance(node, FuncDef) and isinstance(node.type, CallableType):
        return node.type, node
    return None, None


def _check_preparer_return(
    ctx: ClassDefContext,
    callable_type: CallableType,
    node: Node | None,
    expected: Type,
    attr_name: str,
) -> None:
    """Emit an error if the preparer's return type is not compatible with *expected*."""
    ret = callable_type.ret_type
    p_ret = get_proper_type(ret)
    p_exp = get_proper_type(expected)

    # Any on either side: nothing to check
    if isinstance(p_ret, AnyType) or isinstance(p_exp, AnyType):
        return

    try:
        compatible = is_subtype(ret, expected)
    except Exception:
        return  # Couldn't determine; skip

    if not compatible:
        context = node if node is not None else ctx.cls
        ctx.api.fail(
            f'Return type of preparer for "{attr_name}" is incompatible: '
            f"expected {expected}, got {ret}",
            context,
        )


# ---------------------------------------------------------------------------
# TypeVar helpers
# ---------------------------------------------------------------------------


def _make_base_self_tvar(ctx: ClassDefContext) -> TypeVarType:
    """Create (or ensure) the Self TypeVar in the class namespace and return a base instance."""
    info = ctx.cls.info
    obj_type = ctx.api.named_type("builtins.object")

    if SELF_TVAR_NAME not in info.names:
        expr = TypeVarExpr(
            SELF_TVAR_NAME,
            f"{info.fullname}.{SELF_TVAR_NAME}",
            [],
            obj_type,
            AnyType(TypeOfAny.from_omitted_generics),
        )
        info.names[SELF_TVAR_NAME] = SymbolTableNode(MDEF, expr)

    return TypeVarType(
        SELF_TVAR_NAME,
        f"{info.fullname}.{SELF_TVAR_NAME}",
        id=TypeVarId(-1, namespace=""),
        values=[],
        upper_bound=fill_typevars(info),
        default=AnyType(TypeOfAny.from_omitted_generics),
    )


def _method_tvar(base: TypeVarType, method_name: str) -> TypeVarType:
    """Return a method-specific copy of the Self TypeVar (unique namespace per method)."""
    # Extract the class fullname from the TypeVar fullname by stripping the tvar name
    tvar_fullname = base.fullname  # e.g. "pkg.MyClass._SC"
    class_fullname = tvar_fullname[: -(len(SELF_TVAR_NAME) + 1)]
    return base.copy_modified(
        id=TypeVarId(base.id.raw_id, namespace=f"{class_fullname}.{method_name}")
    )


# ---------------------------------------------------------------------------
# Method building helpers
# ---------------------------------------------------------------------------


def _bool_arg(name: str, api) -> Argument:
    bt = api.named_type("builtins.bool")
    return Argument(Var(name, bt), bt, EllipsisExpr(), ARG_NAMED_OPT)


def _callable_type(arg_type: Type, api) -> CallableType:
    ft = api.named_type("builtins.function")
    return CallableType(
        arg_types=[arg_type],
        arg_kinds=[ARG_POS],
        arg_names=[None],
        ret_type=arg_type,
        fallback=ft,
    )


def _nested_kwargs(
    nested_info: TypeInfo | None, api, for_transform: bool = False
) -> list[Argument]:
    """Generate keyword-only optional args for each managed attr of a nested spec-class."""
    if nested_info is None:
        return []
    args = []
    for attr_data in nested_info.metadata.get("spec_class", {}).get("attrs", []):
        if not attr_data.get("is_in_init", True):
            continue
        try:
            typ = deserialize_and_fixup_type(attr_data["type"], api)
        except Exception:
            continue
        arg_type = _callable_type(typ, api) if for_transform else typ
        args.append(
            Argument(
                Var(attr_data["name"], arg_type),
                arg_type,
                EllipsisExpr(),
                ARG_NAMED_OPT,
            )
        )
    return args


def _add(
    ctx: ClassDefContext, method_name: str, args: list[Argument], tvd: TypeVarType
) -> None:
    add_method_to_class(
        ctx.api,
        ctx.cls,
        method_name,
        args=args,
        return_type=tvd,
        self_type=tvd,
        tvar_def=tvd,
    )


# ---------------------------------------------------------------------------
# __init__ generation
# ---------------------------------------------------------------------------


def _add_init(
    ctx: ClassDefContext,
    attrs: list[SpecAttrInfo],
    key: str | None,
    init_overflow_attr: str | None,
) -> None:
    args: list[Argument] = []
    for attr in attrs:
        if not attr.is_in_init:
            continue
        if attr.name == key:
            kind = ARG_OPT if attr.has_default else ARG_POS
        else:
            kind = ARG_NAMED_OPT
        args.append(
            Argument(Var(attr.name, attr.type), attr.type, EllipsisExpr(), kind)
        )
    if init_overflow_attr:
        any_t = AnyType(TypeOfAny.explicit)
        args.append(Argument(Var("kwargs", any_t), any_t, None, ARG_STAR2))
    add_method_to_class(ctx.api, ctx.cls, "__init__", args=args, return_type=NoneType())


# ---------------------------------------------------------------------------
# Top-level methods
# ---------------------------------------------------------------------------


def _add_toplevel_methods(ctx: ClassDefContext, base_tvd: TypeVarType) -> None:
    api = ctx.api
    self_t = fill_typevars(ctx.cls.info)
    any_t = AnyType(TypeOfAny.explicit)

    tvd = _method_tvar(base_tvd, "update")
    _add(
        ctx,
        "update",
        [
            Argument(Var("_new_value", self_t), self_t, EllipsisExpr(), ARG_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
            Argument(Var("attrs", any_t), any_t, None, ARG_STAR2),
        ],
        tvd,
    )

    tvd = _method_tvar(base_tvd, "transform")
    transform_t = _callable_type(self_t, api)
    _add(
        ctx,
        "transform",
        [
            Argument(
                Var("_transform", transform_t), transform_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
            Argument(Var("attr_transforms", any_t), any_t, None, ARG_STAR2),
        ],
        tvd,
    )

    tvd = _method_tvar(base_tvd, "reset")
    _add(ctx, "reset", [_bool_arg("_inplace", api), _bool_arg("_if", api)], tvd)


# ---------------------------------------------------------------------------
# Scalar methods
# ---------------------------------------------------------------------------


def _add_scalar_methods(
    ctx: ClassDefContext, attr: SpecAttrInfo, base_tvd: TypeVarType
) -> None:
    api = ctx.api
    t = attr.type
    # If a _prepare_<attr> method exists the value is cast before type-checking,
    # so accept Any as the input.
    input_t: Type = AnyType(TypeOfAny.special_form) if attr.has_attr_preparer else t
    nested = _get_spec_class_info(t)
    nested_ready = nested is not None and "spec_class" in nested.metadata

    # with_<attr>
    name = f"with_{attr.name}"
    tvd = _method_tvar(base_tvd, name)
    args = [
        Argument(Var("_new_value", input_t), input_t, EllipsisExpr(), ARG_OPT),
        _bool_arg("_inplace", api),
        _bool_arg("_if", api),
    ]
    if nested_ready:
        args.extend(_nested_kwargs(nested, api))
    _add(ctx, name, args, tvd)

    # update_<attr>
    name = f"update_{attr.name}"
    tvd = _method_tvar(base_tvd, name)
    args = [
        Argument(Var("_new_value", input_t), input_t, EllipsisExpr(), ARG_OPT),
        _bool_arg("_inplace", api),
        _bool_arg("_if", api),
    ]
    if nested_ready:
        args.extend(_nested_kwargs(nested, api))
    _add(ctx, name, args, tvd)

    # transform_<attr>
    name = f"transform_{attr.name}"
    tvd = _method_tvar(base_tvd, name)
    transform_t = _callable_type(t, api)
    args = [
        Argument(Var("_transform", transform_t), transform_t, EllipsisExpr(), ARG_OPT),
        _bool_arg("_inplace", api),
        _bool_arg("_if", api),
    ]
    if nested_ready:
        args.extend(_nested_kwargs(nested, api, for_transform=True))
    _add(ctx, name, args, tvd)

    # reset_<attr>
    name = f"reset_{attr.name}"
    tvd = _method_tvar(base_tvd, name)
    _add(ctx, name, [_bool_arg("_inplace", api), _bool_arg("_if", api)], tvd)


# ---------------------------------------------------------------------------
# Collection item methods
# ---------------------------------------------------------------------------


def _add_collection_methods(
    ctx: ClassDefContext, attr: SpecAttrInfo, base_tvd: TypeVarType
) -> None:
    api = ctx.api
    item_name = attr.item_name
    if not item_name:
        return

    item_t: Type = attr.item_type or AnyType(TypeOfAny.unannotated)
    # If a _prepare_<item> method exists the item is cast before type-checking.
    input_item_t: Type = (
        AnyType(TypeOfAny.special_form) if attr.has_item_preparer else item_t
    )
    kind = attr.collection_kind
    int_t = api.named_type("builtins.int")
    bool_t = api.named_type("builtins.bool")
    any_t = AnyType(TypeOfAny.explicit)

    nested = _get_spec_class_info(item_t)
    nested_ready = nested is not None and "spec_class" in nested.metadata

    if kind == "list":
        val_or_idx: Type = UnionType([input_item_t, int_t])

        name = f"with_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        idx_t: Type = UnionType([int_t, any_t])
        args = [
            Argument(Var("_item", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT),
            Argument(Var("_index", idx_t), idx_t, EllipsisExpr(), ARG_NAMED_OPT),
            Argument(Var("_insert", bool_t), bool_t, EllipsisExpr(), ARG_NAMED_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        if nested_ready:
            args.extend(_nested_kwargs(nested, api))
        _add(ctx, name, args, tvd)

        name = f"update_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_value_or_index", val_or_idx), val_or_idx, None, ARG_POS),
            Argument(
                Var("_new_item", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT
            ),
            Argument(Var("_by_index", bool_t), bool_t, EllipsisExpr(), ARG_NAMED_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        if nested_ready:
            args.extend(_nested_kwargs(nested, api))
        _add(ctx, name, args, tvd)

        name = f"transform_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        transform_t = _callable_type(item_t, api)
        args = [
            Argument(Var("_value_or_index", val_or_idx), val_or_idx, None, ARG_POS),
            Argument(
                Var("_transform", transform_t), transform_t, EllipsisExpr(), ARG_OPT
            ),
            Argument(Var("_by_index", bool_t), bool_t, EllipsisExpr(), ARG_NAMED_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

        name = f"without_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_value_or_index", val_or_idx), val_or_idx, None, ARG_POS),
            Argument(Var("_by_index", bool_t), bool_t, EllipsisExpr(), ARG_NAMED_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

    elif kind == "dict":
        key_t: Type = attr.key_type or any_t

        name = f"with_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_key", key_t), key_t, None, ARG_POS),
            Argument(
                Var("_value", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        if nested_ready:
            args.extend(_nested_kwargs(nested, api))
        _add(ctx, name, args, tvd)

        name = f"update_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_key", key_t), key_t, None, ARG_POS),
            Argument(
                Var("_new_item", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        if nested_ready:
            args.extend(_nested_kwargs(nested, api))
        _add(ctx, name, args, tvd)

        name = f"transform_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        transform_t = _callable_type(item_t, api)
        args = [
            Argument(Var("_key", key_t), key_t, None, ARG_POS),
            Argument(
                Var("_transform", transform_t), transform_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

        name = f"without_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_key", key_t), key_t, None, ARG_POS),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

    elif kind == "set":
        name = f"with_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_item", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        if nested_ready:
            args.extend(_nested_kwargs(nested, api))
        _add(ctx, name, args, tvd)

        name = f"update_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_item", input_item_t), input_item_t, None, ARG_POS),
            Argument(
                Var("_new_item", input_item_t), input_item_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

        name = f"transform_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        transform_t = _callable_type(item_t, api)
        args = [
            Argument(Var("_item", input_item_t), input_item_t, None, ARG_POS),
            Argument(
                Var("_transform", transform_t), transform_t, EllipsisExpr(), ARG_OPT
            ),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)

        name = f"without_{item_name}"
        tvd = _method_tvar(base_tvd, name)
        args = [
            Argument(Var("_item", input_item_t), input_item_t, None, ARG_POS),
            _bool_arg("_inplace", api),
            _bool_arg("_if", api),
        ]
        _add(ctx, name, args, tvd)
