import sqlite3
import pyconfigvars.constants as C

TABLES = (
    """ CREATE TABLE IF NOT EXISTS tenants (
            l3vid INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        ); """,
    """ CREATE TABLE IF NOT EXISTS vids (
            vid INTEGER PRIMARY KEY,
            tenant TEXT NOT NULL,
            FOREIGN KEY (tenant) REFERENCES tenants (name)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        ); """,
)


class VlanData:
    "Create and manage VLAN tenant relationship"

    def __init__(self):

        db_path = C.DATABASE_DIR + "/vids.db"
        conn = sqlite3.connect(db_path)
        for t in TABLES:
            conn.execute(t)

        self._conn = conn

        self._l3vids = self._iter_l3vids()

    def _iter_l3vids(self):
        "An iterator that yield unique number for L3 VLANID"

        existing_l3vids = [
            vid for (vid,) in self._conn.execute("SELECT l3vid FROM tenants")
        ]

        def iter_l3vids_():
            l3vids = set(C.RESERVED_L3_VLANID) - set(existing_l3vids)
            for vid in list(l3vids):
                yield vid

        l3vids = iter_l3vids_()
        while True:
            try:
                yield next(l3vids)
            except StopIteration as err_exc:
                err_exc.args = ("Run out of L3 VLANID",)
                raise

    def get_tenants(self):
        with self._conn:
            return [t for (t,) in self._conn.execute("SELECT name FROM tenants")]

    def get_l3vids(self, tenant=None):
        with self._conn:
            if tenant is None:
                return self._conn.execute("SELECT * FROM tenants").fetchall()
            l3vid = self._conn.execute(
                "SELECT l3vid FROM tenants WHERE name=?", (tenant,)
            ).fetchone()
            if l3vid is None:
                l3vid = next(self._l3vids)
                self._conn.execute(
                    "INSERT INTO tenants(l3vid,name) VALUES(?,?)", (l3vid, tenant)
                )
            try:
                return l3vid[0]
            except TypeError:
                return l3vid

    def get_vids(self, tenant=None):
        with self._conn:
            if tenant is None:
                return [vid for (vid,) in self._conn.execute("SELECT vid FROM vids")]
            else:
                return [
                    vid
                    for (vid,) in self._conn.execute(
                        "SELECT vid FROM vids WHERE tenant=?", (tenant,)
                    )
                ]

    def add_vids(self, vids):
        existing_vids = self.get_vids()

        with self._conn:
            for vid, tenant in vids:
                if vid in existing_vids:
                    self._conn.execute(
                        """UPDATE vids SET tenant=? WHERE vid=?""", (tenant, vid)
                    )
                else:
                    self._conn.execute(
                        """INSERT INTO vids(vid,tenant) VALUES(?,?)""", (vid, tenant)
                    )

    def delete_vids(self, vids):
        with self._conn:
            self._dbase.conn.executemany("DELETE FROM vids WHERE vid=?", vids)

    def delete_tenants(self, tenants):
        with self._conn:
            self._conn.executemany("DELETE FROM tenants WHERE name=?", tenants)
