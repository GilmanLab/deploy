import environment
from itertools import cycle
import pulumi
import pulumi_vsphere as vsphere
import hvac
import node
from typing import Any, Dict, List

MINIMUM_NUM_NODES = 3


class ClusterProperties:
    def __init__(self, nodes: int, masters: int, env: environment.Environment):
        self.nodes = nodes
        self.masters = masters
        self.env = env


class Cluster(pulumi.ComponentResource):
    def __init__(self, name: str, props: ClusterProperties, opts=None):
        super().__init__('glab:deploy:cluster', name, None, opts)
        self.name = name
        self.node_count = props.nodes

        if props.nodes < 3:
            raise Exception("Invalid node count: {}. The cluster must have three or more nodes".format(props.nodes))
        if not props.masters:
            raise Exception("Invalid master count: {}. The cluster must have at least one master".format(props.masters))
        if not props.env.pools:
            raise Exception("Must provide at least one resource pool for creating nodes")

        self.props = props
        self.nodes = {
            node.NodeType.MASTER: [],
            node.NodeType.WORKER: [],
        }

        client = hvac.Client(url=props.env.vault_address)
        self.token = client.create_token(policies=['ssh-signer'], lease='60m')['auth']['client_token']

        # Sort pools by weight
        props.env.pools.sort(key=lambda p: p.weight, reverse=True)

        # Distribute the master nodes across the resource pools
        self.add_nodes(node.NodeType.MASTER, self.props.masters)

        # The number of nodes requested minus the number of masters created should be the number of worker nodes needed
        worker_count = self.node_count - len(self.nodes[node.NodeType.MASTER])

        # Distribute the worker nodes across the resource pools
        self.add_nodes(node.NodeType.WORKER, worker_count)

        self.masters = ['{}.{}'.format(m.vm.name, props.env.domain) for m in self.nodes[node.NodeType.MASTER]]
        self.workers = ['{}.{}'.format(w.vm.name, props.env.domain) for w in self.nodes[node.NodeType.WORKER]]
        self.register_outputs({
            "name": self.name,
            "nodes": self.node_count,
            "masters": self.masters,
            "workers": self.workers,
        })

    def add_nodes(self, node_type: node.NodeType, count: int):
        c = cycle(self.props.env.pools)
        for i in range(0, count):
            self.nodes[node_type].append(self.make_node(node_type, next(c)))

    def make_node(self, node_type: node.NodeType, pool: environment.ResourcePool):
        return node.Node(props=node.NodeProperties(
            index=len(self.nodes[node_type]) + 1,
            node_type=node_type,
            resource_pool=pool,
            vault_token=self.token,
            env=self.props.env
        ),
            opts=pulumi.ResourceOptions(parent=self))