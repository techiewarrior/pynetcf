import random

from sortedcontainers import SortedList

import pyconfigvars.constants as C
from .network import Network
from ..resource import get_resource


class NetworkManager:
    "Create and manage NSoT networks"

    def __init__(self, site_id=None):

        # get API endpoint
        site_id, resource = get_resource(site_id, "networks")

        # cache resources
        self._networks_cache = {
            item["cidr"]: Network(nsot_obj=item) for item in resource.get()
        }

        self._parents = SortedList(
            [n for n in self._networks_cache.values() if not n.is_host],
            key=lambda x: x.size,
        )
        self._site_id = site_id

        # add private cidrs
        for cidr in C.PRIVATE_CIDRS:
            self.add(cidr, description="internal_network")

    def get(self, cidr=None):
        "return: list of `Network` or `Network`"
        if cidr:
            if self._networks_cache.get(cidr) is None:
                net = Network(cidr, site_id=self._site_id)
                print("Adding network %s" % cidr)
                self._add_temp(net)
            return self._networks_cache[cidr]
        return list(self._networks_cache.values())

    def add(self, cidr, post=True, **kwargs):
        "Post network in the server if not exist in cache else patch"

        try:
            net = self._networks_cache[cidr]
            if net.nsot_obj["attributes"] != kwargs:
                net.attributes = kwargs
                net.update()
        except KeyError:
            net = Network(cidr, site_id=self._site_id, **kwargs)
            self._add_temp(net)
            if post:
                net.update()

    def delete(self, cidr, force=False):
        "Delete network in the server as well as in cache"

        try:
            key = None
            if isinstance(cidr, Network):
                cidr.delete()
                key = cidr.cidr
            else:
                self._networks_cache[cidr].delete(force=force)
                key = cidr
            del self._networks_cache[key]
        except KeyError:
            return

    def get_children(self, cidr):
        "return: immediate subnets of the `Network`"

        return [net for net in self._networks_cache.values() if cidr == net.parent]

    def get_subnets(self, cidr):
        "return: all subnets of the `Network` including the grandchildren"
        subnets = []
        for subnet in self.get_children(cidr):
            subnets.append(subnet)
            for sub in self.get_subnets(subnet):
                subnets.append(sub)
        return subnets

    def get_ips(self, cidr):
        "return: all IP addresses the the `Network`"
        return [net for net in self.get_subnets(cidr) if net.nsot_obj["is_ip"]]

    def query(self, sortby=None, reverse=False, **kwargs):
        """
        Query `Network` get_dict() result based on kwargs or specific cidrs

        return: list of `Network`
        """
        # default result
        networks = list(self._networks_cache.values())

        if kwargs:
            # query get_dict() result based on kwargs param
            _networks = []
            for net in networks:
                query = []
                for k, v in kwargs.items():
                    value = net.get_dict().get(k)
                    query.append(value == v or v is True and value is not None)
                if all(query):
                    _networks.append(net)
        else:
            _networks = networks

        # sort results
        if sortby:
            return sorted(
                _networks,
                key=lambda x: x.get_dict().get(sortby, ""),
                reverse=reverse,
            )

        return _networks

    def iter_subnets(self, cidrs=None, prefixlen=None, is_random=True):
        """
        An Iterator of `Network` subnets.
        It raises a `StopIterator` if CIDR run out of subnets

        :param cidr: (optional) the CIDR to create subnets.
            Default(PRIVATE_CIDRS)
        :param prefixlen: (optional) the prefixlen of subnets.
            Default(23)
        :param is_random: (optional) `True` will shuffle the list of networks.
            Default(`True`)

        return: `Network`
        """

        msg = None

        if prefixlen is None:
            prefixlen = 23

        def _iter_subnets():
            nonlocal msg

            if cidrs is None:
                _cidrs = [self._networks_cache.get(c) for c in C.PRIVATE_CIDRS]
                if is_random:
                    random.shuffle(_cidrs)
            else:
                _cidrs = [self._networks_cache.get(c) for c in cidrs]

            for _cidr in _cidrs:
                if _cidr.prefixlen <= prefixlen:
                    # add message to StopIteration why the except occur
                    msg = "Run out of subnets, {}".format(_cidr, prefixlen)

                    # existing immediate subnets
                    existing = [n.cidr for n in self.get_children(_cidr)]
                    yield from _cidr.iter_subnets(
                        prefixlen, is_random=is_random, existing_subnets=existing
                    )

        subnets = _iter_subnets()
        while True:
            try:
                subnet = next(subnets)
                self._add_temp(subnet)
                yield subnet
            except StopIteration as e:
                e.args = (msg,)
                raise

    def iter_hosts(self, cidrs=None, is_random=True):
        """
        An Iterator of `Network` IP addresses.
        It raises a `StopIterator` if CIDR run out of subnets

        :param cidrs: (optional) the list of CIDR to create IP addresses.
            Default(PRIVATE_CIDRS)
        :param is_random: (optional) `True` will shuffle the list of networks.
            Default(`True`)

        return: `Network`
        """

        def _iter_hosts():

            if cidrs is None:
                _cidrs = [self._networks_cache[c] for c in C.PRIVATE_CIDRS]
                if is_random:
                    random.shuffle(_cidrs)
            else:
                _cidrs = [self._networks_cache[c] for c in cidrs]

            for cidr in _cidrs:
                existing = [n.cidr for n in self.get_ips(cidr)]
                yield from cidr.iter_hosts(
                    is_random=is_random, existing_ipaddrs=existing
                )

        hosts = _iter_hosts()
        while True:
            try:
                host = next(hosts)
                self._add_temp(host)
                yield host
            except StopIteration as err_exc:
                err_exc.args = ("'%s' has run out of IP addresses",)
                raise

    def _add_temp(self, net):
        """
        Add the `Network` in self._networks_cache
        """
        # set the network parent
        for parent in self._parents:
            if parent.contains(net):
                print("xSetting parent for %s %s" % (net, parent))
                net.parent = parent
                break
        # if Network is not an IP add to self._parent
        if not net.is_host:
            self._parents.add(net)
        self._networks_cache[net.cidr] = net

    def delete_all(self):
        "Delete all networks except private cidrs"
        for net in self._networks_cache.values():
            if net.cidr not in C.PRIVATE_CIDRS:
                net.delete(force=True)
