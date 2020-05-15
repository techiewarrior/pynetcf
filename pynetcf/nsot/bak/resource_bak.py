# from pynsot.vendor.slumber.exceptions import HttpClientError
from collections import defaultdict

from pynetcf.utils import get_logger
from .client import NSoTClient

logger = get_logger(__name__)


def nsot_request(request_func):
    """A decorator that print the body and error message from the request response
    for better presentation of error
    """

    def wrapper(*args, **kwargs):
        try:
            return request_func(*args, **kwargs)
        except Exception as e:
            try:
                msg = e.response.json()["error"]["message"]
                body = e.response.request.body
                print("ERROR:", msg)
                if body:
                    print(body)
            except AttributeError:
                pass
            raise

    return wrapper


class NSoTResource:
    """A single NSoT resource"""

    _endpoints_cache = defaultdict(dict)

    def __init__(self, name, site_name=None, resource_obj=None):
        """
        Constructor

        :param nsot_object: dict object of the resource from GET, POST and PATCH
        :param endpoint: a resource API endpoint it is required if doing a
            request to NSoT server like GET, POST and PATCH, DELETE
        """

        if resource_obj is None:
            if site_name is None:
                site_name = NSoTClient.default_site()[1]
            resource_obj = {}
        else:
            try:
                site_name = NSoTClient.get_sitename(resource_obj["site_id"])
            except KeyError:
                site_name = None

        if self._endpoints_cache[name].get(site_name) is None:
            self._endpoints_cache[name][site_name] = NSoTClient.get_endpoint(
                resource_name=name, site_name=site_name
            )

        self._endpoint = self._endpoints_cache[name][site_name]

        self._object = resource_obj
        self._payload = {}
        self._site_name = site_name
        self._addn_attrs = {}

        self.natural_name = None

    @property
    def site_name(self):
        return self._site_name

    @property
    def id(self):
        return self.object.get("id")

    @property
    def object(self):
        return self._object

    @property
    def payload(self):
        return self._payload

    @property
    def attributes(self):
        return self._object.get("attributes", {})

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
        return str(self.object)

    def exists(self):
        """
        This does not check if the `Resource` truly exists in NSoT server until
        the post_update() is called. If nsot_object param is provided in __init__ it
        will assume that the `Resource` somehow exists in the server. This is to avoid
        addtional HTTP request to the server

        return: True if self.nsot_object is not empty else False
        """
        return bool(self.object)

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
        payload = {**self.object, **self.payload}
        result = None
        if self.exists():
            if payload != self.object:
                result = self._endpoint(self.id).patch(payload)
                logger.info(
                    "[%s] resource updated in the server" % self.natural_name
                )
        else:
            result = self._endpoint.post(payload)
            logger.info("[%s] resource posted in the server" % self.natural_name)

        if result:
            self.object.update(result)

        return self.object

    @nsot_request
    def delete(self, force=False):
        """DELETE resource in NSoT server"""
        if self.exists():
            self._endpoint(self.id).delete(force_delete=force)
            self.object.clear()
            logger.info("[%s] resource deleted in the server" % self.natural_name)
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
        result = self._endpoint.get(**kwargs)
        try:
            return result[0]
        except IndexError:
            return {}
