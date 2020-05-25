# from collections import namedtuple
#
#
# class Resource:
#     from .device import Manager as device
#     from .interface import Manager as interface
#
#     RESOURCE_MODELS = ("device", "interface")
#
#     SiteResourceManager = namedtuple("SiteResourceManager", list(RESOURCE_MODELS))
#
#     _sites_cache = {}
#
#     @classmethod
#     def site(cls, name):
#         if cls._sites_cache.get(name) is None:
#             kwargs = {
#                 r: getattr(cls, r).objects.site(name) for r in cls.RESOURCE_MODELS
#             }
#             cls._sites_cache[name] = cls.SiteResourceManager(**kwargs)
#         return cls._sites_cache[name]
