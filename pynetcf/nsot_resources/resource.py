# import logging

from abc import ABC, abstractmethod

from pynsot.client import get_api_client

# logger = logging.getLogger(__name__)
# logger.addHandler(logging.StreamHandler())


def get_resource(site_id, name):
    """
    Get the NSoT resource API endpoint

    :param site_id: the site ID which the resource belong. If `None`
        try to check if default_site variable defined in pynsotrc else
        raises `TypeError`
    :param name: name of the resource ex. networks, devices, interfaces

    :return: the site_id and pynsot.client
    """
    api_client = get_api_client()
    if site_id is None:
        if api_client.default_site is None:
            raise TypeError(
                "Resource require 'site_id' via param or defined "
                "as 'default_site' variable in pynsotrc"
            )
        site_id = api_client.default_site
    return int(site_id), getattr(api_client.sites(site_id), name)


def nsot_request(request_func):
    """'
    A decorator that disect error message if occur from NSoT request and
    add the message to exception
    """

    def get_error(error):

        msg, is_request = None, False

        if hasattr(error, "response"):
            msg = error.response.json()["error"]["message"]
            is_request = True

            if hasattr(msg, "items"):
                msg = list(msg.values())[0]
        else:
            msg = error

        return msg, is_request

    def wrapper(*args, **kwargs):
        try:
            return request_func(*args, **kwargs)
        except Exception as err_exc:
            msg, is_request = get_error(err_exc)
            if is_request:
                msg = "ERROR: %s" % msg
                err_exc.args = (err_exc.args[0] + "\n" + msg,)
            raise

    return wrapper


class Resource(ABC):
    "A abstract base class of NSoT Resource"

    def __init__(self, name, site_id=None, nsot_obj=None):
        """
        Constructor

        :param name: name of the resource ex. networks,devices,interfaces...
        :param site_id: the site ID which the resource belong. Default to
            `default_site` if defined in pynsotrc else raise TypeError
        :param nsot_obj: dict object of the resource return from GET, POST and PATCH
        """

        if nsot_obj is None:
            nsot_obj = {}

        # get site_id/default_site and resource API endpoint
        site_id, resource = get_resource(nsot_obj.get("site_id"), name)

        self._payload = {}
        self._nsot_obj = nsot_obj
        self._changed = False

        self._site_id = site_id
        self._resource_name = name
        self._resource = resource

    @property
    @abstractmethod
    def natural_name(self):
        "The natural name of the `Resource`"

    @abstractmethod
    def get_dict(self):
        """
        return: a custom dict object of the `Resource` not same with
            the NSoT resource object
        """

    @property
    def nsot_obj(self):
        "The NSoT resource object"
        return self._nsot_obj

    @property
    def attributes(self):
        """
        The current payload attributes not the attributes of the
        existing resource
        """
        if self._resource_name != "attributes":
            return self._payload["attributes"]
        return NotImplemented

    @nsot_obj.setter
    def nsot_obj(self, value):
        self._nsot_obj = value
        self._changed = True

    @attributes.setter
    def attributes(self, value):
        if self._resource_name != "attributes":
            if not isinstance(value, dict):
                raise TypeError("param must be dict a object")
            self._payload["attributes"] = value
        return NotImplemented

    @nsot_obj.deleter
    def nsot_obj(self):
        self._nsot_obj = {}
        self._changed = True

    @attributes.deleter
    def attributes(self):
        self._payload["attributes"].clear()

    def __repr__(self):
        return "%s(%s, %s)" % (
            self.__class__.__name__,
            self._site_id,
            self.natural_name,
        )

    def __str__(self):
        return self.natural_name

    def __eq__(self, other):
        try:
            return (self._site_id, self.natural_name) == (
                other.nsot_obj.get("site_id"),
                other.natural_name,
            )
        except AttributeError:
            if isinstance(other, str):
                return self.natural_name == other
            return NotImplemented

    def exists(self):
        """
        This does not check if the `Resource` really exists in NSoT server until
        the self.update() is called. If nsot_obj param is provided in __init__ it
        will assume that the `Resource` somehow exists in the server. This is to avoid
        addtional HTTP request to the server

        return: True if self.nsot_obj is not empty else False
        """
        return bool(self.nsot_obj)

    @nsot_request
    def update(self):
        """POST or PATCH `Resource` to the NSoT server"""

        # def ensure_attrs():
        #     site_id, rname = self._key
        #
        #     if rname == 'attributes':
        #         return
        #
        #     resource_name = rname[:-1].title()
        #     key = (site_id, 'attributes')
        #
        #     for name, value in self.attributes.items():
        #         natural_name = '%s:%s' % (resource_name, name)
        #
        #         if self.__data[key].get(natural_name) is None:
        #             payload = {
        #                 'site_id': site_id,
        #                 'resource_name': resource_name,
        #                 'name': name,
        #                 'multi': isinstance(value, list)
        #             }
        #             self.__data[key].update(self.__data[key].resource.post(payload))

        # Merge nsot_obj and current payload
        payload = {**self.nsot_obj, **self._payload}

        # PATCH
        if self.exists():
            # compare the current payload and existing resource
            if payload != self.nsot_obj:
                # ensure_attrs()

                # do the acutal patch request
                self.nsot_obj = self._resource(payload["id"]).patch(payload)
        # POST
        else:
            # ensure_attrs()

            # do the acutal post request
            self.nsot_obj = self._resource.post(payload)

    @nsot_request
    def delete(self, force=False):
        """
        Delete `Resource` in NSoT server.

        :param force: (optional) `True` will try force delete the `Resource`
        :return: `True` if `Resource` does not exists in first place and also
            True if it succesfully deleted in the server
        """

        if self.exists():
            self._resource(self.nsot_obj["id"]).delete(force_delete=force)
            del self.nsot_obj
            return True
        return True

    @nsot_request
    def get(self):
        """
        Get resource from the NSoT server. This is the actual method to check if
        the `Resource` really exists in the server but cost an addtional HTTP requests.

        :return: NSoT resource object
        """

        results = self._resource.get(cidr=self.natural_name)
        if results:
            self.nsot_obj = results[0]
        return self.nsot_obj
