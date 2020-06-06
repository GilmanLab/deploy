import glab
import node

lab = glab.GLab()

worker08 = node.KubeNode(
    lab=lab,
    index=8,
    node_type=glab.NodeType.WORKER,
    vm_size=glab.VMSize.S,
    env=glab.EnvType.DEV,
    pool=str(lab.clusters['Lab'].resource_pool_id),
    datastore=lab.datastores['vsan'].id,
    template=lab.templates['kube']
).build()