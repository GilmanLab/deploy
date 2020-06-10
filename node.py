"""The Node class and its helper classes and functions."""
import base64
from enum import Enum
from typing import Any, Dict, List

import pulumi
import pulumi_vsphere as vsphere
from jinja2 import Template

import environment


def _build_disks(template: vsphere.VirtualMachine) -> List[Dict[str, Any]]:
    """Builds a list of disks based off of the disks present in the given virtual machine.

    Args:
        template: The virtual machine to copy disks from

    Returns:
        A list of disks (in dictionary form) copied from the virtual machine
        """
    i = 0
    disks = []
    for disk in template.disks:
        disks.append({'label': 'disk{}'.format(i),
                      'size': int(float(str(disk['size']))) + 1,  # Have to add 1 to account for rounding errors
                      'unitNumber': i,
                      'thinProvisioned': bool(disk['thinProvisioned']),
                      'eagerlyScrub': bool(disk['eagerlyScrub'])})
        i += 1
    return disks


def _render_cloud_init(path: str, **kwargs) -> str:
    """Renders a cloud-init Jinja2 template at the given path using the given keyword arguments.

    Args:
        path: Path to the Jinja2 template
        kwargs: Keyword arguments that will be passed to Jinja2 for rendering

    Returns:
        The rendered template encoded with base64
    """
    with open(path, 'r') as f:
        rendered = Template(f.read()).render(**kwargs)
    return base64.b64encode(rendered.encode('utf-8')).decode('utf-8')


class NodeType(Enum):
    """The type of a given node: either MASTER or WORKER. """
    MASTER = 1
    WORKER = 2


class IPConfig:
    """An IP configuration used to configure a node's interfaces using cloud-init"""

    def __init__(self, ip_address: str, gateway: str, dns_servers: List[str], domains: List[str]):
        """ Initializes IPConfig using the given parameters.

        Args:
            ip_address: The IPv4 address to assign to the node
            gateway: The IPv4 gateway to assign to the interface
            dns_servers: A list of DNS servers to assign to the interface
            domains: A list of default search domains to assign to the interface
        """
        self.ip_address = ip_address
        self.gateway = gateway
        self.dns_servers = dns_servers
        self.domains = domains

    @classmethod
    def from_environment(cls, index: int, node_type: NodeType, env: environment.Environment):
        """Creates and returns an IPConfig object initialized from the given environment.

        The environment can give enough details to correctly configure a node's interface. The only information it
        cannot obtain is the node index which is required to determine the IPv4 address and the node's type which
        determine the subnet and offset for the node's IPV4 address.

        Args:
            index: The node's index number
            node_type: The type of node (MASTER or WORKER)
            env: The environment to use when initializing the IPConfig object

        Returns:
            An IPConfig object configured using the given parameters and environment
        """
        if node_type == NodeType.MASTER:
            address = (env.network.subnet.network_address + env.master_config.network_offset + index)
        else:
            address = (env.network.subnet.network_address + env.worker_config.network_offset + index)
        return IPConfig(
            ip_address=str(address),
            gateway=str(env.network.subnet.network_address + 1),
            dns_servers=env.network.dns_servers,
            domains=env.network.domains
        )


class NodeProperties:
    """Node properties passed to a Node and used to initialize and configure it."""

    def __init__(self, index: int,
                 node_type: NodeType,
                 resource_pool: environment.ResourcePool,
                 vault_token: str,
                 env: environment.Environment):
        """Initializes NodeProperties using the given parameters.

        Args:
            index: The node's index number
            node_type: The type of node (MASTER or WORKER)
            resource_pool: The ResourcePool that the node will be created in
            vault_token: The Vault token that will be passed to cloud-init for signing SSH host keys on boot
            env: The environment to use when initializing the ode
        """
        self.index = index
        self.node_type = node_type
        self.ip_config = IPConfig.from_environment(index, node_type, env)
        self.resource_pool = resource_pool
        self.vault_token = vault_token
        self.env = env


class Node(pulumi.ComponentResource):
    """A logical representation of a node in a kubernetes cluster

    A Node essentially represents a virtual machine in a given cluster. It has a single VirtualMachine object as its
    child which represents the actual resource being deployed in vSphere and a single Cluster object as its parent. The
    node can have two types associated with it: a worker node for kubernetes workers or a master node for kubernetes
    masters. Nodes should not be initialized directly, but rather should be created by configuring a Cluster object.
    """

    def __init__(self, props: NodeProperties, opts=None):
        """ Initializes Node using the given parameters.

        Note that custom component resources normally take a name parameter, however, in the case of a node the name
        is automatically generated based on the given NodeProperties. It is constructed using the given index number
        and the format string provided by the environment.

        Args:
            props: The NodeProperties to configure this node with
            opts: An optional set of ResourceOptions to configure this node with
        """
        if props.node_type == NodeType.MASTER:
            config = props.env.master_config
        else:
            config = props.env.worker_config
        index_str = props.index if props.index > 9 else '0' + str(props.index)
        name = config.name.format(index=index_str, env=props.env.name)
        super().__init__('glab:deploy:node', "node-" + name, None, opts)

        metadata = _render_cloud_init('files/metadata.yml.j2',
                                      hostname=name,
                                      ip_address=props.ip_config.ip_address,
                                      gateway=props.ip_config.gateway,
                                      dns_servers=props.ip_config.dns_servers,
                                      domains=props.ip_config.domains)
        userdata = _render_cloud_init('files/init.sh.j2',
                                      vault_address=props.env.vault_address,
                                      vault_token=props.vault_token)

        self.vm = vsphere.VirtualMachine(
            opts=pulumi.ResourceOptions(parent=self),
            name=name,
            resource_name="vm-" + name,
            resource_pool_id=props.resource_pool.id,
            num_cpus=config.cpus,
            memory=config.memory,
            datastore_id=props.resource_pool.datastore_id,
            guest_id=props.env.node_template.guest_id,
            disks=_build_disks(props.env.node_template),
            clone={
                'templateUuid': props.env.node_template.id
            },
            network_interfaces=[{
                'networkId': props.env.network.id
            }],
            extra_config={
                'guestinfo.metadata': metadata,
                'guestinfo.metadata.encoding': 'base64',
                'guestinfo.userdata': userdata,
                'guestinfo.userdata.encoding': 'base64',
            }
        )

        self.register_outputs({
            "hostname": name,
            "ip_address": props.ip_config.ip_address,
            "type": "master" if props.node_type == NodeType.MASTER else "worker",
        })
