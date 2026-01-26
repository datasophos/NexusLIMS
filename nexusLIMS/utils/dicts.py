"""Dictionary manipulation utilities for NexusLIMS."""

from typing import Any, Dict

from benedict import benedict


def get_nested_dict_value_by_path(nest_dict, path):
    """
    Get a nested dictionary value by path.

    Get the value from within a nested dictionary structure by traversing into
    the dictionary as deep as that path found and returning that value.

    Uses python-benedict for robust nested dictionary operations.

    Parameters
    ----------
    nest_dict : dict
        A dictionary of dictionaries that is to be queried
    path : tuple
        A tuple (or other iterable type) that specifies the subsequent keys
        needed to get to a a value within `nest_dict`

    Returns
    -------
    value : object or None
        The value at the path within the nested dictionary; if there's no
        value there, return None
    """
    # Disable keypath_separator to avoid conflicts with keys containing special chars
    return benedict(nest_dict, keypath_separator=None).get(list(path))


def set_nested_dict_value(nest_dict, path, value):
    """
    Set a nested dictionary value by path.

    Set a value within a nested dictionary structure by traversing into
    the dictionary as deep as that path found and changing it to `value`.

    Uses python-benedict for robust nested dictionary operations.

    Parameters
    ----------
    nest_dict : dict
        A dictionary of dictionaries that is to be queried
    path : tuple
        A tuple (or other iterable type) that specifies the subsequent keys
        needed to get to a a value within `nest_dict`
    value : object
        The value which will be given to the path in the nested dictionary

    Returns
    -------
    value : object
        The value at the path within the nested dictionary
    """
    # Disable keypath_separator to avoid conflicts with keys containing special chars
    b = benedict(nest_dict, keypath_separator=None)
    b[list(path)] = value  # Updates in-place (benedict is dict subclass)


def try_getting_dict_value(dict_, key):
    """
    Try to get a nested dictionary value.

    This method will try to get a value from a dictionary (potentially
    nested) and fail silently if the value is not found, returning None.

    Parameters
    ----------
    dict_ : dict
        The dictionary from which to get a value
    key : str or tuple
        The key to query, or if an iterable container type (tuple, list,
        etc.) is given, the path into a nested dictionary to follow

    Returns
    -------
    val : object or None
        The value of the dictionary specified by `key`. If the dictionary
        does not have a key, returns None without raising an error
    """
    try:
        if isinstance(key, str):
            return dict_[key]
        if hasattr(key, "__iter__"):
            return get_nested_dict_value_by_path(dict_, key)
    except (KeyError, TypeError):
        return None
    else:
        # we shouldn't reach this line, but always good to return a consistent
        # value just in case
        return None  # pragma: no cover


def sort_dict(item):
    """Recursively sort a dictionary by keys."""
    return {
        k: sort_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(item.items(), key=lambda i: i[0].lower())
    }


def remove_dtb_element(tree, path):
    """
    Remove an element from a DictionaryTreeBrowser by setting it to None.

    Helper method that sets a specific leaf of a DictionaryTreeBrowser to None.
    Use with :py:meth:`remove_dict_nones` to fully remove the desired DTB element after
    setting it to None (after converting DTB to dictionary).

    Parameters
    ----------
    tree : :py:class:`~hyperspy.misc.utils.DictionaryTreeBrowser`
        the ``DictionaryTreeBrowser`` object to remove the object from
    path : str
        period-delimited path to a DTB element

    Returns
    -------
    tree : :py:class:`~hyperspy.misc.utils.DictionaryTreeBrowser`
    """
    tree.set_item(path, None)

    return tree


def remove_dict_nones(dictionary: Dict[Any, Any]) -> Dict[Any, Any]:
    """
    Delete keys with a value of ``None`` in a dictionary, recursively.

    Taken from https://stackoverflow.com/a/4256027.

    Parameters
    ----------
    dictionary
        The dictionary, with keys that have None values removed

    Returns
    -------
    dict
        The same dictionary, but with "Nones" removed
    """
    for key, value in list(dictionary.items()):
        if value is None:
            del dictionary[key]
        elif isinstance(value, dict):
            remove_dict_nones(value)
    return dictionary
