import os

# the path where the database of configuration
DATABASE_DIR = "/home/%s/.pynetcf" % os.environ.get("USER")

# L3 VLANID reserve range
RESERVED_L3_VLANID = range(4000, 4091)

# private CIDRS block
PRIVATE_CIDRS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

# index number of the network to select as the default gateway
NETWORK_DEFAULT_GW = -1

# mac addresses reserve range, use for VRRP gateway, MLAG
RESERVED_MAC_ADDRESSES = ("44:38:39:ff:00:00", "44:38:39:ff:ff:ff")

# default prefixlen for auto subnets
DEFAULT_PREFIXLEN = 23

# VXLAN base prefix name
DEFAULT_VXLAN_BASE_NAME = "vni"

# VXLAN base ID
DEFAULT_VXLAN_BASE_ID = 10000
