from ..api import _get_api_client
from ..attributes import Attributes
from .interface import Interface


class InterfaceManager:

    RESOURCE = "interfaces"
    NATURAL_KEY = "name_slug"
    _api = _get_api_client()
    _resources = _api(RESOURCE).get()

    def __init__(self, device):

        self._device = device
        self._attributes = Attributes(self.title)
        self._interfaces = {}

        self.update()

    def __call__(self, name, description=None, attributes=None):

        interface = self._resources.get(name)
        if interface is None:
            parent_id = None

            if child:
                try:
                    parent_id = self._resources[parent].id
                except KeyError:
                    data = Interface(parent, device=self._device).post()
                    parent_id = data["id"]
            interface = Interface(
                name,
                hostname=self._device.hostname,
                parent_id=parent_id,
                description=description,
                attributes=attributes,
            )
            self._resources[name] = interface
        return interface

    def __iter__(self):
        return (intf for intf in self._resources.values())

    @property
    def _model(self):
        return self.RESOURCE[:-1].title()

    @property
    def data(self):
        return {k: v.data for k, v in self._resources.items()}

    def add(self, interface):
        self._resources[interface.name] = interface

    def remove(self, name):
        try:
            interface = self._resources[name]
            interface.delete()
            del self._resources[name]
        except KeyError:
            return

    def get(self):
        for data in self._resources:
            hostname, iface_name = item[self.NATURAL_KEY].split(":")
            if hostname == self._device.hostname:
                interface = Interface(iface_name, self._device.hostname, data=item)
                self._resources[iface_name] = interface
