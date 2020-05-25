from .resource import Resource


class Device(Resource):
    _args = ("hostname", "site_id")

    @classmethod
    def _check_args(cls, attrs):
        attrs.interfaces = {}

    @property
    def interfaces(self):
        """Manipulate object arguments before creating the instance"""
        return tuple(self._attrs.interfaces.values())

    def get_interface(self, ifname):
        """
        Get a single interface from this device
        :param if_name (str): name of the interface
        """
        return self._attrs.interfaces.get(ifname)

    def add_interface(self, ifobj):
        self._attrs.interfaces[ifobj.name] = ifobj

    def remove_interface(self, ifname):
        """
        Remove interface to this device
        param if_name (str): name of the interface
        """
        try:
            self._attrs.interfaces[ifname].delete()
            del self._attrs.interfaces[ifname]
        except KeyError:
            return None

    def delete(self, force=False):
        """
        DELETE device in NSoT server
        :param force (bool): `True` will also delete the interfaces
            assigned to this device
        """

        if force:
            for iface in sorted(
                self._attrs.interfaces.values(),
                key=lambda x: not x.is_subinterface(),
            ):
                iface.delete()

        super().delete()


# class Device(Resource):
#     "Represent a single device"
#
#     def __init__(self, hostname=None, site_name=None, nsot_object=None, **kwargs):
#         """
#         Constructor
#
#         The value from 'nsot_object['hostname']' is use as a 'hostname' when is given
#         else the 'hostname' via param is use. Raises TypeError if both 'nsot_object'
#         and 'hostname' is None.
#
#         :param hostname: the hostname of the device in str format
#         :param resource_obj: the NSoT device object which a return dict from
#             GET, POST, PATCH. If provided, this will assume that the device is
#             somehow exists in NSoT server
#         :param kwargs: key/value pair of NSoT attributes of the device resource,
#             key must be a str and value of str or list depend on the attributes
#             'multi' value. Key as the name of the attribute must created beforehand.
#         """
#         super(Device, self).__init__(site_name=site_name, nsot_object=nsot_object)
#
#         self._hostname = self._nsot_object.get("hostname", hostname)
#         self._interfaces = {}
#         self._attributes = kwargs
#
#         if nsot_object is None:
#             self.init_payload()
#
#     @property
#     def hostname(self):
#         """The hostname of the device"""
#         return self._hostname
#
#     @property
#     def interfaces(self):
#         """The interfaces belong to this device"""
#         return list(self._interfaces.values())
#
#     def init_payload(self):
#         self._payload = {"hostname": self._hostname, "attributes": self._attributes}
#
#     def key(self):
#         return self._hostname, self.site_name
#
#     def get_interface(self, if_name):
#         """Get a single interface
#         :param if_name: name of the interface"""
#         return self._interfaces.get(if_name)
#
#     def add_interface(self, interface):
#         """Add interface to this device
#         param interface: a 'Interface' object to add"""
#         self._interfaces[str(interface)] = interface
#
#     def remove_interface(self, if_name):
#         """Remove interface to this device
#         param if_name: the name of the interface to be delete"""
#         try:
#             self._interfaces[if_name].delete()
#             del self._interfaces[if_name]
#         except KeyError:
#             return None
#
#     def delete(self, force=False):
#         """DELETE device in NSoT server"""
#         # delete all interfaces assign to the device
#         if force:
#             for interface in sorted(
#                 self._interfaces.values(), key=lambda x: not x.is_subinterface()
#             ):
#                 interface.delete()
#
#         super(Device, self).delete()
#
#
# class Manager:
#     objects = NSoTResourceManager(Device)
