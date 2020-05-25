from collections import defaultdict
from random import shuffle

# from itertools import groupby

from netaddr import IPNetwork, IPSet
from sortedcontainers import SortedList

from pynetcf.utils.logger import get_logger
from pynetcf.nsot.resource import Resource, ResourceManager

logger = get_logger(__name__)


class Manager(ResourceManager):
    def assign_parent(self, obj):
        parents = self._parents.get(obj.ip_group)
        if parents:
            for parent in reversed(parents):
                if obj.prefix_length > parent.prefix_length:
                    if obj.is_subnet_of(parent):
                        return parent
        else:
            if obj.is_ip:
                raise ValueError(f"IPAddress {obj} needs a parent network")

    def add_to_parents(self, obj):
        if getattr(self, "_parents", None) is None:
            self._parents = {}

        group = obj.ip_group

        if self._parents.get(group) is None:
            self._parents[group] = SortedList([], key=lambda x: x.sort_key())

        self._parents[group].add(obj)

    def get_hosts_generator(self, obj_key, args):

        obj = self._objects.get(obj_key) or Network(*obj_key)

        if getattr(self, "_hosts_generators_cache", None) is None:
            self._hosts_generators_cache = defaultdict(dict)

        if self._hosts_generators_cache.get(obj_key) is None:
            logger.info(f"{obj_key} Initialise new hosts generator")
            self._hosts_generators_cache[obj_key][args] = obj.hosts_generator(*args)

        elif self._hosts_generators_cache[obj_key].get(args) is None:
            logger.info(
                f"{repr(obj_key)} Initialise hosts generator with new param {args}"
            )
            self._hosts_generators_cache[obj_key] = {
                args: obj.hosts_generator(*args)
            }

        else:
            logger.info(f"{obj_key} using cache hosts generator")

        return self._hosts_generators_cache[obj_key][args]


