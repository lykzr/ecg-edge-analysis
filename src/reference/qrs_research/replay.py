"""从同一输入重建26的两个源事件流；仅离线重放，不称完整在线运行时。"""
from collections import deque
from statistics import median
from . import candidate, gradient


def replay(samples, configuration=None):
    configuration = dict(configuration or {})
    configuration.setdefault('threshold', 1.0)
    positions, primary, _ = candidate.replay(samples, configuration)
    _, secondary, _ = gradient.replay(samples, configuration)
    del positions
    cache = deque()
    k = changed = tail = 0
    output = []
    for emitted, position, _ in primary:
        deadline = emitted + 72
        if deadline >= len(samples):
            tail += 1
            continue
        while k < len(secondary) and secondary[k][0] <= deadline:
            cache.append(secondary[k])
            k += 1
            if len(cache) > 32:
                cache.popleft()
        while cache and deadline - cache[0][0] > 1440:
            cache.popleft()
        nearby = [e for e in cache if 0 < abs(e[1] - position) <= 10]
        if nearby:
            alternate = min(nearby, key=lambda e: abs(e[1] - position))[1]
            lo, hi = sorted([position, alternate])
            flank = samples[max(0, lo-54):max(0, lo-28)] + samples[hi+29:min(deadline, hi+54)+1]
            baseline = median(flank) if flank else samples[position]
            a, b = samples[position]-baseline, samples[alternate]-baseline
            if a*b < 0 and .8 <= abs(b/a) <= 1.25 and (not output or alternate > output[-1][1]):
                position = alternate
                changed += 1
        output.append((deadline, position, 0 if not output else position-output[-1][1]))
    return [i for _, i, _ in output], output, dict(
        changed=changed, tail_pending=tail, qualified=False,
        runtime_implementation=False,
        scope='offline reconstruction of research26; whole input/events and diagnostic audit retained; not bounded online/PS/RTL/board',
    )
