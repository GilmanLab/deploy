#!/usr/bin/env bash

function help {
    echo "Usage: ./up.sh STACK_NAME"
    echo ""
    echo "Flags:"
    echo "  --only-provision  Skips bringing up infrastructure and only runs Kubespray provisioner"
}

function checkForError {
    if [[ $1 -gt 0 ]]; then
        echo "Error: $2. Aborting..."
        exit 1
    fi
}

if [[ -z "$1" ]]; then
    help
    exit 1
fi

if [[ ! $(pulumi stack --show-name) == "$1" ]]; then
    echo "Changing to stack $1..."
    pulumi stack select $1
    checkForError $? "invalid Stack specified"
fi

echo "$2"
if [[ ! "$2" == "--only-provision" ]]; then
#    echo "Bringing up cluster..."
#    pulumi up -y
    checkForError $? "failed bringing up cluster infrastrucure, cluster may be in an incomplete state"
fi

name=$(pulumi stack output cluster | jq -r .name)
env_name=$(pulumi stack output environment | jq -r .name)
master=$(pulumi stack output cluster | jq -r .masters[0])

echo "Pulling down kubespray..."
rm -rf /tmp/kubespray &> /dev/null
git clone https://github.com/kubernetes-sigs/kubespray /tmp/kubespray

echo "Copying inventory over..."
cp -r inv/${env_name} /tmp/kubespray/inventory

echo "Creating inventory file..."
pulumi stack output cluster | python inv.py > /tmp/kubespray/inventory/${env_name}/inventory.ini
checkForError $? "failed generating Ansible inventory"

echo "Configuring cluster..."
ansible-playbook -i /tmp/kubespray/inventory/${env_name}/inventory.ini --become --become-user=root /tmp/kubespray/cluster.yml
checkForError "failed provisioning the cluster, it may be in an incomplete state"

echo "Pulling down kube config..."
mkdir -p ~/.kube/custom-contexts/${name}
ssh -t josh@${master} "sudo cat /etc/kubernetes/admin.conf" > ~/.kube/custom-contexts/${name}/config.yml

echo "Done!"