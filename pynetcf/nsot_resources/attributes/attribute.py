from .resource import Resource


class Attribute(Resource):
    """A single NSoT `Attribute` resource"""

    def __init__(self, resource_name, name, site_id=None, **kwargs):
        super(Attribute, self).__init__("attributes", site_id=site_id)

        self._payload = {
            "multi": kwargs.get("multi", False),
            "description": kwargs.get("description", ""),
            "display": kwargs.get("display", True),
            "required": kwargs.get("required", False),
            "constraints": {
                "pattern": kwargs.get("pattern", ""),
                "valid_values": kwargs.get("valid_values", []),
                "allow_empty": kwargs.get("allow_empty", False),
            },
            "resource_name": resource_name,
            "name": name,
            "site_id": self._resource_keys[0],
        }

    @property
    def natural_name(self):
        return "%s:%s" % (self._payload["resource_name"], self._payload["name"])

    @property
    def constraints(self):
        "The constraints of the `Attribute`"
        return self._payload["constraints"]

    @constraints.setter
    def constraints(self, value):
        for key in list(self._payload["constraints"]):
            if value.get(key):
                self._payload["constraints"][key] = value[key]

    def get_dict(self):
        pass
