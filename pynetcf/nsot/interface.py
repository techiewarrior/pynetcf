# from copy import deepcopy
from pynetcf.utils.logger import get_logger
from .resource import Resource
from .device import Device
from .network import Network


# from pynetcf.utils.macaddr import MACAddressManager

# _macaddr_manager = MACAddressManager()

logger = get_logger(__name__)


class Interface(Resource):
    """A single Interface"""

    # instance arguments
    _args = ("device", "name", "site_id")

    @classmethod
    def _check_args(cls, attrs):
        """Manipulate object arguments before creating the instance"""
        try:
            device = Device.manager.get(id=int(attrs.device))
            attrs._device = device
            attrs.site_id = device.site_id
            attrs.device = device.hostname
        except ValueError:
            return None

    @classmethod
    def _pre_init(cls, obj):
        """Manipulate specific resource instance attributes before returning"""

        # get the device object
        if obj._attrs.get("_device"):
            device = obj._attrs._device
        else:
            device_key = obj.device, obj.site_id
            device = Device.manager._objects.get(device_key) or Device(*device_key)

        device.add_interface(obj)

        # get the network object
        addrs = {
            addr: Network.manager._objects.get((addr, obj.site_id))
            for addr in obj.addresses
        }
        networks = tuple(a.parent for a in addrs.values())

        # get the parent interface object
        try:
            ifname, _ = obj.name.split(".")
            parent_key = obj.device, ifname, obj.site_id
            parent = cls.manager._objects.get(parent_key) or cls(*parent_key)
            parent._sub_interfaces.append(obj)
        except ValueError:
            parent = None

        obj._attrs.pop("_device", None)

        obj._attrs.update(
            {
                "_sub_interfaces": [],
                "_old_addresses": set(),
                "_addresses": addrs,
                "_networks": networks,
                "parent": parent,
                "device": device,
            }
        )

        # placeholder of the name of network assign to this interface
        # this is to assigned addresses automatically
        obj.network_assignment = None

    def is_sub_interface(self):
        """Return `True` if this interface is derived from parent
        interface else `False`"""
        return bool(self.parent)

    def is_parent(self):
        "Return `True` if this interface has sub interfaces else `False`"
        return bool(self._sub_interfaces)

    def update_post(self):
        """POST or UPDATE interface in NSoT server"""
        device = self.device
        parent = self.parent

        # post the device assigned to this interface if not yet exists in NSoT server
        if not device.exists():
            device.update_post()

        # post the parent interface if not yet exists in NSoT server
        try:
            if not parent.exists():
                parent.update_post()
            self._payload["parent_id"] = parent.id
        except AttributeError:
            pass

        self._payload.pop("site_id", None)
        self._payload["device"] = device.id

        # post the addresses if not yet exists in NSoT server
        for addr in self._addresses.values():
            addr.update_post()

        # update the state of old addresses if any
        for addr in self._old_addresses:
            addr.state = "orphaned"
            addr.update_post()

        self._attrs.old_addresses = set()

        super().update_post()

    def delete(self, force=False):
        """
        DELETE interface in NSoT server
        :param force: `True` will also delete all the sub interfaces
            if this interface is a parent interface
        """
        if force:
            # delete all sub interfaces belong to this interface being deleted
            for subif in self._attrs.sub_interfaces:
                subif.delete()

            self._attrs.sub_interfaces = []

        # update the state of old addresses if any
        for addr in self._attrs.old_addresses:
            addr.state = "orphaned"
            addr.post_update()

        super().delete()

        # clear caches
        self._attrs._addresses = {}
        self._attrs._old_interfaces = {}

        # TODO: delete mac address in the database
        # self._mac_address = None

    def assign_address(self, cidr=None, random=False, reverse=False):
        """
        Automatically add an IP address to the existing IP addresses
        :param cidr (str): CIDR IPv4 block to get the IP address automatically.
            If `None` it will check for the `network_assignment` attribute,
            if not check if there is an existing IP addresses and use the first index
            of the network list else raises ValueError
        :param random (bool): `True` will assign a random IP
        :param reverse (bool): `True` will assign a reverse order of IP
        """

        if cidr is None:
            if self.network_assignment:
                cidr = Network.manager.get(assignment=self.network_assignment)
            elif self._networks:
                cidr = self._networks[0]
            param = cidr._key, (random, reverse)
        else:
            param = (cidr, self.site_id), (random, reverse)

        hosts = Network.manager.get_hosts_generator(*param)
        addr = next(hosts)

        self._addresses[str(addr)] = addr

        try:
            self._payload["addresses"].append(str(addr))
        except KeyError:
            self._payload["addresses"] = list(self._addresses)

    def add_addresses(self, *args):
        """Add IP addresses to the existing addresses
        :param args (str): host IPv4 CIDR format ex. 192.168.0.1/32
        """

        for addr in args:
            net = Network(addr, self.site_id)
            self._addresses[net.cidr] = net

        try:
            self._payload["addresses"].extend(args)
        except KeyError:
            self._payload["addresses"] = list(self._addresses)

    def remove_addresses(self, *args):
        """
        Remove IP addresses from the existing addresses
        :param args (str): host IPv4 CIDR format ex. 192.168.0.1/32
        """

        new_addrs = set(self._addresses) - set(args)

        try:
            self._payload["addresses"].extend(new_addrs)
        except KeyError:
            self._payload["addresses"] = list(new_addrs)

        for addr in args:
            self._old_addresses.add(Network(addr, self.site_id))
            try:
                del self._addresses[addr]
            except KeyError:
                pass

    def _set_addresses(self, addrs):

        if not isinstance(addrs, list):
            raise ValueError(f"argurments expect a 'list' object, got {type(addrs)}")

        # the diff of addresses
        del_addrs = set(self._addresses) - set(addrs)
        # add the diff of addresses to old_addresses for later purposes
        self._old_addresses.update({self._addresses.get(a) for a in del_addrs})

        self._addresses = {
            a: Network.manager._objects.get((a, self.site_id)) for a in addrs
        }
        self._payload["addresses"] = addrs

    def _delete_addresses(self):
        # add the current address to old addresses for later purposes
        self._old_addresses.update(self._addresses.values())
        self._attrs.addresses = {}
        self._payload["addresses"] = []


