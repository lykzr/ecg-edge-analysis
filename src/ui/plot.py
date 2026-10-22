"""界面与SVG共用绘图几何；不导入Tk，不读串口或运行检测。"""
from pathlib import Path
from html import escape

def trace_geometry(samples, channel, filtered, width, height):
    """独立缩放两路码值；按像素桶保留最小/最大，避免抽点漏掉窄峰。"""
    left, right, top, bottom = 76, max(77, width - 18), 36, max(37, height - 28)
    selected = samples[-2500:]
    if not selected:
        return [], None
    values = [(s.time_s, getattr(s, channel + '_filtered') if filtered else
               (s.ecg_raw if channel == 'ecg' else s.resp_raw) - 8388608) for s in selected]
    values = [(t, v) for t, v in values if v is not None]
    if not values:
        return [], None
    low, high = min(v for _, v in values), max(v for _, v in values)
    pad = max((high - low) * .08, 1)
    low -= pad; high += pad
    t0, t1 = values[0][0], values[-1][0]
    span = max(t1 - t0, .002)
    buckets = {}
    for t, value in values:
        x = left + (t - t0) / span * (right - left)
        buckets.setdefault(int(x), []).append((x, bottom - (value - low) / (high - low) * (bottom - top)))
    points = []
    for group in buckets.values():
        # 同一像素仍保留先后顺序，且包含首/末和两个极值。
        ids = sorted({0, len(group)-1, min(range(len(group)), key=lambda i: group[i][1]),
                      max(range(len(group)), key=lambda i: group[i][1])})
        points.extend(group[i] for i in ids)
    return points, (low, high, t0, t1, left, right, top, bottom)


def draw_trace(canvas, samples, channel, active, *, filtered=False, title_override=None):
    canvas.delete('all')
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 100 or height < 80:
        return
    points, bounds = trace_geometry(samples, channel, filtered, width, height)
    title = '心电 CH2' if channel == 'ecg' else '呼吸 CH1'
    title += ' · 厂商滤波（历史结果）' if filtered else ' · 有符号原码（未标定）'
    if title_override is not None:
        title = title_override
    canvas.create_text(10, 8, anchor='nw', text=title, fill='#dfe6ec')
    if bounds is None:
        canvas.create_text(width/2, height/2, text='该来源未提供厂商滤波' if filtered and samples else '尚无数据', fill='#9fb0bf')
        return
    lo, hi, t0, t1, left, right, top, bottom = bounds
    for i in range(5):
        y = top + (bottom-top)*i/4
        canvas.create_line(left, y, right, y, fill='#283744')
    if len(points) >= 2:
        canvas.create_line(*[v for p in points for v in p], fill='#58d6a6' if channel == 'ecg' else '#70baff')
    canvas.create_text(left-5, top, anchor='ne', text=f'{hi:.0f}', fill='#9fb0bf')
    canvas.create_text(left-5, bottom, anchor='se', text=f'{lo:.0f}', fill='#9fb0bf')
    label = f'{t0:.3f} → {t1:.3f} 秒（500Hz软件时间，非实测到达时间）'
    if not active:
        label += ' · 历史'
    canvas.create_text(left, height-6, anchor='sw', text=label, fill='#dfe6ec', width=max(width-left-10,1))


def plot_geometry(monitor, width=1000, height=360, margins=(64, 20, 30, 42)):
    """margins=(左, 右, 上, 下)像素；界面按实际Canvas尺寸和DPI传入，SVG沿用默认值。"""
    samples = list(monitor.samples)
    if not samples:
        return {'raw': [], 'filt': [], 'events': [], 'unit': '未提供', 'time_unit': '样本序号'}
    h = monitor.header; left, right, top, bottom = margins[0], width - margins[1], margins[2], height - margins[3]
    first, last = samples[0][1], samples[-1][1]; span = max(last - first, 1)
    values = [v / h.scale if h.scale else v for p in samples for v in (p[2], p[3]) if v is not None]
    low, high = min(values), max(values)
    margin = max((high - low) * .1, .01 if h.scale else 1)
    low -= margin; high += margin
    x = lambda index: left + (index - first) / span * (right - left)
    y = lambda value: bottom - ((value / h.scale if h.scale else value) - low) / (high - low) * (bottom - top)
    paths = {'raw': [], 'filt': []}
    for key, field in [('raw', 2), ('filt', 3)]:
        segment = []; previous = None
        for p in samples:
            if p[field] is None or (previous is not None and p[1] != previous + 1):
                if len(segment) > 1: paths[key].append(segment)
                segment = []
            if p[field] is not None: segment.append((x(p[1]), y(p[field])))
            previous = p[1]
        if len(segment) > 1: paths[key].append(segment)
    return {**paths, 'events': [(x(index), event.seq) for event, index in monitor.visible_events()],
            'unit': 'mV（声明换算）' if h.scale else '码值（未标定）',
            'time_unit': '逻辑采样秒' if h.fs else '样本序号',
            'first': first / h.fs if h.fs else first, 'last': last / h.fs if h.fs else last,
            'low': low, 'high': high}


def save_svg(monitor, path):
    path = Path(path)
    geometry = plot_geometry(monitor); h = monitor.header
    title = '无数据' if h is None else f'{h.source} / {h.detector} / session={h.session}'
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="400" viewBox="0 0 1000 400">',
             '<rect width="1000" height="400" fill="#101820"/>',
             f'<text x="20" y="20" fill="#eeeeee">{escape(title)}</text>']
    for key, color in [('raw', '#58d6a6'), ('filt', '#70baff')]:
        for segment in geometry[key]:
            points = ' '.join(f'{x:.2f},{y:.2f}' for x, y in segment)
            parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.3"/>')
    for x, seq in geometry['events']:
        parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="30" y2="318" stroke="#ffcd70" stroke-dasharray="4 4"/>')
    footer = f"{geometry['unit']} | {geometry['time_unit']} | QRS候选/演示标记，不是疾病判断；滤波与分类未提供时不绘制"
    parts.append(f'<text x="20" y="385" fill="#eeeeee">{escape(footer)}</text></svg>')
    with path.open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(parts))

