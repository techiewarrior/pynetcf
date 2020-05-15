from collections import defaultdict
from itertools import groupby

# from random import shuffle

from sortedcontainers import SortedList

import pynetcf.constants as C
from pynetcf.utils import get_logger
from pynetcf.utils.macaddr import MACAddressManager
from .network import Network
from ..base import NSoTResources, NSoTSiteResources


logger = get_logger(__name__)

RESOURCE_NAME = "networks"


class NSoTSiteNetworks(NSoTSiteResources):
    """Create and manage a single site of NSoT networks"""

    def __init__(self, site_name, resources, attributes):
        super(NSoTSiteNetworks, self).__init__(
            site_name=site_name,
            resources=resources,
            attributes=attributes,
            klass=Network,
        )

        # list of parent networks groupby first octet of IPv4 address and
        # sort by size of the network
        self._parents = {
            k: SortedList(
                [n for n in v if not n.is_host], key=lambda x: x.ipnetwork.size
            )
            for k, v in groupby(self._resources.values(), key=lambda x: x.group)
        }

        private_cidrs = []
        for cidr in C.PRIVATE_CIDRS:
            network = self._resources.get(cidr)
            if network is None:
                network = self.add(cidr, description="Internal network")
            private_cidrs.append(network)

        self._private_cidrs = private_cidrs
        self._mac_addrs = MACAddressManager()

        self._hosts_generators_cache = defaultdict(dict)
        self._subnets_generators_cache = defaultdict(dict)

    @property
    def mac_addrs(self):
        return self._mac_addrs

    def __call__(self, cidr):
        network = super(NSoTSiteNetworks, self).__call__(cidr)

        if network.parent is None:
            try:
                for parent in self._parents[network.group]:
                    if network.ipnetwork in parent.ipnetwork:
                        network.parent = parent
                        break
            except KeyError:
                pass
        else:
            if self._resources.get(network.parent) is None:
                parent = Network(network.parent)
                self._resources[str(parent)] = parent
                network.parent = parent

        if not network.is_host:
            try:
                self._parents[network.group].add(network)
            except KeyError:
                self._parents[network.group] = SortedList(
                    [network], key=lambda x: x.ipnetwork.size
                )

        return network

    def get_subnets(self, network):
        """Return the existing subnets of the network"""
        try:
            for subnet in self._parents[network.group]:
                if (
                    subnet.ipnetwork != network.ipnetwork
                    and subnet.ipnetwork in network.ipnetwork
                ):
                    yield subnet
        except KeyError:
            return None

    def get_hosts(self, network):
        """Return the existing IP host addresses of the network"""
        for _network in self._resources.values():
            if _network.is_host and _network.group == network.group:
                if _network.ipnetwork in network.ipnetwork:
                    yield _network

    def get_host(self, network, index):
        """Return a single IP host address based on index number"""
        if index > 0:
            host_index = index + 1
        else:
            host_index = index - 1
        str_ip = str(network.ipnetwork[host_index])
        return self.__call__(str_ip)

    def subnets_generator(
        self, cidr, prefixlen=None, random=False, reverse=False, is_existing=False
    ):
        """
        An Iterator of the network subnets. Raises a `StopIteration` if CIDR run out
        of subnets. The yield subnet is not automatcally POST in the NSoT server

        :param args: CIDR/s to create subnets. Accept as CIDR in string format or
            `Network`. Default(_private_cidrs)
        :param kwargs:
            prefixlen: the prefixlen of subnets to create. Default(C.DEFAULT_PREFIXLEN)
            random: shuffle the order of networks.
            reverse: reverse the order of networks.

        return: the subnet of the network
        """
        if prefixlen is None:
            prefixlen = C.DEFAULT_PREFIXLEN

        def _subnets_generator():
            if isinstance(cidr, Network):
                _cidr = cidr
            else:
                _cidr = self.get(cidr)

            if prefixlen < _cidr.ipnetwork.prefixlen:
                raise TypeError(
                    "Subnet prefix must be greater than the network being subnetted"
                )

            if not is_existing:
                if _cidr.ipnetwork.prefixlen <= prefixlen:
                    # add message to StopIteration why the except occur
                    # msg = "Run out of subnets, {}".format(cidr, prefixlen)

                    # existing immediate subnets
                    existing = [n.ipnetwork for n in self.get_subnets(_cidr)]

                    yield from _cidr.subnets_generator(
                        prefixlen=prefixlen,
                        random=random,
                        reverse=reverse,
                        existing_subnets=existing,
                    )
            else:
                yield from _cidr.subnets_generator(
                    prefixlen=prefixlen, random=random, reverse=reverse
                )

        subnets = _subnets_generator()
        while True:
            try:
                subnet = next(subnets)
                self._resources[str(subnet)] = subnet
                yield subnet
            except StopIteration as e:
                e.args = ("Network %s has run out of subnets" % cidr,)
                raise

    def hosts_generator(self, cidr, random=False, reverse=False, is_existing=False):
        """
        An Iterator of `Network` IP addresses. Raises a `StopIteration` if CIDR run
        out of IP Address. The yield `Network` object is not automatcally POST in
        the NSoT server

        :param args: CIDR/s to create IP addresses. Default(_private_cidrs)
        :param kwargs:
            random: shuffle the order of `Network`. Default(`False`)
            reverse: reverse the order of `Network`. Default(`False`)
        return: `Network`
        """

        def _hosts_generator():

            if isinstance(cidr, Network):
                _cidr = cidr
            else:
                _cidr = self.get(cidr)

            if not is_existing:
                existing = [n.ipnetwork for n in self.get_hosts(_cidr)]
                yield from _cidr.hosts_generator(
                    random=random, reverse=reverse, existing_hosts=existing
                )
            else:
                yield from _cidr.hosts_generator(random=random, reverse=reverse)

        hosts = _hosts_generator()
        while True:
            try:
                host = next(hosts)
                self._resources[str(host)] = host
                yield host
            except StopIteration as e:
                e.args = ("Network %s has run out of usable IP addresses" % cidr,)
                raise

    def get_hosts_generator(self, cidr, random=False, reverse=False):
        kw = (random, reverse)
        if self._hosts_generators_cache.get(cidr) is None:
            print("[%s] Creating hosts generator" % cidr)
            self._hosts_generators_cache[cidr][kw] = self.hosts_generator(
                cidr, random=random, reverse=reverse
            )
        elif self._hosts_generators_cache[cidr].get(kw) is None:
            print("[%s] Creating hosts generator with new param" % cidr)
            self._hosts_generators_cache[cidr][kw] = self.hosts_generator(
                cidr, random=random, reverse=reverse, is_existing=True
            )
        else:
            print("[%s] using cache hosts generator" % cidr)
        return self._hosts_generators_cache[cidr][kw]

    def get_subnets_generator(
        self, cidr, prefixlen=None, random=False, reverse=False
    ):
        kw = (prefixlen, random, reverse)
        if self._subnets_generators_cache.get(cidr) is None:
            print("[%s] Creating subnets generator" % cidr)
            self._subnets_generators_cache[cidr][kw] = self.subnets_generator(
                cidr, prefixlen=prefixlen, random=random, reverse=reverse
            )
        elif self._subnets_generators_cache[cidr].get(kw) is None:
            print("[%s] Creating subnets generator with new param" % cidr)
            self._subnets_generators_cache[cidr][kw] = self.subnets_generator(
                cidr,
                prefixlen=prefixlen,
                random=random,
                reverse=reverse,
                is_existing=True,
            )
        else:
            print("[%s] using cache subnets generator" % cidr)
        return self._subnets_generators_cache[cidr][kw]

    def delete(self, network, force=False):
        str_net = str(network)
        try:
            self._resources[str_net].delete()
            del self._resources[str_net]
        except KeyError:
            return None


class NSoTNetworks:
    """Manage NSoT networks"""

    _resources = NSoTResources(RESOURCE_NAME, Network)
    _sites = {}

    @classmethod
    def sites(cls, site_name):

        if site_name is None:
            site_name = cls._resources.default_sitename()

        if cls._sites.get(site_name) is None:
            logger.info("Initialising site '%s'" % site_name)
            site = cls._resources.sites(site_name)
            cls._sites[site_name] = NSoTSiteNetworks(
                site_name=site_name,
                resources=site.resources,
                attributes=site.attributes,
            )
        return cls._sites[site_name]

    # @classmethod
    # def filter(cls, **kwargs):
    #     try:
    #         yield from cls._resources.filter(**kwargs)
    #     except StopIteration:
    #         return None
