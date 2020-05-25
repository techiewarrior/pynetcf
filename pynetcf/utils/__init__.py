def filter_objects(objects, **kwargs):
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


def get_objects(objects, **kwargs):
    """Return a single object based on kwargs, if kwargs is not provided it
    return all the objects"""
    # found = True
    try:
        filtered = filter_objects(objects, **kwargs)
        return next(filtered)
    except StopIteration:
        return None

    # if not found:
    #     _kwargs = ", ".join(["{}={}".format(k, v) for k, v in kwargs.items()])
    #     raise ValueError("No object found with keyword arguments {}".format(_kwargs))


class AttrDict(dict):
    def __init__(self, mapping):
        super().__init__(mapping)

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value
