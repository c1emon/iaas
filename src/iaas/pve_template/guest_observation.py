"""Fixed, read-only guest observation for selected disk-growth/network acceptance."""

GENERAL_GUEST_OBSERVATION = r'''
import json, os, pathlib, subprocess
def output(command):
    return subprocess.check_output(command, text=True).strip()
cloud = json.loads(output(['cloud-init', 'status', '--format', 'json']))
if cloud.get('status') == 'done':
    root = output(['findmnt', '-n', '-o', 'SOURCE', '/'])
    parent = output(['lsblk', '--nodeps', '-n', '-o', 'PKNAME', root])
    fs = os.statvfs('/')
    addresses = json.loads(output(['ip', '-j', 'address']))
    routes = json.loads(output(['ip', '-j', 'route']))
    cloud['general_template'] = {
        'root_partition_bytes': int(output(['blockdev', '--getsize64', root])),
        'root_disk_bytes': int(output(['blockdev', '--getsize64', '/dev/' + parent])),
        'root_filesystem_bytes': fs.f_blocks * fs.f_frsize,
        'addresses': [str(a['local']) + '/' + str(a['prefixlen']) for row in addresses for a in row.get('addr_info', [])],
        'default_gateways': [row['gateway'] for row in routes if row.get('dst') == 'default' and 'gateway' in row],
        'nameservers': [row.split()[1] for row in pathlib.Path('/etc/resolv.conf').read_text().splitlines() if row.startswith('nameserver ')],
        'machine_id_initialized': len(pathlib.Path('/etc/machine-id').read_text().strip()) == 32,
        'instance_id': output(['cloud-init', 'query', 'instance_id']),
    }
print(json.dumps(cloud))
'''
