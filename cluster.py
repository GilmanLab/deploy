import pulumi_vsphere as vsphere
import ipaddress
from typing import List

MINIMUM_NUM_NODES = 3


class Network:
    def __init__(self, network_id: str, subnet: ipaddress.IPv4Network, dns_servers: List[str], domains: List[str]):
        self.id = network_id
        self.subnet = subnet
        self.dns_servers = dns_servers
        self.domains = domains


class NodeSettings:
    def __init__(self, name: str, network_offset: int, cpus: int, memory: int):
        self.name = name
        self.network_offset = network_offset
        self.cpus = cpus
        self.memory = memory


class Environment:
    def __init__(self, name,
                 network: Network,
                 node_template: vsphere.VirtualMachine,
                 master_config: NodeSettings,
                 worker_config: NodeSettings,
                 vault_address: str):
        self.name = name
        self.network = network
        self.node_template = node_template
        self.master_config = master_config
        self.worker_config = worker_config
        self.vault_address = vault_address


class ResourcePool:
    def __init__(self, id: str, datastore_id: str, weight: int):
        self.id = id
        self.datastore_id = datastore_id
        self.weight = weight


class ClusterProperties:
    def __init__(self, nodes: int, env: Environment, pools: List[ResourcePool]):
        self.nodes = nodes
        self.env = env
        self.pools = pools
