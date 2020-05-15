from .devices import Devices
from .interfaces import Interfaces


class SiteResource:
    def __init__(self, site_name, **kwargs):
        self.site_name = site_name

        for k, v in kwargs.items():
            setattr(self, k, v)


class Resource:

    devices = Devices
    interfaces = Interfaces

    _sites_cache = {}

    @classmethod
    def site(cls, name):
        if cls._sites_cache.get(name) is None:
            cls._sites_cache[name] = SiteResource(
                site_name=name,
                devices=cls.devices.site(name),
                interfaces=cls.interfaces.site(name),
            )
        return cls._sites_cache[name]

    # @classmethod
    # def interfaces(cls, site_name):
    #     # print("YES")
    #     # from .site.devices import SiteDevices
    #     #
    #     # return NSoTResources(SiteDevices)
    #     site_resource = cls._resources.get("interfaces")
    #     if site_resource is None:
    #         from .site.interfaces import SiteInterfaces
    #
    #         site_resource = NSoTResources(SiteInterfaces)
    #         cls._resources["interfaces"] = site_resource
    #         return site_resource(site_name)
    #     return site_resource(site_name)
