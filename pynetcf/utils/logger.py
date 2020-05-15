import logging
from logging.handlers import RotatingFileHandler


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")

    rfh = RotatingFileHandler("pynetcf.log", maxBytes=512000, backupCount=2)
    rfh.setLevel(logging.DEBUG)
    rfh.setFormatter(formatter)

    logger.addHandler(rfh)

    return logger
