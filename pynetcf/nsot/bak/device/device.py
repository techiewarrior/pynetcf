from pynetcf.utils.logger import get_logger
from ..client import NSoTClient
from ..resource import NSoTResource

logger = get_logger(__name__)

RESOURCE_NAME = "devices"


class Device(NSoTResource):

    _nsot_objects = {}
    _objects = {}

    for obj in NSoTClient.resource.devices.get():
        site_name = NSoTClient.get_sitename(obj["site_id"])
        key = "{}.{}".format(obj["hostname"], site_name)
        _nsot_objects[key] = obj

    def __init__(self, hostname, site_name=None, **kwargs):
        """
        Constructor

        The value from 'nsot_object['hostname']' is use as a 'hostname' when is given
        else the 'hostname' via param is use. Raises TypeError if both 'nsot_object'
        and 'hostname' is None.

        :param hostname: the hostname of the device in str format
        :param resource_obj: the NSoT device object which a return dict from
            GET, POST, PATCH. If provided, this will assume that the device is
            somehow exists in NSoT server
        :param kwargs: key/value pair of NSoT attributes of the device resource,
            key must be a str and value of str or list depend on the attributes
            'multi' value. Key as the name of the attribute must created beforehand.
        """
        if site_name is None:
            site_id, site_name = NSoTClient.default_site()

        self._hostname = hostname

        if self._objects.get(str(self)):
            raise TypeError(
                "{} is already exists use 'get()' classmethod to "
                "access the object".format(self)
            )

        self._site_id = site_id
        self._site_name = site_name

        nsot_object = self._nsot_objects.get(str(self))
        super(Device, self).__init__(nsot_object=nsot_object)

        if nsot_object is None:
            self.payload = {"hostname": hostname, "attributes": kwargs}

        self._interfaces = {}

        self._objects[str(self)] = self

    @classmethod
    def get(cls, **kwargs):
        # if site_name is None:
        #     site_name = NSoTClient.default_site()[1]
        result = []
        for obj in cls._objects.values():
            query = []
            try:
                for k, v in kwargs.items():
                    query.append(getattr(obj, k) == v)
                if all(query):
                    result.append(obj)
            except AttributeError:
                pass

        if len(result) > 1:
            raise ValueError("Result must be equal to one")
        try:
            return result[0]
        except IndexError:
            return None

        # key = "{}.{}".format(hostname, site_name)
        # return cls._objects.get(key)

    @classmethod
    def get_all(cls):
        return list(cls._objects.values())

    @classmethod
    def delete(cls, resource_id):
        cls._

    @property
    def hostname(self):
        """The hostname of the device"""
        return self._hostname

    @property
    def interfaces(self):
        """The interfaces belong to this device"""
        return list(self._interfaces.values())

    def key(self):
        return self._hostname, self.site_name

    #
    # def __repr__(self):
    #     return "Device({}.{})".format(self._hostname, self.resource.site_name)
    #
    # def __str__(self):
    #     return "{}.{}".format(self._hostname, self.resource.site_name)
    #
    # def __getattr__(self, key):
    #     if self.resource.attributes.get(key) is None:
    #         raise AttributeError(
    #             "'%s' object has no attribute '%s'" % (self.__class__.__name__, key)
    #         )
    #     return self.resource.attributes[key]
    #
    # def __eq__(self, other):
    #     try:
    #         return self._hostname == other._hostname
    #     except AttributeError:
    #         return self._hostname == other
    #
    # def __hash__(self):
    #     return hash(self.key())
    #
    # def key(self):
    #     return self._hostname, self.resource.site_name
    #
    # def get_interface(self, if_name):
    #     """Get a single interface
    #     :param if_name: name of the interface"""
    #     return self._interfaces.get(if_name)
    #
    # def add_interface(self, interface):
    #     """Add interface to this device
    #     param interface: a 'Interface' object to add"""
    #     self._interfaces[str(interface)] = interface
    #
    # def remove_interface(self, if_name):
    #     """Remove interface to this device
    #     param if_name: the name of the interface to be delete"""
    #     try:
    #         self._interfaces[if_name].delete()
    #         del self._interfaces[if_name]
    #     except KeyError:
    #         return None
    #
    def post_update(self):
        """POST or UPDATE device in NSoT server"""
        super(Device, self).post_update()

        self._nsot_objects[str(self)] = self._nsot_object

    def delete(self, force=False):
        """DELETE device in NSoT server"""
        super(Device, self).delete()
        # delete all interfaces assign to the device
        if force:
            for interface in sorted(
                self._interfaces.values(), key=lambda x: not x.is_subinterface()
            ):
                interface.delete()

        try:
            del self._nsot_objects[str(self)]
        except KeyError:
            return None
