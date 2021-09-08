Let's start simple. Here's a basic spec-class:

```python
from spec_classes import spec_class

@spec_class
class Door:
    width: float
    height: float
    color: str
```

We can instantiate it:
```python
Door()
# Door(width=MISSING, height=MISSING, color=MISSING)

Door(color='red')
# Door(width=MISSING, height=MISSING, color='red')
```

Mutate it (copy-on-write):
```python
d = Door()
(
    d
    .with_width(5.3)
    .with_height(10.4)
    .with_color('red')
)
# Door(width=5.3, height=10.4, color='red')
d
# Door(width=MISSING, height=MISSING, color=MISSING)
d.with_width(5.3, _inplace=True)
d
# Door(width=5.3, height=MISSING, color=MISSING)
```

Transform it:
```python
(
    Door(width=2.)
    .transform_width(lambda width: 2 * width)
)
# Door(width=4.0, height=MISSING, color=MISSING)
```

Reset it:
```python
(
    Door(width=2.)
    .reset_width()
)
# Door(width=MISSING, height=MISSING, color=MISSING)
```

But... we can't do the wrong thing:
```python

Door(width='invalid')
# TypeError: Attempt to set `Door.width` with an invalid type [got `'invalid'`; expecting `float`].
```
