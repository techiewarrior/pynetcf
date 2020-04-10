import random
from netaddr import IPNetwork, IPSet

import pyconfigvars.constants as C
from ..resource import Resource


class Network(Resource):
    "A single NSoT `Network` resource"

    def __init__(self, addr=None, site_id=None, nsot_obj=None, **kwargs):
        """
        Constructor

        If both nsot_obj and addr param is provided the cidr in nsot_obj is the
        preferred addr to use. If both not provided raises TypeError

        :param addr: a CIDR or IP address string format ex. 192.168.0.0/24, 192.168.0.1
        :param kwargs: a key/value pair of NSoT attributes of the `Network`, key must
            be a str and value of str or list
        """
        super(Network, self).__init__("networks", site_id=site_id, nsot_obj=nsot_obj)

        # get the addr from nsot_obj
        addr = self.nsot_obj.get("cidr") if addr is None else addr
        if addr is None:
            raise TypeError("'Network' require a cidr or nsot_obj via param")

        net = IPNetwork(addr)
        parent = None

        if self.nsot_obj and net.prefixlen == 32:
            parent = self.nsot_obj["parent"]
        elif net.network != net.ip:
            parent = str(net.cidr)

        self.parent = parent
        self._ipnetwork = net

        # set the current payload
        self._payload = {"cidr": self.cidr, "attributes": kwargs}

        # getdict() placeholder
        self._data = {}

    @property
    def natural_name(self):
        return str(self._ipnetwork.cidr)

    @property
    def cidr(self):
        return str(self._ipnetwork.cidr)

    @property
    def network(self):
        return str(self._ipnetwork.network)

    @property
    def is_host(self):
        return self._ipnetwork.network != self._ipnetwork.ip or self.prefixlen == 32

    @property
    def prefixlen(self):
        return self._ipnetwork.prefixlen

    @property
    def size(self):
        return self._ipnetwork.size

    @property
    def gateway(self):
        if C.SVI_GATEWAY > 0:
            return "%s/%s" % (
                self._ipnetwork.network + C.SVI_GATEWAY,
                self.prefixlen,
            )
        elif C.SVI_GATEWAY < 0:
            return "%s/%s" % (
                self._ipnetwork.broadcast - C.SVI_GATEWAY,
                self.prefixlen,
            )

    def contains(self, other):
        return self._ipnetwork.__contains__(other._ipnetwork)

    def get_dict(self):

        if not self._changed and self._data:
            return self._data

        data = {
            "network": self.network,
            "subnet_mask": str(self._ipnetwork.netmask),
            "cidr": self.cidr,
            "prefixlen": self.prefixlen,
            "wildcard_mask": str(self._ipnetwork.hostmask),
        }

        if self.is_host and self.parent:
            parent = IPNetwork(self.parent)
            data.update(
                {
                    "ip": str(self._ipnetwork.ip),
                    "ip_prefix": "%s/%s" % (self._ipnetwork.ip, parent.prefixlen),
                    "prefixlen": parent.prefixlen,
                    "host_prefix": "%s/32" % self._ipnetwork.ip,
                    "cidr": self.parent,
                    "subnet_mask": str(parent.netmask),
                    "wildcard_mask": str(parent.hostmask),
                }
            )

        data.update(self.nsot_obj.get("attributes", {}))

        self._data = data
        self._changed = False
        return data

    def iter_subnets(self, prefixlen, is_random=True, existing_subnets=None):
        """
        An Iterator of `Network` subnets

        :param prefixlen: the prefixlen of subnets
        :param is_random: (optional) `True` will shuffle the list of networks.
            Default(`True`)
        :param existing_subnets: use to generate unique subnets base on given
            existing subnets

        :return: `Network`
        """

        def _iter_subnets(subnets):
            "Inner iterator of subnets"
            if is_random:
                list_subnets = list(subnets)
                random.shuffle(list_subnets)
            else:
                list_subnets = subnets
            for subnet in list_subnets:
                if subnet == self._ipnetwork:
                    yield self
                else:
                    yield Network(str(subnet))

        existing_ipset = IPSet(self._ipnetwork) - IPSet(existing_subnets)
        available_cidrs = existing_ipset.iter_cidrs()

        if prefixlen >= available_cidrs[-1].prefixlen:
            for cidr in available_cidrs:
                # Create a new prefix for large CIDR that require the smallest
                # subnet possible.
                # This is use if is_random param is `True` to able to shuffle the
                # list of subnets thus increase the performance for large network to
                # be subnetted
                # Ex. '10.0.0.0/8' cidr will create a new prefix of /19 to create a
                # /30 subnnet. Setting the threshold of 11 bits meaning
                # 30 - 8 == 22 > 11 then using a formula 30 - (30 - 8) / 2 = 19
                prefix_diff = prefixlen - cidr.prefixlen
                if prefix_diff > 11:
                    new_prefix = int(prefixlen - (prefix_diff / 2))
                    for subnet in cidr.subnet(new_prefix):
                        yield from _iter_subnets(subnet.subnet(prefixlen))
                else:
                    yield from _iter_subnets(cidr.subnet(prefixlen))

    def iter_hosts(self, is_random=True, existing_ipaddrs=None):
        """
        An Iterator `Network` IP addresses

        :param is_random: (optional) `True` will shuffle the list of networks.
            Default(`True`)
        """

        def _iter_hosts(cidr):
            "Inner iterator of IP addresses"
            if is_random:
                ipaddrs = list(cidr)
                random.shuffle(ipaddrs)
            else:
                ipaddrs = cidr
            for ipaddr in ipaddrs:
                yield Network(str(ipaddr))

        if self.is_host:
            yield self

        _existing_ipaddrs = IPSet(existing_ipaddrs)

        # add the network and broadcast address to make it will not include in
        # yielding ip addresses
        _existing_ipaddrs.update([self.network, self._ipnetwork.broadcast])

        # get available CIDRs
        available_cidrs = (IPSet(self._ipnetwork) - _existing_ipaddrs).iter_cidrs()

        for cidr in available_cidrs:
            if cidr.prefixlen <= 30:
                for subnet in cidr.subnet(30):
                    yield from _iter_hosts(subnet)
            else:
                yield from _iter_hosts(cidr)
