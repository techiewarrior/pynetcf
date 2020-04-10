# from ..interfaces.manager import InterfaceManager
from .resource import Resource


class Device(Resource):

    def __init__(self, hostname=None, nsot_data=None, **kwargs):

        super().__init__('devices')

        if not any([hostname, nsot_data]):
            raise ValueError("required either 'hostname' or 'nsot_data' argument")

        if nsot_data is None:
            try:
                self.nsot_data = self._api.devices(hostname).get()
            except HttpNotFoundError:
                self.nsot_data.hostname = hostname
                self.nsot_data.attributes = kwargs
                pass
        else:
            self.nsot_data = nsot_data

        self.attributes = kwargs

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.hostname)

    def __dir__(self):
        return super().__dir__() + self.dynamic_attrs + list(self.attributes)

    def get_dict(self):
        return {
            'hostname': self.hostname,
            **self.attributes
        }

    def post(self):
        if not self.exist:
            try:
                self.nsot_data = self._api.devices.post(self.nsot_data)
            except Exception as e:
                print(e.response.json()['error']['message'])

    def delete(self):
        if self.exist:
            try:
                return self._api.devices(self.id).delete()
            except Exception as e:
                print(e.response.json()['error']['message'])

    def patch(self):
        if self.changed and self.exist:
            try:
                return self._api.devices(self.id).patch(self.nsot_data)
            except Exception as e:
                print(e.response.json()['error']['message'])
