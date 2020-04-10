from .vlan import Vlan
from .data import VlanData


class VlanManager:
    "Manager and create `Vlan`"

    def __init__(self, networks=None):

        self._data = VlanData()

        self._networks = networks
        self._networks_cache = None
        self._networks_changed = False

        self._vlans_cache = {}

    def add(self, **kwargs):
        "Add `Vlan` as well as tenant if not exists"

        vlan = Vlan(**kwargs)

        if vlan.id >= 4000:
            raise ValueError("VLAN%s is reserved for L3VLAN" % vlan.id)

        try:
            if vlan != self._vlans_cache[vlan.id]:
                raise TypeError(
                    "VLAN%s is already assign to '%s' tenant"
                    % (vlan.id, self._vlans_cache[vlan.id].tenant)
                )
        except KeyError:
            self._vlans_cache[vlan.id] = vlan

        tenant = kwargs.get("tenant", "default")
        l3vid = self._data.get_l3vids(tenant)

        if self._vlans_cache.get(l3vid) is None:
            self._vlans_cache[l3vid] = Vlan(id=l3vid, tenant=tenant)

        vlan.l3vid = l3vid

    def get_networks(self):
        if self._networks_cache is None or self._networks_changed:
            self._networks_cache = {
                net.get_dict()["vlan_id"]: net
                for net in self._networks.query(vlan_id=True)
            }
        return self._networks_cache

    def getdict(self):
        return [vlan.getdict() for _, vlan in self._vlans_cache.items()]

    def query(self, vids=None, sortby=None, reverse=False, **kwargs):
        """
        Query `Vlan` attributes based on kwargs or specific cidrs

        return: list of `Vlan`
        """

        def none_to_str(vlan, key):
            attr = getattr(vlan, key, None)
            return "" if attr is None else attr

        # default result
        vlans = list(self._vlans_cache.values())
        results = []

        if vids:
            # query specific vlans
            results = [self._vlans_cache.get(int(vid), Vlan(vid)) for vid in vids]
        elif kwargs:
            # query attributes based on key/value kwargs param
            for vlan in vlans:
                query = []
                for k, v in kwargs.items():
                    value = getattr(vlan, k, None)
                    query.append(value == v or v is True and value is not None)
                if all(query):
                    results.append(vlan)

        # sort results
        if sortby:
            return sorted(
                results, key=lambda x: none_to_str(x, sortby), reverse=reverse
            )
        return results

    def assign_networks(self):
        if self._networks is None:
            return

        # iterator of subnets to use in vlans which has no manually assigned networks
        subnets = self._networks.iter_subnets(["192.168.0.0/16"], is_random=False)
        # get existing assigned networks
        vlan_networks = self.get_networks()

        # placeholder to check if manually assigned network
        # is not assigned to another VLAN
        def_networks = set()

        for vlan in self.query(type="l2", sortby="network", reverse=True):
            str_id = str(vlan.id)

            # check if VLAN has already assigned networks
            net = vlan_networks.get(str_id)

            # create VLAN network
            if net is None:
                # add network which is manually assigned to avoid the iterator
                # to assign same network
                if vlan.network:

                    # raise exception if network is already assign to previous vlan
                    if vlan.network in def_networks:
                        raise TypeError(
                            "Duplicate network assignment in VLANs: '%s'"
                            % vlan.network
                        )
                    # add network to NSoT server
                    net = self._networks.get(vlan.network)

                    def_networks.add(vlan.network)

                # get network in the subnets iterator
                else:
                    net = next(subnets)

                # assign network NSoT attributes and add or update in the server
                net.attributes = {"vlan_id": str_id}
                net.update()
                self._networks_changed = True

            vlan.network = net

    def update(self):

        # placeholder of vids in database that does not exists in current configs and
        # use as a reference to delete the networks assigned to vlans
        to_be_deleted = set(self._data.get_vids()) - set(self._vlans_cache)

        vlan_networks = self.get_networks()
        # delete networks assigned to vlans(in the database) that does not exist in
        # current configs
        if to_be_deleted:
            self._networks_changed = True
            for vid in to_be_deleted:
                self._networks.delete(vlan_networks.get(str(vid)))

        # add or update the current vids in the database
        self._data.add_vids(
            [(vid, v.tenant) for vid, v in self._vlans_cache.items() if vid < 4000]
        )

    def _delete_networks(self):
        for cidr in list(self.get_networks()):
            self._vlans_network_cache[cidr].delete()
            del self._vlans_network_cache[cidr]
