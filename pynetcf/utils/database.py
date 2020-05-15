import os
import pynetcf.constants as C


def get_database(name):
    try:
        os.makedirs(C.DATABASE_DIR)
    except FileExistsError:
        pass

    return C.DATABASE_DIR + "/%s.db" % name
