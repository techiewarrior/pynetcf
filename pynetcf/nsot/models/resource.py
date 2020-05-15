# from pynsot.vendor.slumber.exceptions import HttpClientError
# from collections import defaultdict

from pynetcf.utils.logger import get_logger
from ..client import NSoTClient, nsot_request

logger = get_logger(__name__)


class NSoTResource:
    """A single NSoT resource"""

    _resource_cache = {}

    def __init__(self, site_name=None, nsot_object=None):
        """
        Constructor

        :param nsot_object: dict object of the resource from GET, POST and PATCH
        :param endpoint: a resource API endpoint it is required if doing a
            request to NSoT server like GET, POST and PATCH, DELETE
        """

        if not any([site_name, nsot_object]):
            raise ValueError("require either 'site_name' or 'nsot_object'")

        if nsot_object is None:
            if site_name is None:
                site_name, site_id = NSoTClient.default_site()
            else:
                site_id = NSoTClient.get_siteid(site_name)
            nsot_object = {}
        else:
            site_id = nsot_object.get("site_id")
            if site_id is None:
                site_id = NSoTClient.get_siteid(site_name)
            else:
                site_name = NSoTClient.get_sitename(site_id)

        model = self.__class__.__name__
        name = model.lower() + "s"

        resource_id = "%s.%s" % (site_id, name)

        resource = NSoTResource._resource_cache.get(resource_id)
        if resource is None:
            resource = getattr(NSoTClient.resource.sites(site_id), name)
            NSoTResource._resource_cache[resource_id] = resource

        self._nsot_object = nsot_object
        self._resource = getattr(NSoTClient.resource.sites(site_id), name)
        self._payload = {}
        self._model = model
        self._name = name

        self.site_id = site_id
        self.site_name = site_name

    @property
    def id(self):
        return self._nsot_object.get("id")

    @property
    def attributes(self):
        try:
            return self._payload["attributes"]
        except KeyError:
            return self._nsot_object.get("attributes", {})

    @attributes.setter
    def attributes(self, value):
        if not value:
            return None
        if isinstance(value, dict):
            self._payload["attributes"] = value

    @attributes.deleter
    def attributes(self):
        try:
            self._payload["attributes"].clear()
        except KeyError:
            return None

    def __repr__(self):
        return "{}({})".format(self._model, self.key()[0])

    def __str__(self):
        return self.key()[0]

    def __getattr__(self, key):
        if self.attributes.get(key) is None:
            raise AttributeError(
                "'%s' object has no attribute '%s'" % (self._model, key)
            )
        return self.attributes[key]

    def __eq__(self, other):
        try:
            return self.key() == other.key()
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash(self.key())

    def exists(self):
        """Return `True` if resource exists in the server else `False`"""
        return bool(self._nsot_object)

    def add_attributes(self, **kwargs):
        "Add an attributes to the current attributes"
        try:
            self._payload["attributes"].update(kwargs)
        except KeyError:
            self._payload["attributes"] = {**self.attributes, **kwargs}

    def remove_attributes(self, *args):
        "Remove an attributes to the current attributes"
        if not self._payload.get("attributes"):
            self._payload["attributes"] = {
                k: v for k, v in self.attributes.items() if k not in args
            }
        else:
            for name in args:
                try:
                    del self._payload["attributes"][name]
                except KeyError:
                    pass

    @nsot_request
    def post_update(self):
        """POST or PATCH resource in NSoT server"""
        payload = {**self._nsot_object, **self._payload}
        result = None
        if self.exists():
            if payload != self._nsot_object:
                result = self._resource(self.id).patch(payload)
                logger.info("[%s] resource updated in the server" % self)
        else:
            result = self._resource.post(payload)
            logger.info("[%s] resource posted in the server" % self)

        if result:
            self._nsot_object.update(result)

        return self._nsot_object

    @nsot_request
    def delete(self, force=False):
        """DELETE resource in NSoT server"""
        if self.exists():
            self._resource(self.id).delete(force_delete=force)
            self._nsot_object = {}
            self.init_payload()
            logger.info("[%s] resource deleted in the server" % self)
            return True
        else:
            return True

    @nsot_request
    def get(self, **kwargs):
        """
        Get resource from the NSoT server. This is the actual method to check if
        the resource truly exists in the server but cost an addtional HTTP requests.

        :return: NSoT resource object
        """
        result = self._resource.get(**kwargs)
        try:
            return result[0]
        except IndexError:
            return {}
