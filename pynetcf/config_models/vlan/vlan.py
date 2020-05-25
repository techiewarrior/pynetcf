ATTRIBUTES = [
    ("name", None),
    ("tenant", "default"),
    ("allow_nat", False),
    ("l3vid", None),
]


class Vlan:
    "A single `Vlan`"

    def __init__(self, **kwargs):

        if not kwargs.get("id"):
            raise TypeError("'Vlan' require an ID")

        self._id = int(kwargs["id"])

        for attr, default_v in ATTRIBUTES:
            setattr(self, attr, kwargs.get(attr, default_v))

        self._cidr = kwargs.get("cidr")
        self._network = None
        self._virtual_mac = None

        # self._interface = VLANInterface(name="vlan%s" % self.id)

    @property
    def id(self):
        "return: the ID of `Vlan`"
        return self._id

    @property
    def type(self):
        "return: the type of the `Vlan`"
        return "l2" if self.id < 4000 else "l3"

    @property
    def network(self):
        return self._network

    @network.setter
    def network(self, value):
        if not hasattr(value, "cidr"):
            raise TypeError("Value must be a 'Network' object")
        self._network = value

    @property
    def virtual_mac(self):
        return self._virtual_mac

    @virtual_mac.setter
    def virtual_mac(self, value):
        if not hasattr(value, "address"):
            raise TypeError("Value must be a 'MacAddress' object")
        self._virtual_mac = value

    @property
    def cidr(self):
        return self._cidr

    # @property
    # def vxlan_id(self):
    #     return C.VXLAN_BASE_ID + self.id
    #
    # @property
    # def vxlan_name(self):
    #     return C.VXLAN_BASE_NAME + str(self.id)
    #
    # @property
    # def interface(self):
    #     return "vlan%s" % self._id

    def key(self):
        return self.id, self.tenant

    def __repr__(self):
        return "Vlan(%s)" % self.id

    def __str__(self):
        return "VLAN%s" % self.id

    def __eq__(self, other):
        try:
            return self.key() == other.key()
        except AttributeError:
            return NotImplemented

    def __gt__(self, other):
        try:
            return self.id > other.id
        except AttributeError:
            return NotImplemented

    def __lt__(self, other):
        try:
            return self.id < other.id
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash((self.id, self.tenant))

    # def getdict(self):
    #     "return: a dict object of `Vlan`"
    #     attrs = {attr: getattr(self, attr) for attr, _ in ATTRIBUTES}
    #     return {"id": self.id, **attrs, "cidr": self.cidr, "type": self.type}

    # def iface_dict(self):
    #     return {
    #         "name": "vlan%s" % self.id,
    #         "tenant": self.tenant,
    #         "type": self.type,
    #         **self.interface.getdict(),
    #     }
    #
    # def vxlan_iface_dict(self):
    #     return {
    #         "name": self.vxlan_name,
    #         "id": self.vxlan_id,
    #         "tenant": self.tenant,
    #         "vlan_type": self.type,
    #         "vlan_id": self.id,
    #         "vlan_name": self.name,
    #     }


# class VLANInterface:
#     def __init__(self, name, device=None):
#         self._name = name
#         self._device = None
#
#         self.mac_addr = None
#         self.network = None
#         self.gateway_ip = None
#
#     def getdict(self):
#         try:
#             network = str(self.network.network)
#             prefixlen = self.network.prefixlen
#             subnet_mask = str(self.network.subnet_mask)
#         except AttributeError:
#             network = None
#             prefixlen = None
#             subnet_mask = None
#
#         if self.gateway_ip:
#             gw = str(self.gateway_ip.network)
#         else:
#             gw = None
#
#         if self.mac_addr:
#             mac = str(self.mac_addr)
#         else:
#             mac = None
#
#         return {
#             "network": network,
#             "prefixlen": prefixlen,
#             "subnet_mask": subnet_mask,
#             "gateway_ip": gw,
#             "mac_address": mac,
#         }
