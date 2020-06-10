"""The Environment class and its helper classes."""
import ipaddress
from typing import Any, Dict, List

import pulumi_vsphere as vsphere


class Network:
    """Represents the IPv4 network being used in the environment."""

    def __init__(self, network_id: str, subnet: ipaddress.IPv4Network, dns_servers: List[str], domains: List[str]):
        """ Initializes Network with the given parameters.

        Args:
            network_id: The name of the network as configured in vSphere (typically the port group name)
            subnet: The IPv4 subnet (i.e. 192.168.1.0/24)
            dns_servers: The DNS servers for the environment
            domains: The search domains for the environment
        """
        self.id = network_id
        self.subnet = subnet
        self.dns_servers = dns_servers
        self.domains = domains


class NodeSettings:
    """Represents the settings used to configure a specific node type.

    When a node is created there are certain values that may differ depending on whether the node is of type master or
    of type worker. This class holds this configuration information for each of those types.
    """

    def __init__(self, name: str, network_offset: int, cpus: int, memory: int):
        """ Initializes NodeSettings with the given parameters.

        Args:
            name: A format string in the form of 'NAME{num}' which will be used to generate node names
            network_offset: The offset used to generate a node's IPv4 address
            cpus: The number of CPUs that will be configured when this node type is created
            memory: The amount of memory in MB that will be configured when this node type is created
        """
        self.name = name
        self.network_offset = network_offset
        self.cpus = cpus
        self.memory = memory


class ResourcePool:
    """Represents a resource pool in which the underlying virtual machine of a node will be deployed in.

    When nodes are created they are assigned a resource group which determines where the underlying virtual machine for
    the node will be created. The environment may have one or more resource pools defined to deploy nodes in. Each
    resource pool has an associated weight which determines the distribution of nodes against it. A resource pool which
    has a higher weight will have more nodes distributed in it. By default the distribution is round-robin style,
    however, in the case of an uneven number of nodes the resource pools with higher weights will take precedence.
    """

    def __init__(self, id: str, datastore_id: str, weight: int):
        """ Initializes ResourcePool with the given parameters.

        Args:
            id: The unique resource pool id as defined in vSphere
            datastore_id: The unique id of the associated datastore as defined in vSphere
            weight: The weight used to set the priority of this resource pool
        """
        self.id = id
        self.datastore_id = datastore_id
        self.weight = weight

    @classmethod
    def from_config(cls, dc: vsphere.Datacenter, pool_config: Dict[str, Any]):
        """Creates and returns a resource pool using the given resource pool configuration data.

        Args:
            dc: The vSphere datacenter this resource group is associated with
            pool_config: A subset of configuration data (env['pools'][x]) used to configure the resource pool

        Returns:
            A ResourcePool object configured using the given parameters
        """
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
    """Represents an environment in which a cluster is created and nodes are deployed in.

    Environments are typically unique per Pulumi stack. For instance, a dev stack may have a unique environment which
    differs from the prod stack. The Environment class holds these unique configurations and serves as the primary
    source of truth used to configure a cluster and its associated nodes. The values used to configure an environment
    are held in a stack's configuration data. For details on each configuration value please refer to the README.
    """

    def __init__(self, name,
                 datacenter: vsphere.Datacenter,
                 domain: str,
                 pools: List[ResourcePool],
                 network: Network,
                 node_template: vsphere.VirtualMachine,
                 master_config: NodeSettings,
                 worker_config: NodeSettings,
                 vault_address: str):
        """ Initializes Environment using the given parameters."""
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
            domain=config['domain'],
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