# class Interface(Resource):
#
#     _parents = {}
#     _devices = dev_manager.objects
#     _networks = net_manager.objects
#
#     def __init__(
#         self, device=None, name=None, site_name=None, nsot_object=None, **kwargs
#     ):
#
#         """
#         Constructor
#
#         If resource_obj is provided the device, name and site_name is get from it
#         otherwise it is require to provide the those arguments
#
#         :param device: the hostname of the device in str format which the interface
#             is to be assigned
#         :param name: the name of the interface
#         :param resource_obj: the NSoT interface object which a return dict from
#             GET, POST, PATCH. If provided, it will assume that the interface is
#             somehow exists in NSoT server
#         :param kwargs: key/value pair of NSoT attributes of the interface resource,
#             key must be a str and value of str or list depend on the attributes
#             'multi' value. Key as the name of the attribute must created beforehand.
#         """
#
#         super(Interface, self).__init__(site_name=site_name, nsot_object=nsot_object)
#
#         device = self._nsot_object.get("device_hostname") or device
#         name = self._nsot_object.get("name") or name
#         addrs = self._nsot_object.get("addresses") or []
#
#         if not all([device, name]):
#             raise TypeError("Requires both 'device' and 'name' of the interface")
#
#         _device = self._devices.site(self.site_name).get_key(device)
#
#         addresses = {a: self._networks.site(site_name).get_key(a) for a in addrs}
#
#         try:
#             parent, sub = name.split(".")
#             parent_id = "{}:{}".format(device, parent)
#             if self._parents.get(parent_id) is None:
#                 self._parents[parent_id] = Interface()
#         except ValueError:
#             pass
#
#         self.device = _device
#         self.name = name
#
#         self._attributes = kwargs
#         self._addresses = addresses
#         self._old_addresses = set()
#         self._sub_interfaces = set()
#
#         _device.add_interface(self)
#
#     # @property
#     # def virtual_mac(self):
#     #     return self._mac_addrs.get(self._name)
#
#     @property
#     def parent(self):
#         """The parent interface of the interface"""
#         return self._parent
#
#     @property
#     def sub_interfaces(self):
#         """The sub interfaces of the interface"""
#         return self._sub_interfaces
#
#     @property
#     def description(self):
#         """The description of the interface"""
#         try:
#             return self._payload["description"]
#         except KeyError:
#             return self._nsot_object.get("description")
#
#     @property
#     def addresses(self):
#         """The IP addresses of the interface"""
#         try:
#             return self._payload["addresses"]
#         except KeyError:
#             return list(self._addresses)
#
#     @property
#     def networks(self):
#         """The network that the interface belong"""
#         return self._nsot_object.get("networks")
#
#     @property
#     def mac_address(self):
#         """The MAC address of the interface"""
#         return self._nsot_object.get("mac_address")
#
#     # @parent.setter
#     # def parent(self, parent):
#     #     if not hasattr(parent, "post_update"):
#     #         raise ValueError(
#     #             "Value expect a 'Interface' object got %s" % type(parent)
#     #         )
#     #     if self._parent and self._parent != parent:
#     #         raise ValueError(
#     #             "Parent interface does not match with current interface, %s"
#     #             % self.name
#     #         )
#     #     parent.add_subintf(self)
#     #     self._objs["parent"] = parent
#
#     @description.setter
#     def description(self, description):
#         self._payload["description"] = description
#
#     @addresses.setter
#     def addresses(self, addrs):
#         # the diff of addresses
#         del_addrs = set(self._addresses) - set(addrs)
#         # add the diff of addresses to old_addresses for later purposes
#         self._old_addresses.update({self._addresses.get(a) for a in del_addrs})
#
#         self._addresses = {
#             a: net_manager.site(self.site_name).get_key(a) for a in addrs
#         }
#
#         self._payload["addresses"] = addrs
#
#     @addresses.deleter
#     def addresses(self):
#         # add the current address to old addresses for later purposes
#         self._old_addresses.update(self._addresses.values())
#         self._addresses = {}
#         self._payload["addresses"] = []
#
#     def init_payload(self):
#         if not self.exists():
#             self._payload = {
#                 "device": self._device.id or self._device.hostname,
#                 "name": self._name,
#                 "attributes": self._attributes,
#             }
#
#     def key(self):
#         return str(self.device), self.name, self.site_name
#
#     def assign_address(self, cidr, random=False, reverse=False):
#         """Add an address based on CIDR provided"""
#         addr = next(
#             self._networks[self._site_name].get_hosts_generator(
#                 cidr, random=random, reverse=reverse
#             )
#         )
#         self._addresses[str(addr)] = addr
#
#         try:
#             self._payload["addresses"].append(addr)
#         except KeyError:
#             self._payload["addresses"] = list(self._addresses) + [addr]
# #
#     def add_addresses(self, *args):
#         """
#         Add addresses from the current addresses
#         :param args: 'Network' objects
#         """
#
#         try:
#             self._payload["addresses"].extend(args)
#         except KeyError:
#             self._payload["addresses"] = list(self._addresses)
#
#         for addr in args:
#             self._addresses[addr] = net_manager.site(self.site_name).get_key(addr)
#             self._payload["addresses"].append(addr)
#
#     def remove_addresses(self, *args):
#         """
#         Remove addresses from the current addresses
#         :param args: 'Network' objects
#         """
#
#         new_addrs = set(self._addresses.values()) - set(args)
#
#         try:
#             self._payload["addresses"].extend(new_addrs)
#         except KeyError:
#             self._payload["addresses"] = list(new_addrs)
#
#         for addr in new_addrs:
#             self._old_addresses.add(self._addresses.get(addr))
#             try:
#                 del self._addresses[addr]
#             except KeyError:
#                 pass
#
#     def is_sub_interface(self):
#         """return: True if interface is a sub interface else False"""
#         return bool(self._parent)
#
#     def is_parent(self):
#         """return: True if interface is a parent interface else False"""
#         return bool(self._sub_interfaces)
#
#     def add_sub_interface(self, interface):
#         """
#         Add subinterface to the parent interface
#         :param args: 'Interface' object
#         """
#         self._sub_interfaces.add(interface)
#
#     def post_update(self):
#         """POST or UPDATE interface in NSoT server"""
#         if not self.device.exists():
#             self.device.post_update()
#
#         try:
#             if not self.parent.exists():
#                 self.parent.post_update()
#         except AttributeError:
#             pass
#
#         for addr in self._addresses.values():
#             addr.post_update()
#
#         self._update_old_addresses()
#
#         super(Interface, self).post_update()
#
#         self._old_addresses = set()
#
#     def delete(self, force=False):
#         """
#         DELETE interface in NSoT server
#         :param force: 'True' will try delete all the child interface if the interface
#             to be deleted is a parent interface
#         """
#         if force:
#             # delete all sub interfaces belong to this interface being deleted
#             for sub in self._sub_interfaces:
#                 sub.delete()
#
#             self._sub_interfaces = set()
#
#         # update the state of the addresses assigned to this interface being deleted
#         self._update_old_addresses()
#
#         super(Interface, self).delete()
#
#         # clear caches
#         self._addresses = {}
#         self._old_interfaces = {}
#
#         # TODO: delete mac address in the database
#         self._mac_address = None
#
#     def _update_old_addresses(self):
#         for addr in self._old_addresses:
#             addr.state = "orphaned"
#             addr.post_update()
#
#
# class Manager:
#     objects = NSoTResourceManager(Interface)
