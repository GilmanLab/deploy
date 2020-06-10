import cluster
import environment
import ipaddress
import node
import pulumi
import pulumi_vsphere as vsphere


config = pulumi.Config()
env_config = config.require_object('env')
cluster_config = config.require_object('cluster')

# Build the environment for deploying the cluster
env = environment.Environment.from_config(env_config)

# Create cluster
c = cluster.Cluster(
    name=cluster_config['name'],
    props=cluster.ClusterProperties(
        nodes=cluster_config['nodes'],
        masters=cluster_config['masters'],
        env=env,
    )
)

pulumi.export("cluster", {
    "name": c.name,
    "node_count": c.node_count,
    "masters": c.masters,
    "workers": c.workers,
})