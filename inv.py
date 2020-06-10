"""A small helper script for generating an Ansible inventory file based on the Pulumi stack outputs"""

import json
import sys

from jinja2 import Template

j = json.loads(sys.stdin.read())

all_nodes = j['masters'] + j['workers']
# Min cluster size is 3 nodes, in which case they all need to be etcd members
# otherwise just grab the first 3 nodes
if len(all_nodes) <= 3:
    etcd_nodes = all_nodes
else:
    etcd_nodes = all_nodes[:3]

with open('files/inventory.ini.j2', 'r') as f:
    rendered = Template(f.read()).render(all=all_nodes,
                                         masters=j['masters'],
                                         workers=j['workers'],
                                         etcd_nodes=etcd_nodes)

print(rendered)
