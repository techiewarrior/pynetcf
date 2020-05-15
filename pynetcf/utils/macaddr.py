import sqlite3

from netaddr import EUI, mac_unix_expanded

import pynetcf.constants as C
from .logger import get_logger

TABLES = (
    """ CREATE TABLE IF NOT EXISTS macaddrs (
            value INTEGER PRIMARY KEY,
            address TEXT NOT NULL,
            assignment TEXT NOT NULL
        ); """,
)

logger = get_logger(__name__)


class MACAddress:
    def __init__(self, addr, assignment=None, conn=None):
        self._addr = addr
        self._assignment = assignment
        self._conn = conn

    def __repr__(self):
        return "MACAddress({}.{})".format(self._addr, self._assignment)

    def __str__(self):
        return str(self._addr)

    @property
    def address(self):
        return str(self._addr)

    @property
    def value(self):
        return self._addr.value

    @property
    def assignment(self):
        return self._assignment

    @assignment.setter
    def assignment(self, assignment):
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO macaddrs(value,address,assignment) VALUES(?,?,?)",
                    (self.value, self.address, assignment),
                )
                logger.info(
                    "[MACAddress] %s created new MAC address assign to %s"
                    % (self.address, assignment)
                )
        except sqlite3.IntegrityError:
            if assignment != self._assignment:
                with self._conn:
                    self._conn.execute(
                        "UPDATE macaddrs SET assignment=? WHERE address=?",
                        (assignment, self.address),
                    )
                logger.info(
                    "[MACAddress] %s updated MAC address new assigment=%s previous "
                    "assignment=%s" % (self.addr, assignment, self.assignment)
                )
        self._assignment = assignment

    def delete(self):
        with self._conn:
            self._conn.execute(
                "DELETE FROM macaddrs WHERE address=?", (self.__str__(),)
            )
            logger.info("[MACAddress] %s deleted in the database" % self)


class MACAddressManager:
    def __init__(self):

        db_path = C.DATABASE_DIR + "/macaddr.db"
        conn = sqlite3.connect(db_path)
        for t in TABLES:
            conn.execute(t)

        cache = {}

        for addr, assign in conn.execute("SELECT address,assignment FROM macaddrs"):
            mac = MACAddress(
                EUI(addr, dialect=mac_unix_expanded), assignment=assign, conn=conn
            )
            cache[assign] = mac

        def _addrs_generator():
            start, end = C.RESERVED_MAC_ADDRESSES
            _start = EUI(start)
            _end = EUI(end)

            def _addrs():
                range_value = range(_start.value, _end.value + 1)
                existing_values = [
                    v for (v,) in self._conn.execute("SELECT value FROM macaddrs")
                ]
                for value in set(range_value) - set(existing_values):
                    mac = MACAddress(
                        EUI(value, dialect=mac_unix_expanded), conn=self._conn
                    )
                    yield mac

            addrs = _addrs()
            while True:
                try:
                    yield next(addrs)
                except StopIteration as e:
                    e.args = ("Run out of MAC Addresses",)
                    raise

        self._conn = conn

        self._cache = cache

        self._addrs = _addrs_generator()

    def create(self, assignment):
        addr = next(self._addrs)
        addr.assignment = assignment

        self._cache[assignment] = addr

        return addr

    def filter(self, **kwargs):

        if kwargs:
            for addr in list(self._cache.values()):
                query = []
                try:
                    for key, value in kwargs.items():
                        try:
                            attr_value = value(getattr(addr, key))
                            query.append(attr_value)
                        except TypeError:
                            attr_value = getattr(addr, key)
                            query.append(value == attr_value)
                    if all(query):
                        yield addr
                except AttributeError:
                    pass

    def get(self, assignment=None):
        if assignment:
            return self._cache.get(assignment)
        return list(self._cache.values())

    def delete(self, assignment):
        try:
            self._cache[assignment].delete()
            del self._cache[assignment]
        except KeyError:
            return None
