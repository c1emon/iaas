"""Ordinary VM pool placement and optional inclusive acceptance reservations."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from iaas.common.errors import ValidationError
from iaas.common.io import load_yaml
from iaas.pve_inventory.inventory.model import build_model
from iaas.pve_inventory.inventory.render import render_outputs
from iaas.pve_inventory.inventory.validation.cluster import validate_cluster
from iaas.pve_inventory.inventory.validation.vm import validate_vms

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/environment/inventory'


def documents():
    return copy.deepcopy(load_yaml(FIXTURES / 'pve-cluster.yml')), copy.deepcopy(load_yaml(FIXTURES / 'vms.yml'))


@pytest.mark.parametrize('pool', [None, 'deployment-pool'])
def test_exact_pool_and_reservation_survive_generation(pool):
    cluster_doc, vms_doc = documents()
    cluster_doc['reserved_vm_id_ranges']['acceptance'] = [800, 850]
    cluster_doc['reserved_vm_id_ranges']['ephemeral_lab'][1] = 799
    cluster_doc['vm_defaults']['pool'] = 'unused-default'
    for vm in vms_doc['vms']:
        if pool is None:
            vm.pop('pool', None)
        else:
            vm['pool'] = pool
    state = validate_cluster(cluster_doc)
    model = build_model(state, validate_vms(vms_doc, state))
    output = render_outputs(model)
    payload = json.loads(output['tfvars'])
    assert payload['cluster']['reserved_vm_id_ranges']['acceptance'] == [800, 850]
    assert all(vm['pool'] == pool for vm in payload['vms'])
    assert 'acceptance: 800–850 (inclusive)' in output['docs']
    assert f"pool {pool or 'none'}" in output['docs']


@pytest.mark.parametrize('pool', ['', ' ', 'bad/pool', 1])
def test_invalid_pool_rejected(pool):
    cluster_doc, vms_doc = documents()
    vms_doc['vms'][0]['pool'] = pool
    with pytest.raises(ValidationError, match='pool must be null or a nonempty PVE-safe string'):
        validate_vms(vms_doc, validate_cluster(cluster_doc))
    cluster_doc['vm_defaults']['pool'] = pool
    with pytest.raises(ValidationError, match='pool must be null or a nonempty PVE-safe string'):
        validate_cluster(cluster_doc)


@pytest.mark.parametrize('bounds', [[799, 850], [99, 100], [850, 800], [800, True]])
def test_invalid_acceptance_interval_rejected(bounds):
    cluster_doc, _ = documents()
    cluster_doc['reserved_vm_id_ranges']['ephemeral_lab'][1] = 799
    cluster_doc['reserved_vm_id_ranges']['acceptance'] = bounds
    with pytest.raises(ValidationError):
        validate_cluster(cluster_doc)


@pytest.mark.parametrize('vmid', [800, 825, 850])
def test_ordinary_vm_excluded_from_acceptance_interval(vmid):
    cluster_doc, vms_doc = documents()
    cluster_doc['reserved_vm_id_ranges']['ephemeral_lab'][1] = 799
    cluster_doc['reserved_vm_id_ranges']['acceptance'] = [800, 850]
    state = validate_cluster(cluster_doc)
    vms_doc['vms'][0]['vmid'] = vmid
    with pytest.raises(ValidationError, match='ordinary VMID must not use the acceptance range'):
        validate_vms(vms_doc, state)


@pytest.mark.parametrize('pool', [None, 'deployment-pool'])
def test_actual_hcl_resources_preserve_pool_input(pool):
    import hcl2

    module = ROOT / 'automation/opentofu/modules/pve-cloudinit-vm/main.tf'
    with module.open() as stream:
        parsed = hcl2.load(stream)
    resources = {
        branch.strip('"'): body
        for resource in parsed['resource']
        for resource_type, declarations in resource.items()
        if resource_type.strip('"') == 'proxmox_virtual_environment_vm'
        for branch, body in declarations.items()
    }
    assert set(resources) == {'protected', 'unprotected'}
    cluster_doc, vms_doc = documents()
    vms_doc['vms'][0]['pool'] = pool
    state = validate_cluster(cluster_doc)
    inputs = json.loads(render_outputs(build_model(state, validate_vms(vms_doc, state)))['tfvars'])
    for body in resources.values():
        assert body['pool_id'] == '${var.vm.pool}'
        # The resource's direct attribute reference consumes this exact generated value,
        # including null. No coalesce/default/template expression is permitted.
        assert inputs['vms'][0]['pool'] == pool
