"""External status conversion does not decide domain success or coerce values."""
import pytest

from iaas_automation.common.conversion import normalize_response_status


@pytest.mark.parametrize('value, expected', [
    ('OK\n\n', 'ok'), (' \tOk\r\n', 'ok'), ('ok', 'ok'),
    (' Error (1)\n', 'error (1)'), (' STOPPED ', 'stopped'),
    ('unexpected-token', 'unexpected-token'),
])
def test_external_status_text(value, expected):
    assert normalize_response_status(value) == expected


@pytest.mark.parametrize('value', [None, '', ' \n\t', True, 0, b'OK', {}, []])
def test_non_text_or_blank_status_is_unknown(value):
    assert normalize_response_status(value) is None
