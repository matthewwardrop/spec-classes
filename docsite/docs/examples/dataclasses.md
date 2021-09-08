Spec-classes are interoperable with dataclasses, and data-class definitions can
be easily upgraded into spec-class ones.

Here's a dataclass definition:

```python
from dataclasses import dataclass, field

@dataclass
class Farm:
    owner: str = "Harry"
    animals: List[str] = field(default_factory=list)

f = Farm()
f # Farm(owner='Harry', animals=[])

# We're not protected here from any abuse of types at run-time.
f.owner = 10
f # Farm(owner=10, animals=[])
```

Let's upgrade that to a spec-class the easiest possible way:
```python
from spec_classes import spec_class
from dataclasses import field

@spec_class
class Farm:
    owner: str = "Harry"
    animals: List[str] = field(default_factory=list)

f = Farm()
f # Farm(owner='Harry', animals=[])

# Looks the same! But now we're enforcing types.

f.owner = 10
# TypeError: Attempt to set `Farm.owner` with an invalid type [got `10`; expecting `str`].
```

Spec-classes also has its own equivalent of `field` that provides some
additional spec-classes specific configuration (see [`Attr`](../usage/special_types.md#Attr)),
so the above is equivalent to:
```python
from spec_classes import spec_class, Attr

@spec_class
class Farm:
    owner: str = "Harry"
    animals: List[str] = Attr(default_factory=list)
```

Spec-classes is also special in that it allows mutable types to be set as the
defaults on base class definition (they are safely copied at instantiation time
in the generated constructor). Thus, you can actually just write:
```python
from spec_classes import spec_class

@spec_class
class Farm:
    owner: str = "Harry"
    animals: List[str] = []
```

Boom! Done.