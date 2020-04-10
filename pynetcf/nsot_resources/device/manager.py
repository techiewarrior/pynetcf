import pyconfigvars.constant as C

from pyconfigvars.ansible import Inventory
from pyconfigvars.nsot_api import _get_api_client
from pyconfigvars.resources.device import Device

RESOURCE = C.RESOURCE


class DeviceManager:

    _api = _get_api_client()

    def __init__(self):

        self._ansible_inventory = Inventory()
        self._attributes = Attributes(RESOURCE["name"])
        self._devices = {}

        self.crude()

    def __call__(self, hostname):
        try:
            return self._devices[hostname]
        except KeyError:
            return Device(hostname)

    def __iter__(self):
        return (dev for dev in self._devices.values())

    def __len__(self):
        return len(self._devices)

    def get(self, **kwargs):
        return [
            {"hostname": device.hostname, **device.attributes}
            for device in self._devices.values()
        ]

    def crude(self):

        for nsot_data in self._api(C.RESOURCE["name"]).get():
            self._devices[nsot_data[C.RESOURCE["naturalKey"]]] = Device(
                nsot_data=nsot_data
            )

        ansible_hosts = set(self._ansible_inventory.hosts())
        for hostname in ansible_hosts:
            attributes = self._get_attributes(hostname)
            self._attributes.check(attributes)
            try:
                device = self._devices[hostname]
                device.attributes = attributes
                if device.changed:
                    device.patch()
            except KeyError:
                device = Device(hostname, **attributes)
                device.post()
            self._devices[hostname] = device

        for hostname in set(self._devices) - ansible_hosts:
            self._devices[hostname].delete()
            del self._devices[hostname]

    def _get_attributes(self, hostname):

        groups = sorted(self._ansible_inventory.get_groups(hostname))
        parent_groups = list(
            {p for g in groups for p in self._ansible_inventory.get_parents(g)}
        )
        try:
            mgmt_hwaddr = self._ansible_inventory.hostvars[hostname]["mgmt_hwaddr"]
        except KeyError:
            mgmt_hwaddr = None

        network_os = self._ansible_inventory.hostvars[hostname]["ansible_network_os"]

        attrs = {
            "groups": groups,
            "parent_groups": parent_groups,
            "mgmt_hwaddr": mgmt_hwaddr,
            "network_os": network_os,
        }

        return {k: v for k, v in attrs.items() if v}
