# from pyconfigvars.helpers.macaddress import MACAddress
# from pyconfigvars.variables import FileConfig

ATTRIBUTES = [
    ("name", None),
    ("tenant", "default"),
    ("allow_nat", False),
    ("l3vid", None),
]

SVI_GATEWAY = -1


class Vlan:
    "A single `Vlan`"

    def __init__(self, **kwargs):

        if not kwargs.get("id"):
            raise TypeError("'Vlan' require an ID")

        self._id = int(kwargs["id"])

        for attr, default_v in ATTRIBUTES:
            setattr(self, attr, kwargs.get(attr, default_v))

        self._vlan_iface = None
        self._vxlan_iface = None
        self._network = kwargs.get("network")

    @property
    def vlan_iface(self):
        if self._vlan_iface is None:
            self._vlan_iface = VlanIface(self)
        return self._vlan_iface

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
        try:
            return self._network.cidr
        except AttributeError:
            return self._network

    @network.setter
    def network(self, network):
        if not hasattr(network, "cidr"):
            raise TypeError("Value must be a `Network` class")
        self._network = network

    def key(self):
        return self.id, self.tenant

    def __repr__(self):
        return "Vlan(%s)" % self.id

    def __eq__(self, other):
        try:
            return (self.id, self.tenant) == (other.id, other.tenant)
        except AttributeError:
            return NotImplemented

    def __gt__(self, other):
        try:
            return self.id > other.id
        except AttributeError:
            return NotImplemented

    def __lt__(self, other):
        try:
            return self.id < other.d
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash((self.id, self.tenant))

    def getdict(self):
        "return: a dict object of `Vlan`"
        attrs = {attr: getattr(self, attr) for attr, _ in ATTRIBUTES}
        return {"id": self.id, "type": self.type, **attrs, "network": self.network}

    # def get_vxlan_interface(self):
    #     pass
    #
    # def get_vlan_interface(self):
    #     pass


class VlanIface:
    def __init__(self, vlan):
        self._vlan = vlan
