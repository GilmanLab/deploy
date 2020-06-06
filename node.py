import pulumi_vsphere as vsphere
import glab
import ipaddress
import hvac
import base64
import os
from jinja2 import Template
from typing import Any, Dict, List


def _render_cloud_init(path: str, **kwargs) -> str:
    with open(path, 'r') as f:
        rendered = Template(f.read()).render(**kwargs)
    return base64.b64encode(rendered.encode('utf-8')).decode('utf-8')


class KubeNode:

    def __init__(self, lab: glab.GLab,
                 index: int,
                 node_type: glab.NodeType,
                 vm_size: glab.VMSize,
                 env: glab.EnvType,
                 pool: str,
                 datastore: str,
                 template: vsphere.VirtualMachine):
        self.lab = lab
        # Set name
        num = '0{}'.format(index) if index < 10 else str(index)
        self.name = lab.config['node']['prefixes'][node_type.value] + num

        # Set pool
        self.pool = pool

        # Set resources
        self.cpus = lab.config['vm']['sizes'][vm_size.value]['cpu']
        self.cores = lab.config['vm']['sizes'][vm_size.value]['cores']
        self.memory = lab.config['vm']['sizes'][vm_size.value]['mem']

        # Set datastore
        self.datastore = datastore

        # Set network
        self.network = lab.config['env'][env.value]['network']

        # Set IP address
        ip = ipaddress.ip_network(lab.config['env'][env.value]['subnet'])
        self.ip = str(ip.network_address + lab.config['node']['ip']['offsets'][node_type.value] + index)

        # Set template
        self.template = template

        # Generate token
        client = hvac.Client()
        self.token = client.create_token(policies=['ssh-signer'], lease='25m')['auth']['client_token']

    def _build_disks(self) -> List[Dict[str, Any]]:
        i = 0
        disks = []
        for disk in self.template.disks:
            disks.append({'label': 'disk{}'.format(i),
                          'size': int(float(str(disk['size']))) + 1,  # Have to add 1 to account for rounding errors
                          'unitNumber': i,
                          'thinProvisioned': bool(disk['thinProvisioned']),
                          'eagerlyScrub': bool(disk['eagerlyScrub'])})
            i += 1
        return disks

    def build(self) -> vsphere.VirtualMachine:
        metadata = _render_cloud_init('files/metadata.yml.j2',
                                      hostname=self.name)
        userdata = _render_cloud_init('files/init.sh.j2',
                                      vault_address=os.environ['VAULT_ADDR'],
                                      vault_token=self.token)
        return vsphere.VirtualMachine(resource_name=self.name,
                                      name=self.name,
                                      resource_pool_id=self.pool,
                                      num_cpus=self.cpus,
                                      num_cores_per_socket=self.cores,
                                      memory=self.memory,
                                      guest_id=self.template.guest_id,
                                      datastore_id=self.datastore,
                                      disks=self._build_disks(),
                                      network_interfaces=[{
                                          'networkId': self.lab.networks[self.network].id
                                      }],
                                      clone={
                                          'templateUuid': self.template.id
                                      },
                                      extra_config={
                                          'guestinfo.metadata': metadata,
                                          'guestinfo.metadata.encoding': 'base64',
                                          'guestinfo.userdata': userdata,
                                          'guestinfo.userdata.encoding': 'base64',
                                      })