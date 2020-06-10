# GilmanLab Cluster Deployment

This repository provides the Pulumi infrastructure and configuration files for deploying a Kubernetes cluster to glab.

## Overview

The glab infrastructure deployment process attempts to adopt the "infrastructure as code" model as much as possible. 
Pulumi is the primary technology that drives this methodology as well as the actual deployment process. Rather than
manually specifying which resources to create for a cluster through the use of code the chosen approach relies on
setting specific Stack configuration values which in turn will affect how a cluster is deployed. Pulumi has the concept
of a *Stack* in order to enforce the DRY principle as much as possible. This deployment leverages that concept and
focuses on using the configuration data within a stack in order to determine how to create and deploy the cluster. See
below for usage instructions and additional commentary on the stack configuration data.

## Usage

Usage varies depending on whether a new or existing stack is created. For details on how to configure a stack please
see the configuration section below.

### Creating a new stack

Use the Pulumi CLI to create a new stack:

```bash
$> pulumi stack init <stack name>
```

Configure the stack using the `Pulumi.<stack name>.yaml` file. It's recommended to copy an existing stack configuration
and then make the necessary tweaks. Once the stack is configured a new cluster can be created with:

```bash
./up.sh <stack name>
```

### Using an existing stack

Simply specify the stack you want to bring up:

```bash
./up.sh <stack name>
```

## Stack Outputs

When a cluster is turned up for a stack it generates output data which is later used for configuring the cluster using
Kubespray. The output structure is as follows:

* cluster
  * name: The name of the cluster (used to name the actual cluster configured by Kubespray)
  * node_count: The total number of nodes creating for this cluster
  * masters: A list of hostnames for nodes which are configured to be masters
  * workers: A list of hostnames for nodes which are configured to be workers
  
The `up.sh` script uses this output to dynamically create the Ansible inventory which Kubespray uses for bootstrapping
the cluster:

```bash
pulumi stack output cluster | python inv.py > /tmp/kubespray/inventory/glab/inventory.ini
```

## Stack Configuration

Rather than modfying the underlying code for each infrastructure change, Pulumi is configured to use a set of
configuration data provided by the Stack. This configuration data informs Pulumi about the environment in which the 
cluster is going to be created as well as the specifications of the cluster like its name and number of nodes.

The best method for configuring a new stack is to copy the `Pulumi.<stack name>.yaml` file contents to the new stack
and then make the necessary modifications. Each possible configuration parameter is described below:

* `glab:cluster`
  * `masters`: The number of masters to create for the cluster (counts against node total)
  * `name`: The name of the cluster (used to name the actual cluster configured by Kubespray)
  * `nodes`: The number of nodes to create for this cluster (minimum number is 3)
* `glab:env`
  * `datacenter`: The name of the vSphere datacenter where the cluster will be deployed
  * `domain`: The domain name used to generate hostnames for the Ansible inventory file
  * `network`
    * `domains`: A list of default search domains used to configure a node's network interface
    * `dns_servers`: A list of DNS servers used to configure a node's network interface
    * `name`: The name of the vSphere network/port group which will be assigned to a node's NIC
    * `subnet`: The subnet to use when generating static IP addresses for nodes
  * `name`: The name of this environment
  * `node`
    * `master`
      * `name`: The format string which will be used to name master nodes (ex. `master{index}-{env}`)
        * `index`: The index of the node (i.e. `01`)
        * `env`: The name of the environment
      * `network_offset`: The offset applied when generating static IP addresses (i.e. if subnet is 192.168.1.0 and offset is 20, the first master node will have a static IP address of 192.168.1.21)
      * `cpus`: The number of CPUs to assign to master nodes
      * `memory`: The amount of memory (in MB) to assign to master nodes
    * `worker`: same as above except targeted at worker nodes
  * `pools`: A list of resource pools which nodes will be deployed against
    * `type`: The type of resource pool, either *host* or *cluster*
    * `name`: The name of the cluster or host as defined in vSphere
    * `datastore`: The datastore that will be used for nodes deployed in this resource group
    * `weight`: The weight which determines how nodes are distributed. Higher weights result in the pool having more nodes deployed against it.
  * `template`: The name of the VM template which will be cloned when creating nodes
  * `vault_address`: The address to a Vault server which will be used when nodes sign their SSH host keys on boot via cloud-init
  
## Cluster Creation

The process followed for creating a cluster is contained within `up.sh` and can be summarized as follows:

1. Issue `pulumi up` to deploy the infrastructure for the cluster
2. Pull down the Kubespray repository to a temporary directory
3. Generate an Ansible inventory using the Stack outputs
4. Run Kubespray to bootstrap the cluster
5. Pull down the kube admin config file for working with the new cluster

After completion a fully bootstrapped Kubernetes cluster will be available. 

## Cluster Modification

There currently is not an automated way for modifying an existing cluster. It's possible to modify the Stack
configuration and then apply the changes using `pulumi up`, however, any nodes added or removed from the cluster will
not be configured correctly. There are future plans to work with Kubespray to dynamically add and remove nodes from the
cluster. Making changes to the resource sizes (i.e. adding more CPUs or RAM) is possible using the aforementioned 
method.