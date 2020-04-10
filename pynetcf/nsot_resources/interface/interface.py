from .resource import Resource


class Interface(Resource):

    def __init__(
        self,
        name=None,
        device=None,
        description=None,
        addresses=None,
        attributes=None,
        nsot_data=None,
    ):

        super().__init__(self.RESOURCE)

        self.nsot_data = nsot_data
        self.name = name
        self.device = device
        self.description = description
        self.addresses = addresses
        self.attributes = attributes

        self._parent = None

    def _getName(self):
        return self.nsot_data.get('name')

    def _setName(self, name):
        self._parent = self._get_parent(name)
        if name and name != self._getname():
            self.nsot_data.update_value() = {'name': name}

    def _delName(self):
        del self.nsot_data

    name = property(_getName, _setName, _delName)

    def _getDesc(self):
        return self.nsot_data.get('description')

    def _setDesc(self, description):
        if description and description != self._getDesc():
            self.nsot_data

    def _delDesc(self):
        self.nsot_data.
        try:
            parent, child = name.split('.')
            return parent
        except ValueError:
            return


#     def __repr__(self):
#         return '%s(%s, %s)' % (self.__class__.__name__, self.name, self._hostname)
#
#     @property
#     def device(self):
#         return self._device
#
#     @device.setter
#     def device(self, device):
#         if device is not None:
#             self._hostname = device.hostname
#             device.interfaces.add(interface=self)
#         self._device = device
#
#     @property
#     def attributes(self):
#         if self._attributes is None:
#             return {}
#         return self._attributes
#
#     @attributes.setter
#     def attributes(self, attributes):
#
#         def is_changed(val1, val2):
#             if not val1 and val2 or val1 and not val2:
#                 return True
#             elif all([isinstance(val1, list), isinstance(val2, list)]):
#                 if set(val1) != set(val2):
#                     return True
#                 return False
#             elif val1 != val2:
#                 return True
#
#         if attributes and self._exist:
#             attrs = {}
#             for key, value in attributes.items():
#                 if is_changed(self.data['attributes'].get(key), value):
#                     if value:
#                         attrs[key] = value
#                         break
#             if attrs:
#                 self.data['attributes'] = attrs
#                 self._changed = True
#             for key, value in attributes.items():
#                 if key not in self.DYNAMIC_ATTRS:
#                     self.__dict__[key] = value
#         self._attributes = attributes
#
#     @property
#     def data(self):
#         return self._data
#
#     @data.setter
#     def data(self, data):
#         if data:
#             for attr in self.DYNAMIC_ATTRS:
#                 self.__dict__[attr] = data.get(attr)
#             if data['attributes']:
#                 for key, value in data['attributes'].items():
#                     if key not in self.DYNAMIC_ATTRS:
#                         self.__dict__[key] = value
#             self._exist = True
#         self._data = data
#
#     @property
#     def description(self):
#         if self._description is None:
#             return ''
#         return self._description
#
#     @description.setter
#     def description(self, description):
#         try:
#             if description and description != self.data['description']:
#                 self.data['description'] = description
#                 self._changed = True
#         except TypeError:
#             pass
#
#     @property
#     def name_slug(self):
#         return '%s:%s' % (self._hostname, self.name)
#
#     def assign_address(self, address):
#         try:
#             if address not in self.data['addresses']:
#                 self.data['addresses'].append(address)
#                 self._changed = True
#         except TypeError:
#             pass
#
#     def exist(self):
#         return self._exist
#
    def post(self):
        try:
            self.nsot_data = self._api.interfaces.post(self.nsot_data)
        except Exception as e:
            print(e.response.json())

#
#     def delete(self):
#         if self._exist:
#             try:
#                 for addr in self.addresses:
#                     self._api.networks(addr).delete()
#             except Exception:
#                 pass
#             try:
#                 return self._api.interfaces(self.id).delete()
#             except Exception as e:
#                 print(e.response.json())
#         else:
#             return False
#
#     def patch(self):
#         if self._changed:
#             try:
#                 return self._api.interfaces(self.id).patch(self.data)
#             except Exception as e:
#                 print(e.response.json())
#         else:
#             return False
#
#     # def get_assignments(self):
#     #     if self._exist:
#     #         try:
#     #             return self._api.interfaces(self.id).assignments.get()
#     #         except Exception as e:
#     #             print(e.response.json())
#     #     else:
#     #         return False
#     #
#     # def get_networks(self):
#     #     if self._exist:
#     #         try:
#     #             return self._api.interfaces(self.id).networks.get()
#     #         except Exception as e:
#     #             print(e.response.json())
#     #     else:
#     #         return False
