from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import defaultdict
from inspect import Signature
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Type, Union

from spec_classes.methods import core as core_methods
from spec_classes.methods.scalar import SCALAR_METHODS

from .types import Attr, MISSING, spec_property
from .utils.method_builder import MethodBuilder


@dataclasses.dataclass
class SpecClassMetadata:
    @classmethod
    def for_class(cls, spec_cls):
        metadata = MISSING
        for klass in spec_cls.mro()[1:]:
            if klass.__dict__.get("__spec_class__", MISSING) is not MISSING:
                metadata = klass.__spec_class__
                break
        if metadata is MISSING:
            return cls(owner=spec_cls)

        attrs_inherited = {}

        for parent in reversed(spec_cls.__bases__):
            parent_metadata = getattr(parent, "__spec_class__", None)
            if parent_metadata:
                attrs_inherited.update(parent_metadata.attrs)

        return cls(
            owner=spec_cls,
            key=metadata.key,
            init_overflow_attr=metadata.init_overflow_attr,
            frozen=metadata.frozen,
            do_not_copy=False,  # We always reset this (but attributes inherited will not be copied unless overridden)
            attrs=attrs_inherited,
        )

    owner: Type
    key: Optional[str] = None
    init_overflow_attr: Optional[str] = None
    frozen: bool = False
    do_not_copy: bool = False
    attrs: Dict[str, Attr] = dataclasses.field(default_factory=dict)
    deferred_bootstrap: Optional[Callable] = None

    @spec_property(cache=True, overridable=False)
    def annotations(self):
        return {attr: spec.type for attr, spec in self.attrs.items()}

    @spec_property(cache=True, overridable=False)
    def invalidation_map(self):
        invalidation_map = defaultdict(set)
        for attr, attr_spec in self.attrs.items():
            for invalidator in attr_spec.invalidated_by or ():
                invalidation_map[invalidator].add(attr)
        return invalidation_map


@dataclasses.dataclass
class SpecClassMetadataPlaceholder:

    bootstrapper: Callable

    def __get__(self, instance, owner):
        self.bootstrapper()
        return owner.__spec_class__


