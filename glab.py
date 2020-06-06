from enum import Enum
import pulumi_vsphere as vsphere
from typing import Any, Dict
import yaml
import builders

CONFIG = 'config.yml'


class EnvType(Enum):
    PROD = 'prod'
    DEV = 'dev'


class NodeType(Enum):
    MASTER = 'master'
    WORKER = 'worker'


class VMSize(Enum):
    XS = 'XS'
    S = 'S'
    M = 'M'
    L = 'L'
    XL = 'XL'


class GLab:
    config: Dict[str, Any]
    datacenter: vsphere.Datacenter
    clusters: Dict[str, vsphere.ComputeCluster]
    hosts: Dict[str, vsphere.Host]
    networks: Dict[str, vsphere.AwaitableGetNetworkResult]
    datastores: Dict[str, vsphere.AwaitableGetDatastoreResult]
    templates: Dict[str, vsphere.VirtualMachine]

    def __init__(self):
        with open(CONFIG, 'r') as f:
            self.config = yaml.load(f.read(), Loader=yaml.Loader)

        self.datacenter = vsphere.get_datacenter(self.config['resources']['datacenter'])
        self.clusters = builders.build_clusters(self.datacenter, self.config['resources']['clusters'])
        self.hosts = builders.build_hosts(self.datacenter, self.config['resources']['hosts'])
        self.networks = builders.build_networks(self.datacenter, self.config['resources']['networks'])
        self.datastores = builders.build_datastores(self.datacenter, self.config['resources']['datastores'])
        self.templates = builders.build_templates(self.datacenter, self.config['resources']['templates'])