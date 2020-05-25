from pynsot.client import get_api_client


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


RESOURCES = ("devices", "networks", "interfaces")


class NSoTClient:
    """Manage NSoT API client"""

    resource = get_api_client()
    # iter_sites_attributes = resource.attributes.get()
    _sites = {site["name"]: int(site["id"]) for site in resource.sites.get()}

    _sites_id_cache = {}
    _endpoints_cache = {}
    _default_site = None

    _resource_cache = {}

    @classmethod
    def get_resource(cls, name):
        if name not in RESOURCES:
            raise ValueError("Invalud resource: %s" % name)
        if cls._resource_cache.get(name) is None:
            cls._resource_cache[name] = {
                r["id"]: r for r in getattr(cls.resource, name).get()
            }
        return cls._resource_cache[name]

    @classmethod
    def check_sitename(cls, site_name):
        return bool(cls._sites.get(site_name))

    @classmethod
    def default_site(cls):
        """Return the default site ID and name if defined in pynsotrc file as
        default_site"""

        if cls._default_site is None:
            _site_id = cls.resource.default_site

            if _site_id is None:
                raise ValueError("No 'default_site' defined in pynsotrc")

            site_id = int(_site_id)
            site_name = [k for k, v in cls._sites.items() if v == int(site_id)][0]
            cls._default_site = site_id, site_name

        return cls._default_site

    @classmethod
    def get_sitename(cls, site_id):
        "Return the site name of the given site ID"
        int_siteid = int(site_id)

        if cls._sites_id_cache.get(int_siteid) is None:

            site_name = None
            for name, _id in cls._sites.items():
                if _id == site_id:
                    site_name = name
                    break

            if site_name is None:
                raise ValueError("Site ID '%s' does not exists" % site_id)

            cls._sites_id_cache[int_siteid] = site_name

        return cls._sites_id_cache[int_siteid]

    @classmethod
    def get_siteid(cls, site_name):
        site_id = cls._sites.get(site_name)
        if site_id is None:
            raise ValueError("Site '%s' does not exists" % site_name)
        return site_id

    @classmethod
    def get_endpoint(cls, resource_name, site_name):
        "Return the endpoint API of the given resource and site name"

        # if site_name is None:
        #     site_id, site_name = cls.default_site()
        # else:
        #     site_id = cls._sites.get(site_name)
        #     if site_id is None:
        #         raise ValueError("Site '%s' does not exists" % site_name)

        key = resource_name, site_name
        if cls._endpoints_cache.get(key) is None:
            site_id = cls.get_site_id(site_name)
            cls._endpoints_cache[key] = getattr(
                cls.resource.sites(site_id), resource_name
            )
        return cls._endpoints_cache[key]

    @classmethod
    def create_site(cls, site_name, description=None):
        "POST a new site in NSoT server"
        if description is None:
            description = ""

        payload = {"name": site_name, "description": description}
        result = cls.resource.sites.post(payload)
        cls._sites[site_name] = int(result["id"])
