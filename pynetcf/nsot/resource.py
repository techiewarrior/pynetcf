from pynetcf.nsot.client import NSoTClient, nsot_request
from pynetcf.utils import get_objects, filter_objects, AttrDict
from pynetcf.utils.logger import get_logger

logger = get_logger(__name__)


class EndpointDescriptor:
    def __init__(self, resource_name):
        self._resource_name = resource_name
        self._endpoints = {}

    def __get__(self, obj, type=None):
        try:
            return self._endpoints[obj.site_id]
        except KeyError:
            endpoint = getattr(
                NSoTClient.resource.sites(obj.site_id), self._resource_name
            )
            self._endpoints[obj.site_id] = endpoint
            return endpoint

    def __set__(self, obj, value):
        raise AttributeError("can't set attribute")

    def __delete__(self, obj):
        raise AttributeError("can't delete attribute")


class NSoTObjectDescriptor:
    "Implement NSoT object Descriptor"

    def __init__(self, name, read_only=True, default_value=None):
        self._name = name
        self._read_only = read_only
        self._default_value = default_value

        self.__doc__ = f"Return the {name} of NSoT resource object"

    def __get__(self, obj, type=None):
        if not self._read_only:
            try:
                return obj._payload[self._name]
            except KeyError:
                return obj._nsot_obj.get(self._name, self._default_value)

        try:
            return obj._attrs[self._name]
        except KeyError:
            return obj._nsot_obj.get(self._name)

    def __set__(self, obj, value):
        if self._read_only:
            raise AttributeError("can't set attribute '%s'" % self._name)

        extra_set_method = getattr(obj, f"_set_{self._name}", None)
        if extra_set_method:
            extra_set_method(value)
        else:
            obj._payload[self._name] = value

    def __delete__(self, obj):
        if self._read_only:
            raise AttributeError("can't delete attribute '%s'" % self._name)

        extra_set_method = getattr(obj, f"_delete_{self._name}", None)
        if extra_set_method:
            obj._extra_method()
        else:
            obj._payload[self._name] = self._default


class ResourceAttributes:

    default = ["site_id", "site_name", ("attributes", True, {})]

    devices = ["id", "hostname"]
    interfaces = [
        "id",
        "device",
        "name",
        "networks",
        "parent",
        ("mac_address", False),
        ("addresses", False, []),
        ("description", False, ""),
        ("speed", False, 1000),
        ("type", False, 6),
    ]
    networks = [
        "id",
        "cidr",
        "network_address",
        "prefix_length",
        "parent",
        "is_ip",
        "ip_version",
        ("state", False),
    ]

    @classmethod
    def get(cls, resource_name):
        attrs = getattr(cls, resource_name)
        attrs.extend(cls.default)
        return attrs


class ResourceManager:
    """Holds resource class objects and a helper query function"""

    def __init__(self, model=None, nsot_objects=None, **kwargs):
        self._objects = {}
        self._model = model
        self._nsot_objects = nsot_objects

        for k, v in kwargs.items():
            setattr(self, f"_{k}", v)

    def create(self, *args, **kwargs):
        obj = self._model(*args, **kwargs)
        obj.update_post()

    def post_update(self):
        for obj in self._objects.values():
            obj.update_post()

    def filter(self, **kwargs):
        if not kwargs:
            return []
        yield from filter_objects(iter(self._objects.values()), **kwargs)
        # yield from filter(lambda x: all(f(x) for f in args), x)

    def get(self, **kwargs):
        objects = iter(self._objects.values())
        if not kwargs:
            return list(objects)
        return get_objects(objects, **kwargs)


