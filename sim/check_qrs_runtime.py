"""冻结运行时与原研究26来源；只核哈希/门槛，不声明运行或准确性通过。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    p = json.loads((root / 'data/qrs_runtime_protocol.json').read_text(encoding='utf-8'))
    old = json.loads((root / 'data/qrs_research_protocol.json').read_text(encoding='utf-8'))
    assert p['scope'] == 'KNOWN_DATA_DEVELOPMENT_REPRODUCTION' and not p['independent_test']
    assert not p['qualified']
    assert p['gate'] == old['gate']
    for role in ('development_records', 'evaluation_records'):
        assert p[role] == old[role]
    for name, h in p['source_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == h, name
    result = json.loads((root / 'data/results/qrs_research26_20261023.json').read_text(encoding='utf-8'))
    assert result['metrics']['records_passing'] == 41 and result['metrics']['records_total'] == 42
    assert result['metrics']['failing_records'] == ['105'] and not result['independent_test']
    return dict(passed=True, source_files=len(p['source_sha256']), gates_unchanged=True,
                qualified=False, board_operated=False)


if __name__ == '__main__':
    print(json.dumps(check()))
