from collections import defaultdict

from pynetcf.utils import get_logger
from pynetcf.nsot.network.manager import NSoTNetworks
from pynetcf.utils.macaddr import MACAddressManager
from .vlan import Vlan
from .tenant import TenantData

logger = get_logger(__name__)


class VlanManager:
    "Manager and create `Vlan`"

    def __init__(self, site_name=None):

        self._networks = NSoTNetworks.sites(site_name=site_name)

        self._data = TenantData()

        self._mac_addrs = MACAddressManager()

        self._cache = {}
        self._tenants = set()

    def __call__(self, vid):
        int_vid = int(vid)
        if self._cache.get(int_vid) is None:
            raise TypeError("VLAN%s does not exists" % vid)
        return self._cache[int_vid]

    def add(self, assign_l3vid=False, assign_virtual_mac=False, **kwargs):
        """Add `Vlan` as well as tenant if not exists

        :param assign_l3vid: if `True` will create a L3 VLANID for the tenant
        :param kwargs: attributes of the `Vlan`
        """
        vlan = Vlan(**kwargs)

        # raise if vlan.id in range of the reserved L3VLAN
        if vlan.id >= 4000:
            raise ValueError("VLAN%s is reserved for L3VLAN" % vlan.id)

        try:
            if vlan != self._cache[vlan.id]:
                raise TypeError(
                    "VLAN%s is already assign to %s"
                    % (vlan.id, self._cache[vlan.id].tenant)
                )
        except KeyError:
            self._cache[vlan.id] = vlan

        tenant = kwargs.get("tenant", "default")
        self._tenants.add(tenant)

        if assign_l3vid:
            # assign a L3 VLANID to tenant

            l3vid = self._data.get_l3vids(tenant)
            vlan.l3vid = l3vid

            # add the L3 VLAN once to cache
            if self._cache.get(l3vid) is None:
                l3vlan = Vlan(id=l3vid, tenant=tenant)
                interface = str(l3vlan).lower()

                mac = self._mac_addrs.get(interface)
                if mac is None:
                    l3vlan.virtual_mac = self._mac_addrs.create(interface)
                else:
                    l3vlan.virtual_mac = mac

                self._cache[l3vid] = l3vlan

        interface = str(vlan).lower()
        if assign_virtual_mac:
            mac = self._mac_addrs.get(interface)
            if mac is None:
                vlan.virtual_mac = self._mac_addrs.create(interface)
            else:
                vlan.virtual_mac = mac

    def get(self, vid=None):
        if vid is None:
            return sorted(self._cache.values(), key=lambda x: x.id)
        return self._cache.get(vid)

    def filter(self, **kwargs):

        if kwargs:
            for vlan in self._cache.values():
                query = []
                try:
                    for key, value in kwargs.items():
                        try:
                            attr_value = value(getattr(vlan, key))
                        except TypeError:
                            attr_value = getattr(vlan, key)
                        query.append(
                            True
                            if value == attr_value or attr_value is True
                            else False
                        )
                    if all(query):
                        yield vlan
                except AttributeError:
                    pass

    def assign_networks(self, random=False):
        """Assign network to `Vlan` and MAC address

        :param is_random: if `True` select a random network from the pool of subnets.
        :param mac_addr: if `True` automatically assign MAC address to VLANs from
            reserved range.
        """
        # generator of subnets to use in vlans which does not have manually
        # assigned networks
        subnets = self._networks.subnets_generator("192.168.0.0/16", random=random)
        # mac addresses iterator
        # mac_addrs = self._networks.mac_addrs.iter_addrs()

        # get existing assigned networks
        filtered_networks = self._networks.filter(
            resource=lambda x: x.attributes.get("assignment", "").startswith("vlan")
        )
        networks = {int(n.assignment.split("vlan")[1]): n for n in filtered_networks}

        # placeholder to check if new CIDR was priously assigned
        found = {}
        # placeholder of network/vids value pair to check if network has
        # multiple VLAN assigned
        _networks = defaultdict(list)

        for vlan in sorted(
            self.filter(type="l2"), key=lambda x: True if x.cidr is None else False
        ):

            network = networks.get(vlan.id)

            # create VLAN network which is manually assigned to avoid it
            # assigning automatically to another VLAN later
            if vlan.cidr:
                if found.get(vlan.cidr):
                    raise ValueError(
                        "Duplicate VLAN network assignment: %s," % vlan.cidr
                    )
                else:
                    found[vlan.cidr] = True

                # discard previous network if not equal to current CIDR
                if network and network != vlan.cidr:
                    network = None

                # create network from NSoTNetworks
                if network is None:
                    network = self._networks(vlan.cidr)
                    network.state = "reserved"

                    # raise if CIDR is a host
                    if network.is_host:
                        raise ValueError(
                            "Invalid network: {} is an IP address belong "
                            "to {}".format(vlan.cidr, network.parent)
                        )

                    # raise if network overlaps with network which is already reserved
                    for subnet in self._networks.get_subnets(network):
                        if subnet.state == "reserved":
                            try:
                                assignment = _networks.get(subnet.parent)[0]
                            except TypeError:
                                assignment = subnet.assignment
                            raise ValueError(
                                "{} overlaps with {} which is already a "
                                "reserved CIDR block to {}".format(
                                    vlan.cidr, subnet, assignment.upper()
                                )
                            )

                    # raise if network overlaps with parent which is already reserverd
                    try:
                        if network.parent.state == "reserved":
                            try:
                                assignment = _networks.get(network.parent)[0]
                            except TypeError:
                                assignment = network.parent.assignment
                            raise ValueError(
                                "{} overlaps with {} which is already a "
                                "reserved CIDR block to {}".format(
                                    network, network.parent, assignment.upper()
                                )
                            )
                    except AttributeError:
                        pass
            else:
                # discard previous network if it is manually assigned
                try:
                    if network.is_auto_assign == "False":
                        network = None
                except AttributeError:
                    pass

                # get network from subnets iterator
                if network is None:
                    network = next(subnets)
                    network.state = "reserved"

            _networks[network].append(vlan)

        # print(_networks)
        for _network, vlans in _networks.items():
            # raise if network was assign to multiple VLANs
            if len(vlans) > 1:
                raise ValueError("Duplicate VLAN network assignment: %s," % _network)
            vlan = vlans[0]

            _network.resource.add_attributes(
                assignment="vlan%s" % vlan.id,
                is_auto_assign="False" if vlan.cidr else "True",
            )
            # print(vlan.id, _network, _network.resource.payload)
            _network.post_update()

        # print(_networks)
        # gw_ip = self._networks.get_gateway_ip(_network)
        # vlan.interface.network = _network
        # vlan.interface.gateway_ip = gw_ip

        # if mac_addr:
        #     for vlan in self._cache.values():
        #         assign = "vlan%s" % vlan.id
        #         mac = self._networks.mac_addrs.get(assignment=assign)
        #         if mac is None:
        #             mac = next(mac_addrs)
        #             mac.assignment = assign
        #         vlan.interface.mac_addr = mac
        #
        for _net in set(networks.values()) - set(_networks):
            self._networks.delete(_net, force=True)

    # def get_interface(self, interface):
    #     vid = int(interface.split("vlan")[-1])
    #     return self._cache.get(vid).interface
    #
    # def iter_hosts(self, reverse=False):
    #     return {
    #         "vlan%s" % vlan.id: self._networks.iter_hosts(vlan.interface.network)
    #         for vlan in self._cache.values()
    #         if vlan.type == "l2"
    #     }

    def update(self):

        l3vids = []

        filtered = self._mac_addrs.filter(assignment=lambda x: x.startswith("vlan"))
        for mac_addr in filtered:
            vid = int(mac_addr.assignment.split("vlan")[1])
            if self._cache.get(vid) is None:
                # print(mac_addr, mac_addr.assignment)
                self._mac_addrs.delete(mac_addr.assignment)
                if vid >= 4000:
                    l3vids.append(vid)

        self._data.delete(*l3vids)
        # cur_tenants = {v.tenant for v in self._cache.values()}
        # diff_tenants = set(self._data.get_tenants()) - cur_tenants
        # for tenant in diff_tenants:
        #     l3vid = self._data.get_l3vids(tenant)
        #     self._networks.mac_addrs.delete(assignment="vlan%s" % l3vid)
        # self._data.delete_tenants(diff_tenants)
