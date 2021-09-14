To simplify the process of building and mutating spec-class instances,
`spec_class` generates helper methods and attaches them to class. The number and
types of methods added depends on type annotations, but in every case mutations
performed by these methods are (by default) done on copies of the original
instance, and so can be used safely on instances that are shared between
multiple objects.

!!! note "A note on naming"
    Generated methods are named consistently according to their action on the
    spec-class. In particular:

    - `with` always means that a new value is being associated with
        the spec-class, replacing (scalar methods) or appending to (collection
        methods) existing values.
    - `update` always means that an existing object is being mutated, and that
        attributes not referenced are maintained as is.
    - `transform` always means that a function is going to be applied to an
        existing value, and that (like `update`) and attributes not referenced
        will be maintained as is.
    - `reset` always means that the attributes referenced will be reset to their
        default values.

The base class has three "toplevel" methods added:

  - `update`
  - `transform`
  - `reset`

which can be used to mutate the state of the spec-class as a whole.

All managed attributes have four "scalar" methods added:

  - `with_<attr>`
  - `update_<attr>`
  - `transform_<attr>`
  - `reset_<attr>`

These methods allow the replacement or mutation of attribute values, and are
called scalar because each attribute is treated as one entity by these methods
(as compared to methods that mutate elements of a collection, as below).

Attributes which have collection types (subclasses of `MutableSequence`,
`MutableMapping` or `MutableSet`) also have attract four more "collection"
methods:

  - `with_<attr_singular>`
  - `update_<attr_singular>`
  - `transform_<attr_singular>`
  - `without_<attr_singular>`

These methods act on individual elements within these collections.

By way of demonstration, here is a simple example of how these methods can be
used together:

```python
@spec_class
class ClassExaminationResults:
    teacher_name: str
    student_grades: Dict[str, float]

(
    ClassExaminationResults()
    .update(teacher_name='TBD')
    .with_teacher_name('Mr. Didactic')
    .with_student_grade('Jerry', 12.3)
    .with_student_grade('Jane', 14.1)
    .without_student_grade('Jerry')
    .transform_teacher_name(lambda name: f'{name} and Mrs. Elocution')
)
# ClassExaminationResults(
#   teacher_name='Mr. Didactic and Mrs. Elocution',
#   student_grades={
#       'Jane': 14.1
#   }
# )
```

For more information about how these methods work, please peruse the [Toplevel Methods](toplevel.md), [Scalar Methods](scalars.md) and
[Collection Methods](collections.md) documentation.
