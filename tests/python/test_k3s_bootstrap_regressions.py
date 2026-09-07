"""Focused offline regressions for bootstrap registry policy."""
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.k3s_automation.config import build_composed_model

ROOT = Path(__file__).resolve().parents[2]


def documents():
    fixture = ROOT / 'tests/fixtures/k3s'
    return (yaml.safe_load((fixture / 'intent.yml').read_text()),
            yaml.safe_load((fixture / 'generated-pve.yml').read_text()))


def test_shared_harbor_and_full_name_rewrites():
    intent, inventory = documents()
    mirror = intent['cluster']['registry']['mirrors'][0]
    mirrors = []
    for registry, prefix in [('docker.io', 'dio'), ('quay.io', 'quay'), ('ghcr.io', 'ghcr'),
                             ('gcr.io', 'gcr'), ('nvcr.io', 'nvcr'),
                             ('registry.k8s.io', 'k8s'), ('k8s.gcr.io', 'k8s')]:
        item = deepcopy(mirror)
        item.update(registry=registry, endpoint='https://harbor.synthetic.invalid:883',
                    rewrites={'(^.+$)': prefix + '/$1'})
        mirrors.append(item)
    intent['cluster']['registry']['mirrors'] = mirrors
    model = build_composed_model(intent, inventory)
    assert len(model['cluster']['registry']['mirrors']) == 7
    assert model['cluster']['registry']['mirrors'][0]['rewrites'] == {'(^.+$)': 'dio/$1'}


@pytest.mark.parametrize('field,value', [('auth_ref', 'op://synthetic/other/credentials'),
                                      ('ca_sha256', 'f' * 64)])
def test_shared_endpoint_conflicts_fail(field, value):
    intent, inventory = documents()
    first = intent['cluster']['registry']['mirrors'][0]
    second = deepcopy(first)
    second.update(registry='quay.io')
    second[field] = value
    intent['cluster']['registry']['mirrors'] = [first, second]
    with pytest.raises(ValidationError, match='conflicting'):
        build_composed_model(intent, inventory)


def test_rewrite_replacement_requires_capture():
    intent, inventory = documents()
    intent['cluster']['registry']['mirrors'][0]['rewrites'] = {'^rancher$': 'dio/$1'}
    with pytest.raises(ValidationError, match='capture'):
        build_composed_model(intent, inventory)
