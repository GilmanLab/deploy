import cluster
import ipaddress
import node
import pulumi
import pulumi_vsphere as vsphere

config = pulumi.Config()
env = config.require_object('env')

# Build the environment for deploying the cluster
dc = vsphere.get_datacenter(env['datacenter'])
network = vsphere.get_network(dc.id, name=env['network']['name'])
template = vsphere.get_virtual_machine(dc.id, name=env['template'])
cc = vsphere.get_compute_cluster(dc.id, name='Lab')
ds = vsphere.get_datastore(dc.id, name='vsan')
env = cluster.Environment(
    name=env['name'],
    network=cluster.Network(
        network_id=str(network.id),
        subnet=ipaddress.ip_network(env['network']['subnet']),
        dns_servers=env['network']['dns_servers'],
        domains=env['network']['domains']
    ),
    node_template=template,
    master_config=cluster.NodeSettings(
        name=env['node']['master']['name'],
        network_offset=env['node']['master']['network_offset'],
        cpus=env['node']['master']['cpus'],
        memory=env['node']['master']['memory']
    ),
    worker_config=cluster.NodeSettings(
        name=env['node']['worker']['name'],
        network_offset=env['node']['worker']['network_offset'],
        cpus=env['node']['worker']['cpus'],
        memory=env['node']['worker']['memory']
    ),
    vault_address=env['vault_address']
)

node = node.Node(props=node.NodeProperties(
    index=1,
    node_type=node.NodeType.MASTER,
    resource_pool=cluster.ResourcePool(
        id=str(cc.resource_pool_id),
        datastore_id=ds.id,
        weight=1
    ),
    vault_token='test',
    env=env
))