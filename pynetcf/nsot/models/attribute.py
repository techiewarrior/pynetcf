from pynetcf.utils.logger import get_logger
from ..client import NSoTClient, nsot_request


CONSTRAINTS = ["pattern", "valid_values", "allow_empty"]
RESOURCE_NAME = "attributes"

logger = get_logger(__name__)


class Attribute:
    """A single NSoT `Attribute` resource"""

    def __init__(
        self,
        resource_name=None,
        name=None,
        site_name=None,
        nsot_object=None,
        **kwargs
    ):

        payload = {}

        if nsot_object is None:
            if site_name is None:
                site_name = NSoTClient.default_site()[1]
            else:
                site_id = site_id = NSoTClient.get_siteid(site_name)
            nsot_object = {}
            payload = {
                "multi": kwargs.get("multi", False),
                "resource_name": resource_name,
                "description": kwargs.get("description", ""),
                "display": kwargs.get("display", True),
                "required": kwargs.get("required", False),
                "constraints": {
                    "pattern": kwargs.get("pattern", ""),
                    "valid_values": kwargs.get("valid_values", []),
                    "allow_empty": kwargs.get("allow_empty", False),
                },
                "name": name,
            }
        else:
            site_id = nsot_object["site_id"]
            site_name = NSoTClient.get_sitename(site_id)

        resource_name = nsot_object.get("resource_name") or resource_name
        name = nsot_object.get("name") or name

        if not all([resource_name, name]):
            raise ValueError(
                "Reqiure 'resource_name' and 'name' via param or nsot_object"
            )

        self._resource = getattr(NSoTClient.resource.sites(site_id), RESOURCE_NAME)
        self._values = set()

        self._payload = payload

        self.site_name = site_name
        self.site_id = site_id
        self.resource_name = resource_name
        self.name = name
        self.nsot_object = nsot_object

    @property
    def values(self):
        """The resources that the attribute assigned"""
        return list(self._values)

    # @property
    # def payload(self):
    #     """The current payload of attribute"""
    #     return self._payload
    #
    # @payload.setter
    # def payload(self, value):
    #     if isinstance(value, dict):
    #         for k, v in value.items():
    #             if k in CONSTRAINTS:
    #                 self._payload.setdefault("contraints", [])[k] = v
    #             else:
    #                 self._payload[k] = v

    @property
    def constraints(self):
        """The contraints of the attribute"""
        try:
            return self._payload["contraints"]
        except KeyError:
            return self.nsot_object.get("constraints", {})

    @constraints.setter
    def constraints(self, value):
        for k, v in value.items():
            if k in CONSTRAINTS:
                self._payload.setdefault("constraints", {})[k] = v

    def __repr__(self):
        return "Attribute({})".format(self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        try:
            return self.key() == other.key()
        except AttributeError:
            return None

    def __hash__(self):
        return hash(self.key())

    def key(self):
        return self.resource_name, self.name, self.site_name

    def exists(self):
        """
        This does not check if the attribute truly exists in NSoT server until
        the post_update() is called. If _object is not emptry it will assume that
        the attribute somehow exists in the server. This is to avoid addtional HTTP
        request to the server

        return: True if nsot_object is not empty else False
        """
        return bool(self.nsot_object)

    @nsot_request
    def post_update(self):
        """POST or UPDATE attribute in NSoT server based on the exists() method"""
        payload = {**self.nsot_object, **self._payload}
        if self.exists():
            if self.nsot_object != payload:
                self._resource(self.nsot_object["id"]).patch(payload)
        else:
            self._resource.post(payload)

        return self.nsot_object

    @nsot_request
    def delete(self, force=False):
        """DELETE attribute in NSoT server"""
        if force:
            # walk through all the resources that has the attribute and delete it
            # and also call the post_update() of the resource to update its attributes
            for resource in self._values:
                del resource.attributes[self.name]

        if self.exists():
            self._resource(self.nsot_object["id"]).delete(force_delete=force)
            self.nsot_object.clear()

    def add_value(self, resource):
        """Add resource to attribute values"""
        self._values.add(resource)
