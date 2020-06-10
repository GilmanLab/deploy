"""The Cluster class and its helper classes."""
from itertools import cycle

import hvac
import pulumi

import environment
import node

MINIMUM_NUM_NODES = 3


class ClusterProperties:
    """Cluster properties passed to a Cluster and used to initialize and configure it."""

    def __init__(self, nodes: int, masters: int, env: environment.Environment):
        """Initializes ClusterProperties using the given parameters.

        Args:
            nodes: The number of nodes to create for this cluster
            masters: How many of the nodes are configured to be a kubernetes master
            env: The environment in which to deploy this cluster
        """
        self.nodes = nodes
        self.masters = masters
        self.env = env


class Cluster(pulumi.ComponentResource):
    """A logical representation of a kubernetes cluster.

    A cluster essentially represents a series of nodes which are collectively used to create a kubernetes cluster. It
    has a series of child nodes which may be configured as a master or a worker. The parent of a cluster is always a
    stack as a stack should have a one-to-one relationship with a cluster. The actual implementation of creating the
    underlying virtual infrastructure for the cluster is handled by the nodes which the cluster configures. The cluster
    handles creating and assigning nodes to the resource pools configured in the environment. For more details on how
    this is done refer to the documentation for the ResourcePool type."""

    def __init__(self, name: str, props: ClusterProperties, opts=None):
        """Initializes Cluster using the given parameters.

        Args:
            name: The name of the cluster (this impacts the actual cluster name when it is configured by Kubespray)
            props: The ClusterProperties to configure this cluster with
            opts: An optional set of ResourceOptions to configure this cluster with
        """
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

    def add_nodes(self, node_type: node.NodeType, count: int) -> None:
        """Performs a round-robin distribution of the given node type to the configured environment

        This method uses the resource pools configured in environment.pools and distributes the number of given node
        types in a round-robin style to the pools. It's expected that the resource pools are already sorted by weight.

        Args:
            node_type: The type of node to create, either MASTER or WORKER
            count: The number of nodes to create and distribute to the configured environment
        """
        c = cycle(self.props.env.pools)
        for i in range(0, count):
            self.nodes[node_type].append(self.make_node(node_type, next(c)))

    def make_node(self, node_type: node.NodeType, pool: environment.ResourcePool) -> node.Node:
        """Creates a node of the given type in the given resource pool.

        Args:
            node_type: The type of node to create, either MASTER or WORKER
            pool: The resource pool to create the node in

        Returns:
            The created Node object
        """
        return node.Node(props=node.NodeProperties(
            index=len(self.nodes[node_type]) + 1,
            node_type=node_type,
            resource_pool=pool,
            vault_token=self.token,
            env=self.props.env
        ),
            opts=pulumi.ResourceOptions(parent=self))
