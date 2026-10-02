"""Perl interface fixture for the helper's native parser/compiler integration.

PVE modules are not installed locally. These representative module fixtures
exercise copied pool membership, NoAccess and token intersection through the
real Perl subprocess; they do not qualify installed PVE module versions.
"""
import importlib.machinery
import importlib.util
import json
import subprocess

import pytest


@pytest.mark.parametrize('case', ['pool_only', 'direct_noaccess', 'pool_noaccess', 'token_intersection'])
def test_native_module_interface_compiles_only_in_memory_membership(tmp_path, monkeypatch, case):
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'automation/pve-node/bin/iaas-pve-snippet-delete'
    loader = importlib.machinery.SourceFileLoader('native_permissions_fixture', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    helper = importlib.util.module_from_spec(spec)
    loader.exec_module(helper)
    modules = tmp_path / 'PVE'
    modules.mkdir()
    (modules / 'AccessControl.pm').write_text('''package PVE::AccessControl;
use JSON::PP qw(decode_json);
sub parse_user_config { return decode_json($_[1]); }
1;
''')
    # Representative native interface semantics; actual PVE ACL parsing and
    # compilation remain delegated to installed modules in the shipped helper.
    (modules / 'RPCEnvironment.pm').write_text('''package PVE::RPCEnvironment;
sub permissions {
    my ($self, $principal, $path) = @_;
    my $cfg = $self->{user_cfg};
    my ($user, $token) = split(/!/, $principal);
    my $compile = sub {
        my ($identity) = @_;
        my $direct = $cfg->{direct}->{$identity} || {};
        return {} if exists($direct->{NoAccess});
        my $pool = $cfg->{poolgrants}->{$identity} || {};
        return $pool if $path eq '/pool/acceptance';
        return { %$direct } if !$cfg->{pools}->{acceptance}->{vms}->{9100};
        return {} if exists($pool->{NoAccess});
        return { %$direct, %$pool };
    };
    my $owner = $compile->($user);
    my $token_grants = $compile->($principal);
    return { map { $_ => 0 } grep { exists($owner->{$_}) } keys(%$token_grants) };
}
1;
''')
    grants = {'VM.Allocate': 0, 'VM.PowerMgmt': 0}
    cfg = {'pools': {'acceptance': {'vms': {}}}, 'direct': {},
           'poolgrants': {'caller@pve': grants.copy(), 'caller@pve!token': grants.copy()}}
    if case == 'direct_noaccess':
        cfg['direct']['caller@pve'] = {'NoAccess': 0}
    if case == 'pool_noaccess':
        cfg['poolgrants']['caller@pve!token'] = {'NoAccess': 0}
    if case == 'token_intersection':
        cfg['poolgrants']['caller@pve!token'].pop('VM.PowerMgmt')
    fixture = tmp_path / 'user.cfg'
    fixture.write_text(json.dumps(cfg))
    original = fixture.read_bytes()
    run = subprocess.run
    def fixture_run(args, **kwargs):
        args = list(args)
        args[2] = args[2].replace('/etc/pve/user.cfg', str(fixture))
        args[1:1] = ['-I', str(tmp_path)]
        return run(args, **kwargs)
    monkeypatch.setattr(helper.subprocess, 'run', fixture_run)
    answer = helper.prospective_permissions('caller@pve!token', 9100, 'acceptance',
                                            helper.Deadline('2099-01-01T00:00:00Z'))
    assert answer['complete'] is True
    assert answer['current_direct'] == {}
    if case == 'pool_only':
        assert answer['grants'] == grants
    elif case in ('direct_noaccess', 'pool_noaccess'):
        assert answer['grants'] == {}
    else:
        assert answer['grants'] == {'VM.Allocate': 0}
    assert fixture.read_bytes() == original