class Network(Resource):
    """A single Network"""

    # instance arguments
    _args = ("cidr", "site_id")
    # sort the existing NSoT resource objects before creating an instance
    # use in class customisation in parent __init_subclass__
    _sort_objects_by = "prefix_length"

    manager = Manager(parents=None, hosts_generators_cache=None)

    @classmethod
    def _check_args(cls, attrs, **kwargs):
        """Manipulate resource specific arguments before instance creation"""
        cidr = attrs.cidr
        ipnet = IPNetwork(cidr)

        if ipnet.sort_key()[-1]:
            cidr = str(ipnet.ip)
            ipnet = IPNetwork(ipnet.ip)

        if ipnet.prefixlen == 32:
            attrs.is_ip = True

        attrs.update(
            {
                "_ipnet": ipnet,
                "_sorted_subnets": SortedList([], key=lambda x: x.sort_key()),
                "cidr": cidr,
                "prefix_length": ipnet.prefixlen,
                "ip_group": ipnet.ip.words[:-2],
                "value": ipnet.value,
                "size": ipnet.size,
                "sort_key": ipnet.sort_key,
            }
        )

    @classmethod
    def _pre_init(cls, obj):
        """Manipulate specific resource instance attributes before returning"""

        if not obj.is_ip:
            cls.manager.add_to_parents(obj)

        if obj.parent:
            parent_key = obj.parent, obj.site_id
            parent = cls.manager._objects.get(parent_key) or cls(*parent_key)
        else:
            parent = cls.manager.assign_parent(obj)

        try:
            prefix_length = obj.prefix_length

            parent._sorted_subnets.add(obj)
            if obj.is_ip:
                host_num = obj.value - parent.value
                obj._attrs.is_usable = host_num > 0 and host_num < parent.size
                prefix_length = parent.prefix_length
        except AttributeError:
            pass

        obj._attrs.update({"parent": parent, "prefix_length": prefix_length})

    @property
    def assignment(self):
        "Return the name of the network assignment"
        try:
            return self.attributes["assignment"]
        except KeyError:
            return self._payload.get("attributes", {}).get("assignment")

    @assignment.setter
    def assignment(self, value):
        self.add_attributes(assignment=value)

    def update_post(self):
        """POST or UPDATE interface in NSoT server"""
        if self.is_ip:
            parent = self.parent
            parent.state = "reserved"
            # POST the parent network if not exists in the NSoT server
            if not parent.exists():
                # update the state of the parent network to reserved meaning
                # the network has already assigned hosts
                parent.update_post()

        super().update_post()

    def delete(self, force=False):
        """
        DELETE interface in NSoT server
        :param force: `True` will also delete all the subnets of this network
        """
        if force:
            # if this network is a parent delete all its subnets
            for subnet in self._sorted_subnets:
                subnet.delete(force=True)

        super().delete()

    def is_subnet_of(self, parent):
        """Return `True` if this network is subnet of parent
        :param parent (Network): the Network object
        """
        return self.value - parent.value < parent.size

    def hosts(self):
        "Generator that yield the IP host address in this network"
        for subnet in self._sorted_subnets:
            if subnet.is_ip and subnet.state != "orphaned":
                yield subnet

    def subnets(self, all=False):
        "Generator that yield the immediate subnets of this network"
        if self.state == "reserved":
            return None

        for subnet in self._sorted_subnets:
            if not subnet.is_ip:
                if all:
                    yield from subnet.subnets(all=True)
                yield subnet

    def subnets_generator(self, prefixlen, random=False, reverse=False, strict=True):
        """
        A subnets generator
        :param prefixlen (int): the prefixlen of subnets to create
        :param random (bool): `True` will shuffle the order of subnets.
        :param reverse (bool): `True` will reverse the order of subnets
        :param strict (bool): 'True' by default will raise to error if
            the state of this network is `reserved` meaning that there is
            already have assigned hosts. Same with if this network overlaps
            with parent network which state is `reserved`. `False` will create
            a subnet of this network without error, and will reparent the subnets.
        :yield: `Network`
        """

        if self.is_ip:
            raise TypeError(f"Network '{self}' is a host")

        if strict:
            try:
                if self.parent.state == "reserved":
                    raise ValueError(
                        f"Parent network {self.parent} has already assigned hosts"
                    )
            except AttributeError:
                pass

            if self.state == "reserved":
                raise TypeError(f"{self} has already assigned hosts")

        _prefixlen = self.prefix_length

        if prefixlen < _prefixlen:
            raise ValueError(f"New prefix must be greater {_prefixlen}")

        if prefixlen == _prefixlen:
            yield self
            raise None

        global_ipset = IPSet(self._ipnet) - IPSet(
            [s._ipnet for s in self.subnets(all=True)]
        )

        def to_network(subnets, is_shuffle=False):
            if is_shuffle:
                shuffle(subnets)

            for subnet in subnets:
                yield Network(str(subnet), self.site_id)

        def unique_subnets():
            for cidr in global_ipset.iter_cidrs():
                yield from cidr.subnet(prefixlen)

        def _subnets_generator(ipset):
            if random:
                try:
                    subnets = unique_subnets()
                    while True:
                        subnet_chunk = [next(subnets) for _ in range(1024)]
                        yield from to_network(subnet_chunk, True)
                        ipset = ipset - IPSet(subnet_chunk)
                        subnet_chunk.clear()
                except StopIteration:
                    yield from to_network(
                        [s for c in ipset.iter_cidrs() for s in c.subnet(prefixlen)],
                        True,
                    )
            elif reverse:
                cidrs = []
                for cidr in ipset.iter_cidrs():
                    prefix_diff = prefixlen - cidr.prefixlen
                    if prefix_diff > 11:
                        new_prefix = int(prefixlen - (prefix_diff / 2))
                        for subnet in cidr.subnet(new_prefix):
                            cidrs.append(subnet)
                    else:
                        cidrs.append(cidr)
                for cidr in reversed(cidrs):
                    subnets = list(cidr.subnet(prefixlen))
                    yield from to_network(reversed(subnets))
            else:
                yield from to_network(unique_subnets())

        subnets = _subnets_generator(global_ipset)

        try:
            while True:
                yield next(subnets)
        except StopIteration as e:
            e.args = (f"Network {self} run out of subnets",)
            raise

    def hosts_generator(self, random=False, reverse=False):
        """
        A hosts generator

        :param random (bool): `True` will shuffle the order of hosts addresses.
        :param reverse (bool): `True` will reverse the order of hosts addresses
        :yield: `Network`
        """

        if self.is_ip:
            raise TypeError(f"Network {self} is a host")

        _ipnet = self._ipnet
        _prefixlen = self.prefix_length

        existing_hosts = IPSet([s._ipnet for s in self.hosts()])
        existing_hosts.update([_ipnet.network, _ipnet.broadcast])

        global_ipset = IPSet(_ipnet) - existing_hosts

        def to_network(hosts, is_shuffle=False):
            if is_shuffle:
                shuffle(hosts)

            for host in hosts:
                yield Network(f"{host}/32", self.site_id)

        def unique_hosts():
            for cidr in global_ipset.iter_cidrs():
                for host in cidr:
                    yield host

        def _hosts_generator(ipset):
            if random:
                try:
                    hosts = unique_hosts()
                    while True:
                        hosts_chunk = [next(hosts) for _ in range(1024)]
                        yield from to_network(hosts_chunk, True)
                        ipset = ipset - IPSet(hosts_chunk)
                        hosts_chunk.clear()
                except StopIteration:
                    yield from to_network(
                        [h for c in ipset.iter_cidrs() for h in c], True
                    )
            elif reverse:
                cidrs = []
                for cidr in ipset.iter_cidrs():
                    prefix_diff = _prefixlen - cidr.prefixlen
                    if prefix_diff > 11:
                        new_prefix = int(_prefixlen - (prefix_diff / 2))
                        for subnet in cidr.subnet(new_prefix):
                            cidrs.append(subnet)
                    else:
                        cidrs.append(cidr)
                for cidr in reversed(cidrs):
                    yield from to_network(reversed(list(cidr)))
            else:
                yield from to_network(unique_hosts())

        ips = _hosts_generator(global_ipset)

        try:
            while True:
                ip = next(ips)
                if ip.is_usable:
                    yield ip
        except StopIteration as e:
            e.args = (f"Network {self} run out of hosts",)
            raise


