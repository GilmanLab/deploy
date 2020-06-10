import pulumi
import pulumi_vsphere as vsphere
import base64
import environment
from enum import Enum
from typing import Any, Dict, List
from jinja2 import Template


def _build_disks(template: vsphere.VirtualMachine) -> List[Dict[str, Any]]:
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
    with open(path, 'r') as f:
        rendered = Template(f.read()).render(**kwargs)
    return base64.b64encode(rendered.encode('utf-8')).decode('utf-8')


class NodeType(Enum):
    MASTER = 1
    WORKER = 2


class IPConfig:
    def __init__(self, ip_address: str, gateway: str, dns_servers: List[str], domains: List[str]):
        self.ip_address = ip_address
        self.gateway = gateway
        self.dns_servers = dns_servers
        self.domains = domains

    @classmethod
    def from_environment(cls, index: int, node_type: NodeType, env: environment.Environment):
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
    def __init__(self, index: int,
                 node_type: NodeType,
                 resource_pool: environment.ResourcePool,
                 vault_token: str,
                 env: environment.Environment):
        self.index = index
        self.node_type = node_type
        self.ip_config = IPConfig.from_environment(index, node_type, env)
        self.resource_pool = resource_pool
        self.vault_token = vault_token
        self.env = env


class Node(pulumi.ComponentResource):
    def __init__(self, props: NodeProperties, opts=None):
        if props.node_type == NodeType.MASTER:
            config = props.env.master_config
        else:
            config = props.env.worker_config
        name = config.name.format(num=props.index if props.index > 9 else '0' + str(props.index))
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

