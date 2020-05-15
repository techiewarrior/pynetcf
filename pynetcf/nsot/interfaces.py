from .resource import NSoTResources, SiteResources
from .models.interface import Interface

RESOURCE_NAME = "interfaces"


class SiteInterfaces(SiteResources):
    """Create and manage a single site NSoT interfaces"""

    _klass = Interface

    def __init__(self, site, objects, attributes, klass):
        super(SiteInterfaces, self).__init__(
            site=site, objects=objects, attributes=attributes, klass=klass
        )


class Interfaces:

    objects = NSoTResources(SiteInterfaces)

    _sites = {}

    @classmethod
    def site(cls, name):
        if cls._sites.get(name) is None:
            cls._sites[name] = cls.objects(name)
        return cls._sites[name]
