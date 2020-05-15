from random import shuffle

from netaddr import IPNetwork, IPSet, IPRange

from pynetcf.utils import get_logger
from ..resource import NSoTResource

logger = get_logger(__name__)

RESOURCE_NAME = "networks"


class Network:
    "A single NSoT network resource"

    def __init__(self, cidr=None, site_name=None, resource_obj=None, **kwargs):
        """
        Constructor

        The value from 'nsot_object['cidr']' is use as a 'cidr' when is given else
        the 'cidr' via param is use. Raises TypeError if both 'nsot_object' and
        'addr' is None or if 'cidr' not in CIDR or IP address string format.

        :param addr: CIDR or IP address in string format ex. 192.168.0.0/24,
            192.168.0.1, 192.168.0.0/32.
        :param endpoint: the NSoT resource API endpoint
        :param nsot_object: the NSoT resource object which a return dict from
            GET, POST, PATCH. If param is provided, this will assume that the resource
            is somehow exists in NSoT server
        :param check: 'True' will check if the resource truly exists in NSoT server
        :param kwargs: key/value pair of NSoT attributes of the networks resource,
            key must be a str and value of str or list depend on the attributes
            'multi' value. Key as the name of the attribute must created beforehand.
        """

        resource = NSoTResource(
            name=RESOURCE_NAME, site_name=site_name, resource_obj=resource_obj
        )

        cidr = resource.object.get("cidr", cidr)
        if cidr is None:
            raise TypeError("'Network' require a cidr via param or nsot_object")

        ipnetwork = IPNetwork(cidr)

        is_true_cidr = True
        parent = None

        # rewrite ipnetwork if provided 'cidr' via param is not a host address
        # ex. '192.168.0.1/24' will rewrite to '192.168.0.1/32'
        if ipnetwork.sort_key()[3]:
            parent = str(ipnetwork.cidr)
            ipnetwork = IPNetwork("%s/32" % ipnetwork.ip)
            is_true_cidr = False

        is_host = resource.object.get("is_ip", ipnetwork.prefixlen == 32)

        if resource_obj is None:
            resource.payload = {"cidr": str(ipnetwork), "attributes": kwargs}

        resource.natural_name = str(ipnetwork)

        self.resource = resource
        self.ipnetwork = ipnetwork
        self.is_host = is_host
        self.is_true_cidr = is_true_cidr
        self.parent = resource.object.get("parent") or parent
        self.state = self.resource.object.get("state")

        # self.assignment = None
        self.state_checked = False

        self._ip_prefix = None

        self._available_ipset = None
        self._existing = IPSet()

    @property
    def state(self):
        try:
            return self.resource.payload["state"]
        except KeyError:
            return self.resource.object.get("state")

    @state.setter
    def state(self, value):
        self.resource.payload["state"] = value

    @property
    def ip_range(self):
        return IPRange(self.ipnetwork.network, self.ipnetwork.broadcast)

    @property
    def group(self):
        return self.__str__().split(".")[0]

    @property
    def assignment(self):
        return self.resource.attributes.get("assignment")

    @assignment.setter
    def assignment(self, value):
        self.resource.add_attributes(assignment=value)

    # @property
    # def ip_prefix(self):
    #     if self.is_host:
    #         if self._ip_prefix is None:
    #             try:
    #                 if isinstance(self.parent, Network):
    #                     parent = self.parent.ipnetwork
    #                 else:
    #                     parent = IPNetwork(self.parent)
    #                 self._ip_prefix = IPNetwork(
    #                     "%s/%s" % (self.ipnetwork.ip, parent.prefixlen)
    #                 )
    #             except TypeError:
    #                 return self.ipnetwork
    #         return self._ip_prefix
    #     return self.ipnetwork

    def __repr__(self):
        return "Network({}.{})".format(*self.key())

    def __str__(self):
        return str(self.ipnetwork)

    def __getattr__(self, key):
        if self.resource.attributes.get(key) is None:
            raise AttributeError(
                "'%s' object has no attribute '%s'" % (self.__class__.__name__, key)
            )
        return self.resource.attributes[key]

    def __hash__(self):
        return hash(self.key())

    def key(self):
        return str(self.ipnetwork), self.resource.site_name

    def subnets_generator(
        self, prefixlen, random=False, reverse=False, existing_subnets=None
    ):
        """
        An Iterator of `Network` subnets

        :param prefixlen: the prefixlen of subnets to create
        :param random: `True` will shuffle the order of subnets.
        :param reverse: `True` will reverse the order of subnets
        :param existing_subnets:
            this will generate a unique subnets if existing_subnets is truly a
            subnet of this `Network`

        :return: `Network`
        """

        def ipnetwork_to_network_object(subnets):
            try:
                shuffle(subnets)
            except TypeError:
                pass

            if self.resource.exists():
                for subnet in subnets:
                    self._existing.add(subnet)
                    network = Network(subnet)
                    logger.info("[{}] yielded subnet: {}".format(self, network))
                    yield network
            else:
                logger.warning("%s does not yet exists in the NSoT server" % self)
                for subnet in subnets:
                    self._existing.add(subnet)
                    network = Network(subnet)
                    network.parent = self
                    logger.info("[{}] yielded subnet: {}".format(self, network))
                    yield network

        if self._available_ipset is None:
            if self.is_host:
                raise TypeError("Network '%' is a host" % self)

            if self.state == "reserved":
                raise TypeError("%s has already assigned hosts" % self)

            if prefixlen < self.ipnetwork.prefixlen:
                raise TypeError(
                    "Subnet prefix must be greater than the network being subnetted"
                    % self
                )

            self._available_ipset = IPSet(self.ipnetwork) - IPSet(existing_subnets)

        available_ipset = self._available_ipset - self._existing

        logger.info(
            "[{}] Starting subnets generator with param: prefixlen={}, random={}, "
            "reverse={}\nAvailable CIDRS: {}".format(
                self, prefixlen, random, reverse, available_ipset.iter_cidrs()
            )
        )

        def available_subnets():
            for cidr in available_ipset.iter_cidrs():
                for subnet in cidr.subnet(prefixlen):
                    yield subnet

        if self.ipnetwork.prefixlen == prefixlen:
            yield self
            return None

        if random:
            _available_subnets = available_subnets()
            try:
                while True:
                    subnets = [next(_available_subnets) for _ in range(1024)]
                    yield from ipnetwork_to_network_object(subnets)
                    available_ipset = available_ipset - IPSet(subnets)
                    subnets.clear()
            except StopIteration:
                remaining_subnets = [
                    subnet
                    for cidr in available_ipset.iter_cidrs()
                    for subnet in cidr.subnet(prefixlen)
                ]
                yield from ipnetwork_to_network_object(remaining_subnets)
        else:
            if reverse:
                cidrs = []
                for cidr in available_ipset.iter_cidrs():
                    prefix_diff = prefixlen - cidr.prefixlen
                    if prefix_diff > 11:
                        new_prefix = int(prefixlen - (prefix_diff / 2))
                        for subnet in cidr.subnet(new_prefix):
                            cidrs.append(subnet)
                    else:
                        cidrs.append(cidr)
                for cidr in reversed(cidrs):
                    reversed_subnets = reversed(list(cidr.subnet(prefixlen)))
                    yield from ipnetwork_to_network_object(reversed_subnets)
            else:
                yield from ipnetwork_to_network_object(available_subnets())

    def hosts_generator(self, random=False, reverse=False, existing_hosts=None):
        """
        An Iterator `Network` usable IP addresses

        :param random: `True` will shuffle the order of hosts addresses.
        :param reverse: `True` will reverse the order of hosts addresses
        :param existing_hosts:
            this will generate a unique host addresses if existing_hosts is truly a
            hosts belong to this `Network`

        :return: `Network`
        """

        def ipnetwork_to_network_object(hosts):
            try:
                shuffle(hosts)
            except TypeError:
                pass

            if self.resource.exists():
                for host in hosts:
                    network = Network("%s/32" % host)
                    logger.info("[{}] yielded host: {}".format(self, network))
                    self._existing.add(host)
                    yield network
            else:
                logger.warning("%s does not yet exists in the NSoT server" % self)
                for host in hosts:
                    network = Network("%s/32" % host)
                    network.parent = self
                    logger.info("[{}] yielded host: {}".format(self, network))
                    self._existing.add(host)
                    yield network

        if self._available_ipset is None:
            if self.is_host:
                raise TypeError("Network %s is a host" % self)

            if existing_hosts is None:
                existing_hosts = []

            # append the network and broadcast address to the existing IP hosts
            existing_hosts.extend([self.ipnetwork.network, self.ipnetwork.broadcast])

            # available_ipset = IPSet(self.ipnetwork) - IPSet(existing_hosts)
            # available_cidrs = available_ipset.iter_cidrs()
            self._available_ipset = IPSet(self.ipnetwork) - IPSet(existing_hosts)

        available_ipset = self._available_ipset - self._existing

        def available_hosts():
            for cidr in available_ipset.iter_cidrs():
                for host in cidr:
                    yield host

        if random:
            _available_hosts = available_hosts()
            try:
                while True:
                    hosts = [next(_available_hosts) for _ in range(1024)]
                    yield from ipnetwork_to_network_object(hosts)
                    available_ipset = available_ipset - IPSet(hosts)
                    hosts.clear()
            except StopIteration:
                remaining_hosts = [
                    host for cidr in available_ipset.iter_cidrs() for host in cidr
                ]
                yield from ipnetwork_to_network_object(remaining_hosts)
        else:
            if reverse:
                cidrs = []
                for cidr in available_ipset.iter_cidrs():
                    prefix_diff = self.ipnetwork.prefixlen - cidr.prefixlen
                    if prefix_diff > 11:
                        new_prefix = int(self.prefixlen - (prefix_diff / 2))
                        for subnet in cidr.subnet(new_prefix):
                            cidrs.append(subnet)
                    else:
                        cidrs.append(cidr)
                for cidr in reversed(cidrs):
                    reversed_hosts = reversed(list(cidr))
                    yield from ipnetwork_to_network_object(reversed_hosts)
            else:
                yield from ipnetwork_to_network_object(available_hosts())

    def post_update(self):
        """POST or UPDATE network in NSoT server"""
        if self.is_host:
            parent = self.parent
            # POST the parent network if not exists in the NSoT server
            try:
                if not parent.state_checked and not parent.resource.exists():
                    parent.state_checked = True
                    parent.state = "reserved"
                    parent.resource.post_update()
            except AttributeError:
                pass

        self.resource.payload["state"] = self.state
        self.resource.post_update()

    def delete(self, force=False):
        self.resource.payload = {}
        self.resource.delete(force=force)
