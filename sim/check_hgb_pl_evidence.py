"""核对独立PL实板原始日志及计时汇总，不操作板卡。"""
from pathlib import Path
import json
import re
import math

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'docs/evidence/hgb_pl_20261101'
s=json.loads((base/'summary.json').read_text(encoding='utf-8'))
raw=(base/'serial.log').read_text(encoding='utf-8')
assert 'FAIL' not in raw and 'PASS HGB_PL vectors=160' in raw
rows=[tuple(map(int,m)) for m in re.findall(r'BEAT,(\d+),ARM_ticks,(\d+),PL_call_ticks,(\d+),PL_cycles,(\d+)',raw)]
assert len(rows)==160 and [r[0] for r in rows]==list(range(160))
for i,name in enumerate(('arm_ticks','pl_call_ticks','pl_core_cycles'),1):
    assert sum(r[i] for r in rows)==s[name]
assert math.isclose(s['call_speedup'],s['arm_ticks']/s['pl_call_ticks'])
assert math.isclose(s['core_speedup'],(s['arm_ticks']/s['timer_hz'])/(s['pl_core_cycles']/s['pl_clock_hz']))
assert s['timing_setup_slack_ns']>=0 and s['timing_hold_slack_ns']>=0
assert s['score_mismatches']==0 and s['qualified'] is False
assert 'All user specified timing constraints are met.' in (base/'timing.rpt').read_text()
print(json.dumps(dict(passed=True,vectors=160,call_speedup=s['call_speedup'],scope='既有日志汇总校验，不是新实板运行'),ensure_ascii=False))
