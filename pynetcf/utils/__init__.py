def filter_object(objects, **kwargs):
    """Filter objects based on kwargs"""
    if kwargs:
        for obj in objects:
            query = []
            try:
                for key, value in kwargs.items():
                    try:
                        attr_value = value(getattr(obj, key))
                        query.append(attr_value)
                    except TypeError:
                        attr_value = getattr(obj, key)
                        query.append(value == attr_value)
                if all(query):
                    yield obj
            except AttributeError:
                pass


def get_object(objects, **kwargs):
    """Return a single object based on kwargs, if kwargs is not provided it
    return all the objects"""
    if not kwargs:
        return objects

    found = True
    try:
        filtered = filter_object(objects, **kwargs)
        return next(filtered)
    except StopIteration:
        found = False

    if not found:
        _kwargs = " ".join(["{}={}".format(k, v) for k, v in kwargs.items()])
        raise ValueError("No object found with values {}".format(_kwargs))