if __name__ == "__main__":

    import pprint

    for network in Network.manager.get():

        print("Network:", network, "\n")
        pprint.pprint(network.__dict__, depth=4)

        # try:
        #     subnets = network.subnets_generator(30)
        #     for r in range(2):
        #         print("Subnets:", next(subnets))
        # except (TypeError, ValueError):
        #     print("Caught error", network)
        #
        # try:
        #     hosts = network.hosts_generator()
        #     for r in range(2):
        #         print("Hosts:", next(subnets))
        # except (TypeError, ValueError):
        #     print("Caught error", network)


# class Network(Resource):
#     "A single NSoT network resource"
#
#     def __init__(self, cidr=None, site_name=None, nsot_object=None, **kwargs):
#         """
#         Constructor
#
#         The value from 'nsot_object['cidr']' is use as a 'cidr' when is given else
#         the 'cidr' via param is use. Raises TypeError if both 'nsot_object' and
#         'addr' is None or if 'cidr' not in CIDR or IP address string format.
#
#         :param addr: CIDR or IP address in string format ex. 192.168.0.0/24,
#             192.168.0.1, 192.168.0.0/32.
#         :param endpoint: the NSoT resource API endpoint
#         :param nsot_object: the NSoT resource object which a return dict from
#             GET, POST, PATCH. If param is provided, this will assume that the resource
#             is somehow exists in NSoT server
#         :param check: 'True' will check if the resource truly exists in NSoT server
#         :param kwargs: key/value pair of NSoT attributes of the networks resource,
#             key must be a str and value of str or list depend on the attributes
#             'multi' value. Key as the name of the attribute must created beforehand.
#         """
#
#         super(Network, self).__init__(site_name=site_name, nsot_object=nsot_object)
#
#         if nsot_object is None:
#             if cidr is None:
#                 raise TypeError(
#                     "Require a cidr via param if nsot_object is not provided"
#                 )
#
#             ipnetwork = IPNetwork(cidr)
#             parent = None
#
#             # rewrite ipnetwork if provided 'cidr' via param is usable IP address
#             # address ex. '192.168.0.1/24' will rewrite to '192.168.0.1/32'
#             if ipnetwork.sort_key()[3]:
#                 parent = str(ipnetwork.cidr)
#                 ipnetwork = IPNetwork(ipnetwork.ip)
#             is_host = ipnetwork.prefixlen == 32
#             self._payload = {"cidr": str(ipnetwork), "attributes": kwargs}
#         else:
#             cidr = self._nsot_object.get("cidr")
#             ipnetwork = IPNetwork(cidr)
#             parent = self._nsot_object.get("parent")
#             is_host = self._nsot_object.get("is_ip")
#
#         self.ipnetwork = ipnetwork
#         self.is_host = is_host
#         self.parent = parent
#         self.state_checked = False
#
#         self._available_ipset = None
#         self._existing = IPSet()
#         self._ipset = IPSet(ipnetwork)
#
#     @property
#     def state(self):
#         try:
#             return self._payload["state"]
#         except KeyError:
#             return self._nsot_object.get("state")
#
#     @state.setter
#     def state(self, value):
#         self._payload["state"] = value
#
#     @property
#     def assignment(self):
#         return self.attributes.get("assignment")
#
#     @assignment.setter
#     def assignment(self, value):
#         self._add_attributes(assignment=value)
#
#     def base_group(self):
#         return str(self.ipnetwork).split(".")[0]
#
#     def key(self):
#         return str(self.ipnetwork), self.site_name
#
#     def subnets_generator(
#         self, prefixlen, random=False, reverse=False, existing_subnets=None
#     ):
#         """
#         An Iterator of `Network` subnets
#
#         :param prefixlen: the prefixlen of subnets to create
#         :param random: `True` will shuffle the order of subnets.
#         :param reverse: `True` will reverse the order of subnets
#         :param existing_subnets:
#             this will generate a unique subnets if existing_subnets is truly a
#             subnet of this `Network`
#
#         :return: `Network`
#         """
#
#         def ipnetwork_to_network_object(subnets):
#             try:
#                 shuffle(subnets)
#             except TypeError:
#                 pass
#
#             if self.exists():
#                 for subnet in subnets:
#                     self._existing.add(subnet)
#                     network = Network(subnet)
#                     logger.info("[{}] yielded subnet: {}".format(self, network))
#                     yield network
#             else:
#                 logger.warning("%s does not yet exists in the NSoT server" % self)
#                 for subnet in subnets:
#                     self._existing.add(subnet)
#                     network = Network(subnet)
#                     network.parent = self
#                     logger.info("[{}] yielded subnet: {}".format(self, network))
#                     yield network
#
#         if self._available_ipset is None:
#             if self.is_host:
#                 raise TypeError("Network '%' is a host" % self)
#
#             if self.state == "reserved":
#                 raise TypeError("%s has already assigned hosts" % self)
#
#             if prefixlen < self.ipnetwork.prefixlen:
#                 raise TypeError(
#                     "Subnet prefix must be greater than the network being subnetted"
#                     % self
#                 )
#
#             self._available_ipset = self._ipset - IPSet(existing_subnets)
#
#         available_ipset = self._available_ipset - self._existing
#
#         logger.info(
#             "[{}] Starting subnets generator with param: prefixlen={}, random={}, "
#             "reverse={}\nAvailable CIDRS: {}".format(
#                 self, prefixlen, random, reverse, available_ipset.iter_cidrs()
#             )
#         )
#
#         def available_subnets():
#             for cidr in available_ipset.iter_cidrs():
#                 for subnet in cidr.subnet(prefixlen):
#                     yield subnet
#
#         if self.ipnetwork.prefixlen == prefixlen:
#             yield self
#             return None
#
#         if random:
#             _available_subnets = available_subnets()
#             try:
#                 while True:
#                     subnets = [next(_available_subnets) for _ in range(1024)]
#                     yield from ipnetwork_to_network_object(subnets)
#                     available_ipset = available_ipset - IPSet(subnets)
#                     subnets.clear()
#             except StopIteration:
#                 remaining_subnets = [
#                     subnet
#                     for cidr in available_ipset.iter_cidrs()
#                     for subnet in cidr.subnet(prefixlen)
#                 ]
#                 yield from ipnetwork_to_network_object(remaining_subnets)
#         else:
#             if reverse:
#                 cidrs = []
#                 for cidr in available_ipset.iter_cidrs():
#                     prefix_diff = prefixlen - cidr.prefixlen
#                     if prefix_diff > 11:
#                         new_prefix = int(prefixlen - (prefix_diff / 2))
#                         for subnet in cidr.subnet(new_prefix):
#                             cidrs.append(subnet)
#                     else:
#                         cidrs.append(cidr)
#                 for cidr in reversed(cidrs):
#                     reversed_subnets = reversed(list(cidr.subnet(prefixlen)))
#                     yield from ipnetwork_to_network_object(reversed_subnets)
#             else:
#                 yield from ipnetwork_to_network_object(available_subnets())
#
#     def hosts_generator(self, random=False, reverse=False, existing_hosts=None):
#         """
#         An Iterator `Network` usable IP addresses
#
#         :param random: `True` will shuffle the order of hosts addresses.
#         :param reverse: `True` will reverse the order of hosts addresses
#         :param existing_hosts:
#             this will generate a unique host addresses if existing_hosts is truly a
#             hosts belong to this `Network`
#
#         :return: `Network`
#         """
#
#         def ipnetwork_to_network_object(hosts):
#             try:
#                 shuffle(hosts)
#             except TypeError:
#                 pass
#
#             if self.exists():
#                 for host in hosts:
#                     network = Network("%s/32" % host)
#                     logger.info("[{}] yielded host: {}".format(self, network))
#                     self._existing.add(host)
#                     yield network
#             else:
#                 logger.warning("%s does not yet exists in the NSoT server" % self)
#                 for host in hosts:
#                     network = Network("%s/32" % host)
#                     network.parent = self
#                     logger.info("[{}] yielded host: {}".format(self, network))
#                     self._existing.add(host)
#                     yield network
#
#         if self._available_ipset is None:
#             if self.is_host:
#                 raise TypeError("Network %s is a host" % self)
#
#             if existing_hosts is None:
#                 existing_hosts = []
#
#             # append the network and broadcast address to the existing IP hosts
#             existing_hosts.extend([self.ipnetwork.network, self.ipnetwork.broadcast])
#
#             # available_ipset = IPSet(self.ipnetwork) - IPSet(existing_hosts)
#             # available_cidrs = available_ipset.iter_cidrs()
#             self._available_ipset = self._ipset - IPSet(existing_hosts)
#
#         available_ipset = self._available_ipset - self._existing
#
#         def available_hosts():
#             for cidr in available_ipset.iter_cidrs():
#                 for host in cidr:
#                     yield host
#
#         if random:
#             _available_hosts = available_hosts()
#             try:
#                 while True:
#                     hosts = [next(_available_hosts) for _ in range(1024)]
#                     yield from ipnetwork_to_network_object(hosts)
#                     available_ipset = available_ipset - IPSet(hosts)
#                     hosts.clear()
#             except StopIteration:
#                 remaining_hosts = [
#                     host for cidr in available_ipset.iter_cidrs() for host in cidr
#                 ]
#                 yield from ipnetwork_to_network_object(remaining_hosts)
#         else:
#             if reverse:
#                 cidrs = []
#                 for cidr in available_ipset.iter_cidrs():
#                     prefix_diff = self.ipnetwork.prefixlen - cidr.prefixlen
#                     if prefix_diff > 11:
#                         new_prefix = int(self.prefixlen - (prefix_diff / 2))
#                         for subnet in cidr.subnet(new_prefix):
#                             cidrs.append(subnet)
#                     else:
#                         cidrs.append(cidr)
#                 for cidr in reversed(cidrs):
#                     reversed_hosts = reversed(list(cidr))
#                     yield from ipnetwork_to_network_object(reversed_hosts)
#             else:
#                 yield from ipnetwork_to_network_object(available_hosts())
#
#     def post_update(self):
#         """POST or UPDATE network in NSoT server"""
#         if self.is_host:
#             parent = self.parent
#             # POST the parent network if not exists in the NSoT server
#             try:
#                 if not parent.state_checked and not parent.exists():
#                     parent.state_checked = True
#                     parent.state = "reserved"
#                     parent.resource.post_update()
#             except AttributeError:
#                 pass
#
#         self.payload["state"] = self.state
#         self.post_update()