class spec_class:
    """
    A class decorator that adds `with_<field>`, `transform_<field>` and
    `without_<field>` methods to a class in order to simplify the incremental
    building and mutating of specification objects. By default these methods
    return a new instance decorated class, with the appropriate field mutated.

    It can be used directly on a class, for example:
    >>> @spec_class
    >>> class MyClass:
    >>>     pass
    or can be passed arguments (see the constructor for argument details), for
    example:
    >>> @spec_class(attrs={'my_field'}, key='my_key_field')
    >>> class MyClass:
    >>>     pass

    For each attribute that `spec_cls` is told to manage (if not explicitly
    told, it will manage all attributes that have a type annotation), `spec_cls`
    will add a subset of the following methods (depending on the type of each
    attribute):

    - all types:
        - `with_<attribute>(...)`: Update the attribute value.
        - `transform_<attribute>(...)`: Update the attribute value by calling
            a passed function on the existing value.
    - collection types (sequence, mapping, set):
        - `with_<singular_noun_for_attribute>(...)`: Add/modify a member of the
            collection.
        - `transform_<singular_noun_for_attribute>(...)`: Update a member of a
            collection by transforming an existing member.
        - `without_<singular_noun_for_attribute>(...)`: Remove a member of a
            collection.

    If the attribute type (or type stored by a collection) is also decorated by
    `spec_cls`, then additional arguments will be exposed in the methods to
    directly modify nested structure. For example, if an attribute `foos` has
    type `List[Foo]`, and `Foo` is a class decorated by `spec_class`, then the
    method `with_foo` method will have signature:
    `with_foo(<spec>, *, _index=MISSING, _insert=False, <all attributes of foo>=MISSING)`

    If the attribute type (or type stored by a collection) is annoted by
    `spec_cls` and a key attribute has been specified, then in collections the
    key of the element can additionally be used to directly look up elements.

    For more information, you can look up the generated docstrings on any of
    these methods.

    Notes:
        * `spec_cls` "upgrades" all classes to be dataclasses. As always,
            if you have already implemented __init__, it won't be overridden.
        * Any attribute passed to `spec_cls` (or all attributes if none are
            explicitly passed to the constructor) should be both gettable and
            settable (i.e., no read-only properties). Where this is not
            satisfied you will need to implement your own `with_*`, `transform_*`
            and `without_*` methods (`spec_cls` will never clobber existing
            methods).
        * For any attribute managed by `spec_cls`, it should be possible to
            construct an instance of the decorated class using
            `cls(**attributes)`. This is used whenever a decorated class refers
            to other types decorated by `spec_cls`.

    Examples:
    (1) Simple example
        @spec_class
        class Foo:
            key: str
            value: int

        @SpecClass(foo=Foo)
        class Bar:
            foo: Foo = Foo('k', 1)

        Bar().with_foo(Foo('k2', 2)).foo  # Foo('k2', 2)
        Bar().with_foo(value=3).foo  # Foo('k', 3)
        Bar().transform_foo(lambda x: x.with_value(10)).foo  # Foo('k', 10)

    (2) A class demonstrating all functionalities. You can experiment with this
        class and/or look up its docstrings in order to understand how
        everything works.

        @spec_class
        class UnkeyedSpec:
            nested_scalar: int = 1
            nested_scalar2: str = 'original value'

        @spec_class(key='key')
        class KeyedSpec:
            key: str = 'key'
            nested_scalar: int = 1
            nested_scalar2: str = 'original value'


        @spec_class(key='key')
        class Spec:
            key: str = None
            scalar: int = None
            list_values: List[int] = None
            dict_values: Dict[str, int] = None
            set_values: Set[str] = None
            spec: UnkeyedSpec = None
            spec_list_items: List[UnkeyedSpec] = None
            spec_dict_items: Dict[str, UnkeyedSpec] = None
            keyed_spec_list_items: List[KeyedSpec] = None
            keyed_spec_dict_items: Dict[str, KeyedSpec] = None
            recursive: Spec = None

    For more complete examples, refer to the method docstrings, or to the unit
    tests which thoroughly test example (2) above.
    """

    def __new__(cls, *args, **kwargs):
        """
        Handle un-annotated case where the class to be decorated is passed
        directly to the `spec_class` constructor, for example:
        >>> @spec_class
        >>> class MyClass:
        >>>     pass
        """
        if len(args) == 1 and isinstance(args[0], type):
            return spec_class()(args[0])
        return super().__new__(cls)

    def __init__(
        self,
        key: str = MISSING,
        do_not_copy: Union[bool, Iterable[str]] = False,
        frozen: bool = False,
        init: bool = True,
        repr: bool = True,  # pylint: disable=redefined-builtin
        eq: bool = True,
        bootstrap: bool = False,
        attrs: Iterable[str] = MISSING,
        attrs_typed: Mapping[str, Type] = MISSING,
        attrs_skip: Iterable[str] = MISSING,
        init_overflow_attr: Optional[str] = MISSING,
    ):
        """
        Args:
            key: The name of the attribute which can be used to uniquely
                identify a particular specification. If not specified, it will
                be inherited from the parent class. To explicitly disable the
                key functionality, pass `None`.
            do_not_copy: Whether to avoid copying spec-classes (or attributes
                thereof) during mutations. If `True`, then all mutations will be
                done inplace. If `False`, then complete deep-copies will be
                performed before any mutation using the helper methods. If this is
                an iterable of strings, the strings should correspond to the
                attributes which should be passed through to the copy of class
                instances without being copied. This is valuable when copying is
                memory intensive, and when mutations *only* occur via the helper
                methods generated by `spec_class`. If not specified, and not
                inherited from a subclass, this will default to `False`.
            frozen: Whether to disallow direct modifications of attributes. If
                not specified and not inherited from parent class, this will
                default to `False`.
            init: Whether to add an `__init__` method if one does not already
                exist.
            repr: Whether to add a `__repr__` method if one does not already
                exist.
            eq: Whether to add an `__eq__` method if one does not already
                exist.
            bootstrap: Whether to bootstrap spec-class immediately (True), or
                wait until first instantiation (False). Default is to defer
                bootstrapping to avoid cyclic annotation imports (False). This
                may be suboptimal if subclasses are wanting to override the
                generated methods.
            attrs: The attrs for which this `spec_cls` should add helper
                methods.
            attrs_typed: Additional attributes for which this `spec_cls`
                should add helper methods, with the type of the attr taken to be
                as specified, overriding (if present) any other type annotations
                for that attribute (e.g. List[int], Dict[str, int], Set[int], etc).
            attrs_skip: Attributes which should not be considered by this `spec_cls`.
            init_overflow_attr: If specified, any extra keyword arguments passed
                to the constructor will be collected as a dictionary and set as
                an attribute of this name.

        Notes:
            - If `attrs` and `attrs_typed` are not specified, then spec-classes
              will manage all annotated attributes. To treat these fields as
              incremental on top of all attributes, pass a (potentially empty)
              iterable to `attrs_skip`.
        """
        self.inherit_annotations = (
            not (attrs or attrs_typed) or attrs_skip is not MISSING
        )
        self.key = key
        self.attrs = {
            **{attr: Any for attr in (attrs or set())},
            **(attrs_typed or {}),
            **({init_overflow_attr: Dict[str, Any]} if init_overflow_attr else {}),
        }
        self.attrs_skip = set(attrs_skip or set())
        self.spec_cls_methods = {
            "__init__": init,
            "__eq__": eq,
            "__repr__": repr,
            "__getattr__": True,
            "__setattr__": True,
            "__delattr__": True,
            "__deepcopy__": True,
        }
        self.do_not_copy = do_not_copy
        self.frozen = frozen
        self.init_overflow_attr = init_overflow_attr
        self.bootstrap_immediately = bootstrap

        # Check for private attr specification, and if found, raise!
        private_attrs = [attr for attr in self.attrs if attr.startswith("_")]
        if private_attrs:
            raise ValueError(
                f"`spec_cls` cannot be used to generate helper methods for private attributes (got: {private_attrs})."
            )

    def __call__(self, spec_cls: type) -> type:
        """
        Mark the nominated `spec_cls` as a spec-class, and wrap the `__new__`
        magic method with hooks to lazily bootstrap spec-class utility methods
        upon first instantiation unless bootstrapping immediately.

        Args:
            spec_cls: The decorated class.

        Returns:
            `spec_cls`, with the necessary hooks to generate methods on first
                instantiation (or immediately if `self.bootstrap_immediately`).

        Notes:
            We defer method generation by default until first instantiation to
            mitigate cyclic import errors when type annotations are
            bi-directional between two classes.
        """
        if self.bootstrap_immediately:
            self.bootstrap(spec_cls)
        else:
            spec_cls.__spec_class__ = SpecClassMetadataPlaceholder(
                lambda: self.bootstrap(spec_cls)
            )
            orig_new = spec_cls.__new__ if "__new__" in spec_cls.__dict__ else None

            def __new__(cls, *args, **kwargs):
                # Bootstrap spec class (looking at the __spec_class__ does this automatically)
                if not isinstance(cls.__spec_class__, SpecClassMetadata):
                    raise RuntimeError(
                        "Something has gone wrong! Please report this."
                    )  # pragma: no cover; We should never see this.

                # Chain out to original __new__ implementation if defined on this
                # spec class, and remove this __new__ wrapper.
                if orig_new:
                    spec_cls.__new__ = orig_new
                elif super(spec_cls, cls).__new__ is object.__new__:

                    def __new__(cls, *args, **kwargs):
                        return object.__new__(cls)

                    spec_cls.__new__ = __new__
                else:
                    del spec_cls.__new__

                return spec_cls.__new__(cls, *args, **kwargs)

            spec_cls.__new__ = __new__
        return spec_cls

    def bootstrap(self, spec_cls: type):
        """
        Bootstrap `spec_cls` by assembling the `__spec_class__` metadata,
        reconciling attribute annotations, and adding class/helper methods.

        Args:
            spec_cls: The decorated class.
        """
        # Bootstrap any parents of this class first (we can abort without
        # recursing since each parent will bootstrap its own parents, and so
        # on).
        for parent in spec_cls.__bases__:
            hasattr(
                parent, "__spec_class__"
            )  # Just looking at this will ensure we are bootstrapped

        # Begin assembling all metadata, inheriting any base class configuration
        # and the overriding where necesary.
        metadata = SpecClassMetadata.for_class(spec_cls)
        if self.key is not MISSING:
            metadata.key = self.key
        if self.frozen is not MISSING:
            metadata.frozen = self.frozen
        if self.init_overflow_attr is not MISSING:
            metadata.init_overflow_attr = self.init_overflow_attr
        if self.do_not_copy is True:
            metadata.do_not_copy = True

        # Identify which attributes should be managed by spec-classes.
        # We explicitly preserve ordering of attributes; starting with those
        # defined as annotations on the class, and then those manually annotated.
        managed_attrs = []
        if self.inherit_annotations:
            managed_attrs.extend(
                attr
                for attr in getattr(spec_cls, "__annotations__", {})
                if (not attr.startswith("_") and attr not in self.attrs_skip)
            )
        managed_attrs.extend(self.attrs)

        # Generate namespace of annotations (in addition to local class context)
        annotation_namespace = {spec_cls.__name__: spec_cls}
        if hasattr(spec_cls, "ANNOTATION_TYPES"):
            spec_annotation_types = spec_cls.ANNOTATION_TYPES
            if hasattr(spec_annotation_types, "__call__"):
                spec_annotation_types = spec_cls.ANNOTATION_TYPES()
            if isinstance(spec_annotation_types, Mapping):
                annotation_namespace.update(spec_annotation_types)

        # Generate type-map for all managed attributes (including local overrides)
        # We explicitly add the `key` attribute even if it is not a managed
        # attribute, so that we can look up the type as necessary later.
        attr_types_raw = typing.get_type_hints(spec_cls, localns=annotation_namespace)
        attr_types = {
            attr: (
                self.attrs[attr]
                if self.attrs.get(attr, Any) is not Any
                else attr_types_raw.get(attr, Any)
            )
            for attr in [self.key, *managed_attrs]
            if attr not in {None, MISSING}
        }

        # Update inherited `Attr` specifications. If attribute default is
        # overridden on class, or the attribute's `do_not_copy` attribute needs
        # to be updated, create a new `Attr` instance that maintains the
        # existing `owner` attribute.
        for attr, attr_spec in metadata.attrs.items():
            if attr in attr_types:
                continue
            do_not_copy = (
                self.do_not_copy
                if isinstance(self.do_not_copy, bool)
                else attr in self.do_not_copy
            )
            if attr in spec_cls.__dict__ or do_not_copy is not attr_spec.do_not_copy:
                metadata.attrs[attr] = self.build_attr_spec(
                    spec_cls,
                    attr,
                    attr_spec.type,
                    do_not_copy=do_not_copy,
                    owner=attr_spec.owner,
                )

        # Generate new `Attr` instances for each new (or overridden) attribute
        # (or lift `Attr` instances from class definition)
        metadata.attrs.update(
            {
                attr: self.build_attr_spec(
                    spec_cls,
                    attr,
                    attr_types[attr],
                    do_not_copy=self.do_not_copy
                    if isinstance(self.do_not_copy, bool)
                    else attr in self.do_not_copy,
                )
                for attr in managed_attrs
            }
        )

        # Update __annotations__ attribute to be consistent with spec_class
        # typings (unless already defined on the class contrarily)
        if not hasattr(spec_cls, "__annotations__"):
            spec_cls.__annotations__ = {}
        for attr, attr_spec in metadata.attrs.items():
            if attr_spec.owner is spec_cls and attr not in spec_cls.__annotations__:
                spec_cls.__annotations__[attr] = attr_spec.type

        # Add any extra invalidation mappings from non-attributes
        for name, member in spec_cls.__dict__.items():
            if name not in metadata.attrs and hasattr(
                member, "__spec_class_invalidated_by__"
            ):
                for invalidator in member.__spec_class_invalidated_by__:
                    metadata.invalidation_map[invalidator].add(name)

        # Finalize metadata and remove bootstrapper from class.
        spec_cls.__spec_class__ = metadata

        # Register class-level methods and validate constructor/etc.
        methods = self.get_methods_for_spec_class(
            spec_cls, self.spec_cls_methods
        ).copy()
        for attr_spec in metadata.attrs.values():
            if attr_spec.owner is not spec_cls:
                continue
            for helper_method in attr_spec.helper_methods or ():
                method = helper_method(attr_spec, spec_cls=spec_cls)
                methods[method.method_name] = method
        self.register_methods(spec_cls, methods)

        # Ensure resulting spec class is valid.
        self._validate_spec_cls(spec_cls)

    def build_attr_spec(
        self, spec_cls, attr, attr_type, *, do_not_copy=False, owner=None
    ):
        owner = owner or spec_cls
        if hasattr(spec_cls, attr):
            attr_value = getattr(spec_cls, attr, MISSING)
            if isinstance(attr_value, (Attr, dataclasses.Field)):
                setattr(
                    spec_cls,
                    attr,
                    attr_value.default_factory()
                    if attr_value.default_factory
                    else attr_value.default,
                )
                owner = spec_cls  # If an Attr was declared, this spec-class should own the attribute.
            elif inspect.isfunction(attr_value) or inspect.isdatadescriptor(attr_value):
                attr_value = (
                    MISSING  # Methods will already be bound to instance from class
                )
            attr_spec = Attr.from_attr_value(
                attr, attr_value, type=attr_type, do_not_copy=do_not_copy, owner=owner
            )
        else:
            attr_spec = Attr.from_attr_value(
                attr, MISSING, type=attr_type, do_not_copy=do_not_copy, owner=owner
            )

        # Add helper methods
        attr_spec.helper_methods = self.get_methods_for_attribute(attr_spec)

        # Check for invalidated_by information
        if not attr_spec.invalidated_by and hasattr(
            attr_spec.default, "__spec_class_invalidated_by__"
        ):
            attr_spec.invalidated_by = attr_spec.default.__spec_class_invalidated_by__

        # Check for preparer
        preparer = getattr(spec_cls, f"_prepare_{attr_spec.name}", MISSING)
        if preparer:
            attr_spec.prepare = preparer

        # Check for item_preparer
        if attr_spec.is_collection:
            item_preparer = getattr(
                spec_cls, f"_prepare_{attr_spec.item_name}", MISSING
            )
            if item_preparer:
                attr_spec.prepare_item = item_preparer

        return attr_spec

    @classmethod
    def _validate_spec_cls(cls, spec_cls):
        spec_annotations = spec_cls.__spec_class__.attrs

        # Check that constructor is present for all managed keys.
        init_sig = Signature.from_callable(spec_cls.__init__)
        missing_args = set(spec_annotations).difference(init_sig.parameters)

        if missing_args:
            raise ValueError(
                f"`{spec_cls.__name__}.__init__()` is missing required arguments to populate attributes: {missing_args}."
            )

    @classmethod
    def get_methods_for_spec_class(
        cls, spec_cls: type, methods_filter: Dict[str, bool]
    ) -> Dict[str, Callable]:
        """
        Generate any required `__init__`, `__repr__` and `__eq__` methods. Will
        only be added if these methods do not already exist on the class.
        """
        __init__ = core_methods.InitMethod(spec_cls).method
        __repr__ = core_methods.ReprMethod(spec_cls).method
        __eq__ = core_methods.EqMethod(spec_cls).method

        __getattr__ = core_methods.GetAttrMethod(spec_cls).method
        __setattr__ = core_methods.SetAttrMethod(spec_cls).method
        __delattr__ = core_methods.DelAttrMethod(spec_cls).method
        __deepcopy__ = core_methods.DeepCopyMethod(spec_cls).method

        methods = {
            # Potentially overwritable
            "__init__": __init__,
            "__repr__": __repr__,
            "__eq__": __eq__,
            # Backups to allow reuse by methods
            "__spec_class_init__": __init__,
            "__spec_class_repr__": __repr__,
            "__spec_class_eq__": __eq__,
            # Mandatory methods
            "__getattr__": __getattr__,
            "__setattr__": __setattr__,
            "__delattr__": __delattr__,
            "__deepcopy__": __deepcopy__,
        }
        return {
            name: method
            for name, method in methods.items()
            if name.startswith("__spec_class") or methods_filter.get(name, False)
        }

    def get_methods_for_attribute(self, attr_spec: Attr) -> Dict[str, Callable]:
        """
        Return the methods that should be added to `spec_cls` for the given
        `attr_name` and `attr_type`.

        Args:
            spec_cls: The decorated class for which methods should be generated.
            attr_name: The name of the attribute for which methods should be
                generated.
            attr_type: The type of the attribute (used to determine which
                methods are generated).

        Returns:
            A dictionary of methods (keyed by method name).
        """
        methods = [*SCALAR_METHODS]
        if attr_spec.is_collection:
            methods.extend(attr_spec.collection_mutator_type.HELPER_METHODS)
        return methods

    @classmethod
    def register_methods(cls, spec_cls: type, methods: Dict[str, Callable]):
        """
        Register nominated methods onto `spec_cls`. Methods will not be added if
        they already exist on the class.

        Args:
            spec_cls: The decorated class.
            methods: A dictionary of methods keyed by name.
        """
        for name, method in methods.items():
            cls.register_method(spec_cls, name, method)

    @staticmethod
    def register_method(spec_cls: type, name: str, method: Callable):
        """
        Add a method to the decorated class, and name it `name`. Do nothing if a
        method by this name already exists.

        Args:
            spec_cls: Decorated class.
            name: The name of the method to add.
            method: The method to add.
        """
        if name in spec_cls.__dict__ and not name.startswith("__spec_class"):
            return
        if isinstance(method, MethodBuilder):
            method = method.build()
        if hasattr(method, "__set_name__"):
            method.__set_name__(spec_cls, name)
        setattr(spec_cls, name, method)
