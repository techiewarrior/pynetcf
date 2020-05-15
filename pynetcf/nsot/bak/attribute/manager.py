from .attribute import Attribute
from ..resource import get_resource


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AttributeManager(metaclass=Singleton):
    def __init__(self):
        resource = get_resource(default_site=False)

        self._cache = [Attribute(nsot_obj=r) for r in resource.attributes.get()]
        self._sites_cache = {}

        self._resource = resource
        self._resource_cache = {}

    def get(self, resource_name):
        return {
            a.name: a
            for a in self._cache
            if getattr(a, "site_id") == site_id
            and getattr(a, "resource_name") == resource_name
        }

    def add(self, site_id, **kwargs):
        print(site_id)
        if self._resource_cache.get(site_id) is None:
            self._resource_cache[site_id] = self._resource.sites(site_id).attributes

        resource = self._resource_cache[site_id]
        attr = Attribute(site_id=site_id, resource=resource, **kwargs)
        attr.update()
        self._cache.append(attr)

    def delete(self, attribute):
        try:
            attribute.delete()
        except AttributeError:
            return
