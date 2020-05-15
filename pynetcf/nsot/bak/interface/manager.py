# import pynetcf.constants as C
from pynetcf.utils import get_logger

from .interface import Interface

# from ..manager import NSoTResourceManager
from ..base import NSoTResources, NSoTSiteResources


logger = get_logger(__name__)

RESOURCE_NAME = "interfaces"


class NSoTSiteInterfaces(NSoTSiteResources):
    """Create and manage a single site of NSoT interfaces"""

    def __init__(self, site_name, resources, attributes):
        super(NSoTSiteInterfaces, self).__init__(
            site_name=site_name,
            resources=resources,
            attributes=attributes,
            klass=Interface,
        )

        for interface in list(self._resources.values()):
            if interface.parent:
                interface.parent = self.__call__(interface.parent)


# class NSoTInterfaces:
#     """Manage NSoT networks"""
#
#     _resources = NSoTResources(RESOURCE_NAME, Interface)
#     _sites = {}
#
#     @classmethod
#     def sites(cls, site_name):
#
#         if site_name is None:
#             site_name = cls._resources.default_sitename()
#
#         if cls._sites.get(site_name) is None:
#             logger.info("Initialising site '%s'" % site_name)
#             site = cls._resources.sites(site_name)
#             cls._sites[site_name] = NSoTSiteInterfaces(
#                 site_name=site_name,
#                 resources=site.resources,
#                 attributes=site.attributes,
#             )
#         return cls._sites[site_name]
