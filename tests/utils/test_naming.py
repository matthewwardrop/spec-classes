from spec_classes.utils.naming import get_singular_form


def test_singularisation():
    assert get_singular_form("values") == "value"
    assert get_singular_form("classes") == "class"
    assert get_singular_form("collection") == "collection_item"
