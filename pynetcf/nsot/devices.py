from .resource import NSoTResources, SiteResources
from .models.device import Device

RESOURCE_NAME = "devices"


class SiteDevices(SiteResources):
    """Create and manage a single site NSoT devices"""

    _klass = Device

    def __init__(self, site, objects, attributes, klass):
        super(SiteDevices, self).__init__(
            site=site, objects=objects, attributes=attributes, klass=klass
        )


class Devices:

    objects = NSoTResources(SiteDevices)

    _sites = {}

    @classmethod
    def site(cls, name):
        if cls._sites.get(name) is None:
            cls._sites[name] = cls.objects(name)
        return cls._sites[name]
