"""只读解析受支持的Vivado英文报告；缺字段/未知格式不默认通过。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

CHECKS = ('no_clock', 'constant_clock', 'pulse_width_clock',
          'unconstrained_internal_endpoints', 'no_input_delay', 'no_output_delay',
          'multiple_clock', 'generated_clocks', 'loops', 'partial_input_delay',
          'partial_output_delay', 'latch_loops')


def number(value):
    v = float(value)
    if not math.isfinite(v):
        raise ValueError('非有限数字')
    return v


def identity(text):
    result = {}
    for key, label in [('tool', 'Tool Version'), ('design', 'Design'),
                       ('device', 'Device'), ('state', 'Design State')]:
        m = re.search(r'^\|\s*' + label + r'\s*:\s*(.+?)\s*$', text, re.M)
        if not m:
            raise ValueError('报告身份字段缺失：' + label)
        result[key] = m[1]
    return result


def resources(text):
    result = {}
    for key, labels in [('lut', ('Slice LUTs', 'CLB LUTs')),
                        ('ff', ('Slice Registers', 'CLB Registers')),
                        ('bram36', ('Block RAM Tile',)), ('dsp', ('DSPs',))]:
        rows = []
        for line in text.splitlines():
            cells = [s.strip() for s in line.split('|')[1:-1]]
            if len(cells) == 6 and cells[0] in labels:
                used, available = number(cells[1]), number(cells[4])
                if used < 0 or available <= 0 or used > available:
                    raise ValueError('资源数量非法：' + key)
                rows.append(dict(used=used, available=available, percent=used / available * 100))
        if not rows or any(r != rows[0] for r in rows):
            raise ValueError('资源缺失或多处不一致：' + key)
        result[key] = rows[0]
    return result


def timing(text):
    section = text.split('| Design Timing Summary', 1)
    if len(section) != 2:
        raise ValueError('缺少Design Timing Summary')
    lines = section[1].splitlines()
    header = next((i for i, s in enumerate(lines) if 'WNS(ns)' in s and 'WPWS(ns)' in s), None)
    if header is None:
        raise ValueError('不支持的时序汇总表头')
    fields = None
    for line in lines[header + 1:header + 5]:
        parts = line.split()
        if parts and all(set(p) == {'-'} for p in parts):
            continue
        if len(parts) == 12:
            fields = [number(v) for v in parts]
            break
    if fields is None:
        raise ValueError('时序汇总缺值')
    result = {}
    for prefix, start in [('setup', 0), ('hold', 4), ('pulse', 8)]:
        slack, total_slack, failing, endpoints = fields[start:start + 4]
        if failing < 0 or endpoints <= 0 or failing > endpoints or not failing.is_integer() or not endpoints.is_integer():
            raise ValueError('时序端点数量非法')
        result[prefix] = dict(worst_ns=slack, total_negative_ns=total_slack,
                              failing=int(failing), endpoints=int(endpoints))
    counts = {}
    for name, raw in re.findall(r'checking\s+(\w+)\s+\((\d+)\)', text):
        count = int(raw)
        if name in counts and count != counts[name]:
            raise ValueError('重复约束检查不一致：' + name)
        counts[name] = count
    if set(counts) != set(CHECKS):
        raise ValueError('约束检查缺项或出现未支持项')
    clocks = {}
    section = text.split('| Clock Summary', 1)
    if len(section) != 2:
        raise ValueError('缺少Clock Summary')
    for name, period, freq in re.findall(
            r'^\s*(\S+)\s+\{[^}]+\}\s+([\d.]+)\s+([\d.]+)\s*$', section[1].split('Intra Clock Table')[0], re.M):
        period, freq = number(period), number(freq)
        if period <= 0 or freq <= 0 or name in clocks or abs(1000 / period - freq) > .1:
            raise ValueError('时钟表数据非法')
        clocks[name] = dict(period_ns=period, frequency_mhz=freq)
    if not clocks:
        raise ValueError('时钟表为空或格式未支持')
    return result, counts, clocks


def check(utilization, timing_report, *, device=None, clock=None, period_ns=None,
          budget=None, reviewed=None, review_note=''):
    paths = [Path(utilization), Path(timing_report)]
    texts = [p.read_text(encoding='utf-8-sig') for p in paths]
    identities = [identity(t) for t in texts]
    errors = []
    for key in ('design', 'tool', 'state'):
        if identities[0][key] != identities[1][key]:
            errors.append('配对报告身份不一致：' + key)
    def part_base(value):
        # Timing reports may omit the xc prefix and speed grade.
        return re.sub(r'-\d[^-]*$', '', value.lower()).removeprefix('xc').replace('-', '')
    if part_base(identities[0]['device']) != part_base(identities[1]['device']):
        errors.append('配对报告器件不一致')
    if identities[0]['state'].lower() != 'routed':
        errors.append('不是Routed实现结果')
    if device and identities[0]['device'] != device:
        errors.append('器件不匹配')
    usage = resources(texts[0])
    summary, counts, clocks = timing(texts[1])
    for name, row in summary.items():
        if row['worst_ns'] < 0 or row['total_negative_ns'] != 0 or row['failing'] != 0:
            errors.append('时序违例：' + name)
    reviewed = reviewed or {}
    if reviewed and not review_note.strip():
        raise ValueError('接受检查项必须提供review-note')
    if set(reviewed) - set(CHECKS):
        raise ValueError('未知审核检查项')
    for name, count in counts.items():
        if name in reviewed and reviewed[name] != count:
            errors.append('审核数量与报告不一致：' + name)
        elif count and name not in reviewed:
            errors.append('约束检查需核查：' + name + '=' + str(count))
    if (clock is None) != (period_ns is None):
        raise ValueError('clock与period-ns必须成对提供')
    if clock is not None:
        expected = number(period_ns)
        if expected <= 0:
            raise ValueError('周期必须大于0')
        if clock not in clocks or abs(clocks[clock]['period_ns'] - expected) > .001:
            errors.append('目标时钟或周期不匹配')
    budget_data = None
    if budget:
        budget_data = json.loads(Path(budget).read_text(encoding='utf-8-sig'))
        if set(budget_data) != {'max_percent'} or not isinstance(budget_data['max_percent'], dict) or not budget_data['max_percent']:
            raise ValueError('预算需非空max_percent映射')
        for key, limit in budget_data['max_percent'].items():
            if key not in usage or isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 0 <= number(limit) <= 100:
                raise ValueError('预算资源名或阈值非法')
            if usage[key]['percent'] > limit:
                errors.append('超过资源预算：' + key)
    receipts = {role: dict(name=p.name, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
                for role, p in zip(('utilization', 'timing'), paths)}
    return dict(passed=not errors, errors=errors, identities=identities, resources=usage,
                timing=summary, checks=counts, constraints_clean=not any(counts.values()),
                reviewed_checks=reviewed, review_note=review_note, clocks=clocks,
                budget=budget_data, inputs=receipts,
                scope='report parsing only; no DRC, synthesis, hardware access or runtime load measurement')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--utilization', required=True)
    p.add_argument('--timing', required=True)
    p.add_argument('--device')
    p.add_argument('--clock')
    p.add_argument('--period-ns', type=float)
    p.add_argument('--budget')
    p.add_argument('--reviewed-check', action='append', default=[])
    p.add_argument('--review-note', default='')
    a = p.parse_args()
    try:
        reviewed = {}
        for value in a.reviewed_check:
            name, count = value.split('=')
            if name in reviewed or not count.isdigit():
                raise ValueError('审核项重复或数量非法')
            reviewed[name] = int(count)
        result = check(a.utilization, a.timing, device=a.device, clock=a.clock,
                       period_ns=a.period_ns, budget=a.budget, reviewed=reviewed, review_note=a.review_note)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = dict(passed=False, errors=[str(error)])
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
