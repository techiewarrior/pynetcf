import sqlite3

import pynetcf.constants as C
from pynetcf.utils import get_logger, get_database

TABLES = (
    """ CREATE TABLE IF NOT EXISTS vids (
            vid INTEGER PRIMARY KEY,
            tenant TEXT NOT NULL
        ); """,
)

logger = get_logger(__name__)


class TenantData:
    "Create and manage VLAN tenant relationship"

    def __init__(self):

        db_path = get_database("vids")
        conn = sqlite3.connect(db_path)
        for t in TABLES:
            conn.execute(t)

        vids = conn.execute("SELECT vid,tenant FROM vids").fetchall()

        self._conn = conn
        self._tenants = {t: v for v, t in vids}

        def _l3vids_generator():
            "A generator that produce a unique number for L3 VLANID"

            def _l3vids():
                l3vids = set(C.RESERVED_L3_VLANID) - set(self._tenants.values())
                for vid in list(l3vids):
                    yield vid

            l3vids = _l3vids()
            while True:
                try:
                    yield next(l3vids)
                except StopIteration as err_exc:
                    err_exc.args = ("Run out of L3 VLANID",)
                    raise

        self._l3vids = _l3vids_generator()

    def get_l3vids(self, tenant=None):
        "Return the L3 VLAN ID associated with the tenant"
        if tenant is None:
            return list(self._tenants.values())

        try:
            l3vid = self._tenants[tenant]
        except KeyError:
            l3vid = next(self._l3vids)
            with self._conn:
                self._conn.execute(
                    "INSERT INTO vids(vid,tenant) VALUES(?,?)", (l3vid, tenant)
                )

            self._tenants[tenant] = l3vid
            logger.info(
                "[TenantData] created L3 VLANID {} assign to {}".format(
                    l3vid, tenant
                )
            )

        return l3vid

    def get_tenants(self, l3vid=None):
        "Return the tenant associated with L3 VLAN ID"
        if l3vid is None:
            return list(self._tenants)
        for k, v in self._tenants.values():
            if l3vid == v:
                return k

    def delete(self, *args):
        """
        Delete vids from the database

        :param args: L3 VLANID
        """
        with self._conn:
            self._conn.execute("BEGIN")
            for vid in args:
                self._conn.execute("DELETE FROM vids WHERE vid=?", (vid,))
                logger.info(
                    "[TenantData] deleted L3 VLANID %s in the database" % vid
                )
            self._conn.execute("COMMIT")
