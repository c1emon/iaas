"""Current acceptance/recovery admission without converting legacy approval."""
from __future__ import annotations

from typing import Any

from iaas.common.errors import require
from iaas.pve_acceptance_contracts import OneShotAdmission, canonical_digest
from iaas.runtime_execution.pve_contracts import validate_vmid_reservation


def validate_one_shot_admission(value: Any, *, request: dict, preview: dict,
                                execution_id: str, image_digest: str,
                                vmids: list[int], recovery_of: str | None = None) -> dict:
    try:
        require(isinstance(value, dict) and type(value.get('schema_version')) is int,
                'invalid one-shot admission')
        admission = OneShotAdmission.model_validate(value).model_dump()
    except Exception:
        raise ValueError('invalid one-shot admission v2') from None
    require(admission['execution_id'] == execution_id and bool(execution_id), 'admission execution conflicts')
    require(admission['request_digest'] == canonical_digest(request), 'admission request digest conflicts')
    require(admission['plan_digest'] == preview['preview_digest'].removeprefix('sha256:'), 'admission preview conflicts')
    require(admission['target'] == request['target'] == preview['target'], 'admission target conflicts')
    require(admission['deadlines'] == request['deadlines'], 'admission deadlines conflict')
    require(admission['runtime'] == request['runtime'] == preview['runtime'] == {'image_digest': image_digest},
            'admission runtime conflicts')
    consumption, pending, serialization = (admission[name] for name in ('consumption', 'pending', 'serialization'))
    require(consumption.get('reserved') is True and serialization.get('held') is True,
            'current consumption and serialization required')
    for record, key in ((consumption, 'reservation_id'), (pending, 'record_id'), (serialization, 'context_id')):
        require(isinstance(record.get(key), str) and bool(record[key]), 'admission association missing')
    validate_vmid_reservation(admission, cluster_scope=request['cluster_scope'], vmids=vmids)
    require(admission.get('recovery_of') == recovery_of and recovery_of != execution_id,
            'admission recovery association conflicts')
    if recovery_of is not None:
        require(pending.get('execution_id') == request['caller_association']['execution_id'],
                'recovery caller pending association conflicts')
    return admission
