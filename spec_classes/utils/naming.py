import inflect

INFLECT_ENGINE = inflect.engine()
INFLECT_CACHE = {}


def get_singular_form(attr_name):
    """
    Determine the singular form of an attribute name, for use in the naming
    of collection helper methods.
    """
    if attr_name not in INFLECT_CACHE:
        singular = INFLECT_ENGINE.singular_noun(attr_name)
        if not singular or singular == attr_name:
            singular = f"{attr_name}_item"
        INFLECT_CACHE[attr_name] = singular
    return INFLECT_CACHE[attr_name]
