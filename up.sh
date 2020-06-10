#!/usr/bin/env bash

echo "Bringing up cluster..."
#pulumi up -y

echo "Pulling down kubespray..."
rm -rf /tmp/kubespray &> /dev/null
git clone https://github.com/kubernetes-sigs/kubespray /tmp/kubespray

echo "Cloning inventory..."
cp -r /tmp/kubespray/inventory/sample /tmp/kubespray/inventory/glab

echo "Creating inventory file..."
pulumi stack output cluster | python inv.py > /tmp/kubespray/inventory/glab/inventory.ini

echo "Setting cluster name..."
name=$(pulumi stack output cluster | jq -r .name)
sed -i "" -e "s/cluster.local/$name/" /tmp/kubespray/inventory/glab/group_vars/k8s-cluster/k8s-cluster.yml

echo "Configuring cluster..."
ansible-playbook -i /tmp/kubespray/inventory/glab/inventory.ini --become --become-user=root /tmp/kubespray/cluster.yml

echo "Pulling down kube config..."
env_name=$(pulumi stack output environment | jq -r .name)
master=$(pulumi stack output cluster | jq -r .masters[0])
mkdir -p ~/.kube/custom-contexts/${name}
ssh -t josh@${master} "sudo cat /etc/kubernetes/admin.conf" > ~/.kube/custom-contexts/${name}/config.yml

echo "Done!"