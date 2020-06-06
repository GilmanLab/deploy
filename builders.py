import pulumi_vsphere as vsphere
from typing import Any, Callable, Dict, List


def build_clusters(datacenter: vsphere.Datacenter, clusters: List[str]) -> Dict[str, vsphere.ComputeCluster]:
    return _build(clusters,
                  lambda name: vsphere.get_compute_cluster(datacenter_id=str(datacenter.id), name=name))


def build_datastores(datacenter: vsphere.Datacenter, datastores: List[str]) -> \
        Dict[str, vsphere.AwaitableGetDatastoreResult]:
    return _build(datastores,
                  lambda name: vsphere.get_datastore(datacenter_id=str(datacenter.id), name=name))


def build_hosts(datacenter: vsphere.Datacenter, hosts: List[str]) -> Dict[str, vsphere.Host]:
    return _build(hosts,
                  lambda name: vsphere.get_host(datacenter_id=str(datacenter.id), name=name))


def build_networks(datacenter: vsphere.Datacenter, networks: List[str]) -> Dict[str, vsphere.AwaitableGetNetworkResult]:
    return _build(networks,
                  lambda name: vsphere.get_network(datacenter_id=str(datacenter.id), name=name))


def build_templates(datacenter: vsphere.Datacenter, templates: List[str]) -> Dict[str, vsphere.VirtualMachine]:
    return _build(templates,
                  lambda name: vsphere.get_virtual_machine(datacenter_id=str(datacenter.id), name=name))


def _build(names: List[str], builder: Callable) -> Dict[str, Any]:
    result = {}
    for n in names:
        result[n] = builder(n)
    return result
