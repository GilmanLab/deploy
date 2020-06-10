import ipaddress
import pulumi_vsphere as vsphere
from typing import Any, Dict, List


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


class ResourcePool:
    def __init__(self, id: str, datastore_id: str, weight: int):
        self.id = id
        self.datastore_id = datastore_id
        self.weight = weight

    @classmethod
    def from_config(cls, dc: vsphere.Datacenter, pool_config: Dict[str, Any]):
        if pool_config['type'].lower() == 'cluster':
            return ResourcePool(
                id=vsphere.get_compute_cluster(str(dc.id), pool_config['name']).resource_pool_id,
                datastore_id=vsphere.get_datastore(str(dc.id), name=pool_config['datastore']).id,
                weight=pool_config['weight']
            )
        else:
            return ResourcePool(
                id=vsphere.get_host(str(dc.id), pool_config['name']).resource_pool_id,
                datastore_id=vsphere.get_datastore(str(dc.id), name=pool_config['datastore']).id,
                weight=pool_config['weight']
            )


class Environment:
    def __init__(self, name,
                 datacenter: vsphere.Datacenter,
                 domain: str,
                 pools: List[ResourcePool],
                 network: Network,
                 node_template: vsphere.VirtualMachine,
                 master_config: NodeSettings,
                 worker_config: NodeSettings,
                 vault_address: str):
        self.name = name
        self.datacenter = datacenter
        self.domain = domain
        self.pools = pools
        self.network = network
        self.node_template = node_template
        self.master_config = master_config
        self.worker_config = worker_config
        self.vault_address = vault_address
        
    @classmethod
    def from_config(cls, config: Dict[str, Any]):
        dc = vsphere.get_datacenter(config['datacenter'])
        # Build resource pools
        pools = []
        for pool in config['pools']:
            pools.append(ResourcePool.from_config(dc, pool))

        return Environment(
            name=config['name'],
            datacenter=dc,
            pools=pools,
            network=Network(
                network_id=str(vsphere.get_network(dc.id, name=config['network']['name']).id),
                subnet=ipaddress.ip_network(config['network']['subnet']),
                dns_servers=config['network']['dns_servers'],
                domains=config['network']['domains']
            ),
            node_template=vsphere.get_virtual_machine(dc.id, name=config['template']),
            master_config=NodeSettings(
                name=config['node']['master']['name'],
                network_offset=config['node']['master']['network_offset'],
                cpus=config['node']['master']['cpus'],
                memory=config['node']['master']['memory']
            ),
            worker_config=NodeSettings(
                name=config['node']['worker']['name'],
                network_offset=config['node']['worker']['network_offset'],
                cpus=config['node']['worker']['cpus'],
                memory=config['node']['worker']['memory']
            ),
            vault_address=config['vault_address']
        )

