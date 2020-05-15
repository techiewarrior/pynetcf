from pynetcf.utils import get_logger
from .device import Device

# from ..client import NSoTClient

# from ..client import _client
from ..base import NSoTResources, NSoTSiteResources


logger = get_logger(__name__)

RESOURCE_NAME = "devices"


class NSoTSiteDevices(NSoTSiteResources):
    """Create and manage a single site NSoT devices"""

    def __init__(self, site_name, resources, attributes):
        super(NSoTSiteDevices, self).__init__(
            site_name=site_name,
            resources=resources,
            attributes=attributes,
            klass=Device,
        )


class NSoTDevices:
    """Manage NSoT devices"""

    _resources = NSoTResources(RESOURCE_NAME, Device)
    _sites = {}

    @classmethod
    def sites(cls, site_name):
        if cls._sites.get(site_name) is None:
            site = cls._resources.sites(site_name)
            cls._sites[site_name] = NSoTSiteDevices(
                site_name=site_name,
                resources=site.resources,
                attributes=site.attributes,
            )
        return cls._sites[site_name]

    @classmethod
    def get(cls, **kwargs):
        try:
            return next(cls._resources.filter(**kwargs))
        except StopIteration:
            return None
