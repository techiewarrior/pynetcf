from .resource import NSoTResource
from ..devices import Devices

# from ..network.manager import NSoTNetworks

# from pynetcf.utils.macaddr import MACAddressManager

RESOURCE_NAME = "interfaces"

# _macaddr_manager = MACAddressManager()


class Interface(NSoTResource):

    _parents = {}
    _sitedevices_cache = {}

    def __init__(
        self, device=None, name=None, site_name=None, nsot_object=None, **kwargs
    ):

        """
        Constructor

        If resource_obj is provided the device, name and site_name is get from it
        otherwise it is require to provide the those arguments

        :param device: the hostname of the device in str format which the interface
            is to be assigned
        :param name: the name of the interface
        :param resource_obj: the NSoT interface object which a return dict from
            GET, POST, PATCH. If provided, it will assume that the interface is
            somehow exists in NSoT server
        :param kwargs: key/value pair of NSoT attributes of the interface resource,
            key must be a str and value of str or list depend on the attributes
            'multi' value. Key as the name of the attribute must created beforehand.
        """

        if nsot_object:
            _device = Devices.objects.get(id=nsot_object["device"])
            site_name = _device.site_name

        super(Interface, self).__init__(site_name=site_name, nsot_object=nsot_object)

        if nsot_object is None:
            if not all([device, name]):
                raise TypeError("Requires both 'device' and 'name' of the interface")

            if self._sitedevices_cache.get(self.site_name) is None:
                self._sitedevices_cache[self.site_name] = Devices.site(
                    self.site_name
                )
            _device = self._sitedevices_cache[self.site_name](device)

        self.device = _device
        self.name = self._nsot_object.get("name") or name

        # resource = NSoTResource(
        #     name=RESOURCE_NAME, site_name=site_name, resource_obj=resource_obj
        # )
        #
        # name = resource.object.get("name", name)
        #
        # if not resource_obj:
        #     if not all([device, name]):
        #         raise TypeError("Requires both 'device' and 'name' of the interface")
        #     site_name = resource.site_name
        #     _device = Resource.devices.get(hostname=device, site_name=site_name)
        #     resource.payload = {"device": device, "name": name, "attributes": kwargs}
        # else:
        #     _device = NSoTDevices.get(id=resource_obj.get("device"))
        #     site_name = _device.site_name
        #
        # if self._networks.get(site_name) is None:
        #     self._networks[site_name] = NSoTNetworks.sites(site_name)
        #
        # addresses = resource.object.get("addresses", [])
        #
        # _addresses = {
        #     addr: self._networks[site_name].get(addr) for addr in addresses
        # }
        #
        # try:
        #     parent, sub = name.split(".")
        #     parent_id = "{}:{}".format(device, parent)
        #     if self._parents.get(parent_id) is None:
        #         self._parents[parent_id] = Interface()
        # except ValueError:
        #     pass
        #
        # self.resource = resource
        # self.parent = parent
        #
        # self._device = _device
        # self._name = name
        # self._addresses = _addresses
        # self._old_addresses = set()
        # self._sub_intfs = set()
        # self._site_name = site_name
        #
        _device.add_interface(self)

    # @property
    # def virtual_mac(self):
    #     return self._mac_addrs.get(self._name)

    # @property
    # def name(self):
    #     """The name of the interface"""
    #     return self._name

    # @property
    # def device(self):
    #     """The device which the interface is assigned"""
    #     return self._device

    @property
    def parent(self):
        """The parent interface of the interface"""
        return self._parent

    @property
    def name_slug(self):
        """The unique name of the interface which is a the combination of
        hostname:interface_name ex. switch1:lo0"""
        return "{}:{}".format(self.device, self.name)

    @property
    def sub_interfaces(self):
        """The sub interfaces of the interface"""
        return self._subintfs

    @property
    def description(self):
        """The description of the interface"""
        return self.resource.object.get("description")

    @property
    def addresses(self):
        """The IP addresses of the interface"""
        return list(self._addresses)

    @property
    def networks(self):
        """The network that the interface belong"""
        return self.resource.object.get("networks")

    @property
    def mac_address(self):
        """The MAC address of the interface"""
        return self.resource.object.get("mac_address")

    # @parent.setter
    # def parent(self, parent):
    #     if not hasattr(parent, "post_update"):
    #         raise ValueError(
    #             "Value expect a 'Interface' object got %s" % type(parent)
    #         )
    #     if self._parent and self._parent != parent:
    #         raise ValueError(
    #             "Parent interface does not match with current interface, %s"
    #             % self.name
    #         )
    #     parent.add_subintf(self)
    #     self._objs["parent"] = parent

    @description.setter
    def description(self, description):
        self.resource.payload["description"] = description

    @addresses.setter
    def addresses(self, addrs):
        # the diff of addresses
        diff_addrs = set(self._addresses) - set(addrs)
        # add the diff of addresses to old_addresses for later purposes
        self._old_addresses.update(diff_addrs)
        self._addresses = {
            addr: self._networks[self._site_name].get(addr) for addr in addrs
        }

    @addresses.deleter
    def addresses(self):
        # add the current address to old addresses for later purposes
        self._old_addresses.update(self._objs["addresses"])
        self._addresses = set()

    def key(self):
        return self.name_slug, self.site_name

    # def __repr__(self):
    #     return "Interface({}, {})".format(self._device, self._name)
    #
    # def __eq__(self, other):
    #     try:
    #         return (self._device, self._name) == (other.device, other.name)
    #     except AttributeError:
    #         return self.name_slug == other
    #
    # def __hash__(self):
    #     return hash((self._device, self._name))

    def assign_address(self, cidr, random=False, reverse=False):
        """Add an address based on CIDR provided"""
        addr = next(
            self._networks[self._site_name].get_hosts_generator(
                cidr, random=random, reverse=reverse
            )
        )
        self._addresses[str(addr)] = addr

    def add_addresses(self, *args):
        """
        Add addresses from the current addresses
        :param args: 'Network' objects
        """
        for addr in args:
            self._addresses[addr] = self._networks[self._site_name].get(addr)

    def remove_addresses(self, *args):
        """
        Remove addresses from the current addresses
        :param args: 'Network' objects
        """

        self._old_addresses.update(
            [self._networks[self._site_name].get(addr) for addr in args]
        )
        for addr in args:
            try:
                del self._addresses[addr]
            except KeyError:
                pass

    def is_subinterface(self):
        """return: True if interface is a sub interface else False"""
        return bool(self._parent)

    def is_parent(self):
        """return: True if interface is a parent interface else False"""
        return bool(self._sub_intfs)

    def add_subinterface(self, interface):
        """
        Add subinterface to the parent interface
        :param args: 'Interface' object
        """
        self._sub_intfs.add(interface)

    def post_update(self):
        """POST or UPDATE interface in NSoT server"""
        if not self._device.resource.exists():
            self._device.post_update()

        try:
            if not self._parent.resource.exists():
                self._parent.post_update()
        except AttributeError:
            pass

        for addr in self._addresses.values():
            addr.post_update()

        for old_addr in self._old_addresses:
            old_addr.state = "orphaned"
            old_addr.post_update()

        self.resource.payload["addresses"] = list(self._addresses)
        self.resource.post_update()

        self._old_addresses.clear()

    def delete(self, force=False):
        """
        DELETE interface in NSoT server
        :param force: 'True' will try delete all the child interface if the interface
            to be deleted is a parent interface
        """
        if force:
            # delete all sub interfaces belong to this interface being deleted
            for sub in self._sub_intfs:
                sub.delete()

        # update the state of the addresses assigned to this interface being deleted
        for addr in self._addresses:
            addr.state = "orphaned"
            addr.post_update()

        self.resource.delete()

        # clear caches
        self._addresses.clear()
        self._sub_intfs.clear()

        # TODO: delete mac address in the database
        self._mac_address = None

    def get(self):
        return self.resource.get(name_slug=self.name_slug)
