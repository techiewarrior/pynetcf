# from pynsot.vendor.slumber.exceptions import HttpClientError
from collections import defaultdict

from pynetcf.utils import get_logger
from .client import NSoTClient, nsot_request

logger = get_logger(__name__)


class NSoTResource:
    """A single NSoT resource"""

    _sites_attributes = NSoTClient.resource.attributes.get()

    _endpoints_cache = defaultdict(dict)

    def __init__(self, nsot_object=None):
        """
        Constructor

        :param nsot_object: dict object of the resource from GET, POST and PATCH
        :param endpoint: a resource API endpoint it is required if doing a
            request to NSoT server like GET, POST and PATCH, DELETE
        """
        if nsot_object is None:
            nsot_object = {}

        model = self.__class__.__name__
        name = model.lower() + "s"

        self._nsot_object = nsot_object
        self._resource = getattr(NSoTClient.resource.sites(self._site_id), name)

        self._payload = {}
        self._addn_attrs = {}

    @property
    def resource_model(self):
        return self.__class__.__name__

    @property
    def resource_name(self):
        return self.resource_model.lower() + "s"

    @property
    def id(self):
        return self._nsot_object.get("id")

    @property
    def payload(self):
        return self._payload

    @property
    def attributes(self):
        try:
            return self._payload["attributes"]
        except KeyError:
            return self._nsot_object.get("attributes", {})

    @payload.setter
    def payload(self, value):
        if value is None:
            return None
        if isinstance(value, dict):
            self._payload = value

    @attributes.setter
    def attributes(self, value):
        if value is None:
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
        return "{}({})".format(self.__class__.__name__, ".".join(self.key()))

    def __str__(self):
        return ".".join(self.key())

    def exists(self):
        """Return `True` if resource exists in the server else `False`"""
        return bool(self._nsot_object)

    def add_attributes(self, **kwargs):
        try:
            self._payload["attributes"].update(kwargs)
        except KeyError:
            self._payload["attributes"] = {**self.attributes, **kwargs}

    def remove_attributes(self, *args):
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
        payload = {**self._nsot_object, **self.payload}
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
            self._nsot_object.clear()
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