class Resource:
    """Base class for NSoT resource
    This is base on the flyweight design pattern that overide __new__ to return
    the resource object that is already exists.

    https://python-patterns.guide/gang-of-four/flyweight/

    Resource specific argurments is defined in class model _args variable
    """

    def __init_subclass__(cls):
        """Customise subclass creation and create class instance from the
        existing NSoT resource objects"""

        model = cls.__name__
        name = model.lower() + "s"
        resource = getattr(NSoTClient.resource, name)
        nsot_objects = resource.get()

        for attr in ResourceAttributes.get(name):
            if isinstance(attr, tuple):
                setattr(cls, attr[0], NSoTObjectDescriptor(*attr))
            else:
                setattr(cls, attr, NSoTObjectDescriptor(attr))

        setattr(cls, "_resource", EndpointDescriptor(name))

        if getattr(cls, "manager", None) is None:
            cls.manager = ResourceManager()

        cls.manager._model = cls
        cls.manager._nsot_objects = {obj["id"]: obj for obj in nsot_objects}

        if getattr(cls, "_sort_objects_by", None):
            nsot_objects = sorted(
                nsot_objects, key=lambda x: x[cls._sort_objects_by]
            )

        for nsot_obj in nsot_objects:
            cls(*[nsot_obj.get(k) for k in cls._args], nsot_obj=nsot_obj)

    def __new__(cls, *args, **kwargs):

        # specific arguments is defined in class _args attribute
        # kwargs is the resource attributes
        required_args = cls._args[:-1]

        if len(args) < len(required_args):
            raise ValueError(
                f"object '{cls.__name__}' missing reqiured argurments {required_args}"
            )

        new_attrs = AttrDict({k: v for k, v in zip(cls._args, args)})

        nsot_obj = kwargs.pop("nsot_obj", {})

        # pass the argument back class to manipulate specific arguments
        if getattr(cls, "_check_args", None):
            cls._check_args(new_attrs)

        site_id = new_attrs.get("site_id")

        # check if default_site variable is defined in pynsotrc else raises ValueError
        if site_id is None:
            site_id, site_name = NSoTClient.default_site()
            new_attrs.site_id = site_id
        else:
            site_name = NSoTClient.get_sitename(site_id)
        new_attrs.site_name = site_name

        # the resource key use to look up the existing object
        key = tuple([new_attrs.get(a) for a in cls._args])
        object = cls.manager._objects.get(key)

        if object:
            logger.info(f"{key} returning cache object")
            return object
        else:
            # create new object
            self = super().__new__(cls)

            if nsot_obj:
                self._payload = {}
            else:
                payload = {k: v for k, v in zip(cls._args, key)}
                self._payload = {**payload, "attributes": kwargs}

            self._attrs = new_attrs
            self._key = key
            self._nsot_obj = nsot_obj

            cls.manager._objects[key] = self

            # pass the object back to class for spefic object attributes
            if getattr(cls, "_pre_init", None):
                cls._pre_init(self)

            return self

    def __repr__(self):
        keys = ", ".join([str(k) for k in self._key])
        return f"<{self.__class__.__name__}: {keys}>"

    def __str__(self):
        natural_name = ":".join([str(self._attrs.get(k)) for k in self._args[:-1]])
        return f"{natural_name}"

    def __getattr__(self, key):

        found = True
        try:
            return self._attrs[key]
        except KeyError:
            found = False

        if not found:
            raise AttributeError(f"'Network' object has no attribute '{key}'")

    def __eq__(self, other):
        try:
            return self._key == other._key
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(self._key)

    def exists(self):
        "Return `True` if resource exists in NSoT server"
        return bool(self._nsot_obj)

    def add_attributes(self, **kwargs):
        """Add attributes to the existing attributes
        The attribute name must be first exists in NSoT server otherwise raises
        Exception
        :param kwargs (str/str|list): key/value of the attribute
        """
        try:
            self._payload["attributes"].update(kwargs)
        except KeyError:
            self._payload["attributes"] = {
                **self._nsot_obj.get("attributes", {}),
                **kwargs,
            }

    def remove_attributes(self, *args):
        """
        Remove attributes to the current attributes
        :param args (str): name of the attribute
        """
        attributes = self._payload.get("attributes")
        if attributes:
            for name in args:
                try:
                    del attributes[name]
                except KeyError:
                    pass
        else:
            self._payload["attributes"] = {
                k: v
                for k, v in self._nsot_obj.get("attributes", {}).items()
                if k not in args
            }

    @nsot_request
    def update_post(self):
        """POST or PATCH resource in NSoT server"""
        obj = self._nsot_obj

        payload = {**obj, **self._payload}
        if obj:
            if payload != obj:
                self._nsot_obj = self._resource(obj["id"]).patch(payload)
                logger.info(f"{self._key} PATCH")
        else:
            self._nsot_obj = self._resource.post(payload)
            logger.info(f"{self._key} POST")

        return self._nsot_obj

    @nsot_request
    def delete(self):
        """DELETE resource in NSoT server"""
        _id = self._nsot_obj.get("id")
        if _id:
            self._resource(_id).delete()
            self._nsot_obj = {}
            self._payload = {
                **{k: v for k, v in zip(self._key, self._args[:-1])},
                "attributes": {},
            }
            del self.__class__.manager._objects[self._key]
            logger.info(f"{self._key} DELETE")
            return True
        else:
            return True

    def get(self):
        "Return the NsoT object"
        return self._nsot_obj
