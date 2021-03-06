from collections import defaultdict

from pynetcf.utils import filter_object, get_object
from .client import NSoTClient
from .attribute import Attribute


class SiteResourceManager:
    """Base class for creating and managing a single NSoT site resources"""

    def __init__(self, site, objects, attributes, klass, **kwargs):

        self.site_name, self.site_id = site

        model = klass.__name__
        self._klass = klass
        self._model = model

        self._objects = objects
        self._attributes = attributes

        for obj in objects.values():
            for attr in obj.attributes:
                attributes(attr).add_value(obj)

    @property
    def attributes(self):
        return self._attributes

    def __call__(self, key):
        if self._objects.get(key) is None:
            param = tuple(key.split(":")) + (self.site_name,)
            resource = self._klass(*param)
            self._objects[key] = resource
        return self._objects[key]

    def get_key(self, key):
        return self.__call__(key)

    def filter(self, **kwargs):
        yield from filter_object(list(self._objects.values()), **kwargs)

    def get(self, **kwargs):
        return get_object(list(self._objects.values()), **kwargs)

    def add(self, *args, **kwargs):
        key = ":".join(args)
        resource = self.__call__(key)
        if not resource.exists():
            resource.attributes = kwargs
            resource.post_update()


class SiteAttributeManager:
    """Create and manage a single NSoT site attributes"""

    def __init__(self, site_name, model, attributes):
        self._attributes = attributes

        self.site_name = site_name
        self.model = model

    def __call__(self, name):
        if self._attributes.get(name) is None:
            attr = Attribute(self.model, name, self.site_name)
            self._attributes[name] = attr
        return self._attributes[name]

    def filter(self, **kwargs):
        yield from filter_object(list(self._attributes.values()), **kwargs)

    def get(self, **kwargs):
        return get_object(list(self._attributes.values()), **kwargs)

    def add(self, name, **kwargs):
        attr = self.__call__(name)
        if not attr.exists():
            attr.constraints = kwargs
            attr.post_update()

    def delete(self, name):
        try:
            self._attributes[name].delete()
            del self._attributes[name]
        except KeyError:
            return None


class NSoTAttributeManager:
    """Generate NSoT resource attribute objects"""

    _sites_attributes = NSoTClient.resource.attributes.get()

    def __init__(self, model):

        attributes = defaultdict(dict)

        for nsot_object in self._sites_attributes:
            if nsot_object["resource_name"] == model:
                attr = Attribute(nsot_object=nsot_object)
                attributes[attr.site_name][attr.name] = attr

        self._attributes = attributes
        self._sites_cache = {}

        self.model = model

    def __call__(self, site_name):
        if self._sites_cache.get(site_name) is None:
            self._sites_cache[site_name] = SiteAttributeManager(
                site_name=site_name,
                model=self.model,
                attributes=self._attributes[site_name],
            )
        return self._sites_cache[site_name]

    def filter(self, **kwargs):
        """Return a list of resource based on kwargs"""
        yield from filter_object(self._get_all(), **kwargs)

    def get(self, **kwargs):
        """Return a single `Device` based on kwargs, if kwargs is not provided it
        return all the objects"""
        return get_object(self._get_all(), **kwargs)

    def _get_all(self):
        return [obj for k, v in self._attributes.items() for _, obj in v.items()]


class NSoTResourceManager:
    """Generate NSoT resource objects"""

    def __init__(self, resource_class, manager_class=None, **kwargs):

        model = resource_class.__name__
        name = model.lower() + "s"

        attributes = NSoTAttributeManager(model)
        objects = defaultdict(dict)

        for _, nsot_object in NSoTClient.get_resource(name).items():
            resource = resource_class(nsot_object=nsot_object)
            site_name = resource.site_name
            objects[site_name][str(resource)] = resource

        self._objects = objects
        self._attributes = attributes
        self._model = model
        self._resource_class = resource_class
        self._manager_class = manager_class
        self._kwargs = kwargs

        self._sites_cache = {}

    @property
    def attributes(self):
        return self._attributes

    def site(self, site_name):
        if self._sites_cache.get(site_name) is None:
            site_id = NSoTClient.get_siteid(site_name)

            if self._site_resource_manager_class is None:
                manager_class = SiteResourceManager

            manager_class = manager_class(
                site=(site_name, site_id),
                objects=self._objects[site_name],
                attributes=self._attributes(site_name),
                klass=self._resource_class,
                **self._kwargs
            )

        return self._sites_cache[site_name]

    def filter(self, **kwargs):
        """Return a list of resource based on kwargs"""
        yield from filter_object(self._get_all(), **kwargs)

    def get(self, **kwargs):
        """Return a single `Device` based on kwargs, if kwargs is not provided it
        return all the objects"""
        return get_object(self._get_all(), **kwargs)

    def _get_all(self):
        return [obj for k, v in self._objects.items() for _, obj in v.items()]
