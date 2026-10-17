"""从固定WFDB版本提取MIT许可决策循环，生成可暂停且无尾部补样的流式派生核心。"""
import ast
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import textwrap
import wfdb
from wfdb.processing.qrs import GQRS

ROOT = Path(__file__).resolve().parents[1]


class RemoveDocstrings(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
            node.body = node.body[1:]
        return node


def generate(output_dir=None):
    if wfdb.__version__!='4.3.1':
        raise ValueError('仅支持已审查的WFDB 4.3.1')
    folder = Path(output_dir) if output_dir is not None else ROOT/'src/third_party'
    targets = [folder/name for name in ('gqrs_core.py','wfdb_license.txt','gqrs_provenance.json')]
    if any(path.exists() for path in targets):
        raise FileExistsError('派生核心或许可已存在；停止而不覆盖')
    source = textwrap.dedent(inspect.getsource(GQRS.gqrs))
    tree = ast.parse(source)
    function = tree.body[0]
    function = RemoveDocstrings().visit(function)
    loops = [(i,n) for i,n in enumerate(function.body) if isinstance(n,ast.While)]
    if len(loops)!=2:
        raise ValueError('上游结构与已审查版本不符')
    index,loop = loops[0]
    function.body = function.body[:index+1]
    function.name = 'steps'
    function.args = ast.arguments(posonlyargs=[],args=[ast.arg(arg='self'),ast.arg(arg='from_sample')],
        kwonlyargs=[],kw_defaults=[],defaults=[ast.Constant(value=0)])
    loop.test = ast.Constant(value=True)
    # 有效样本到齐才让调用者恢复；不进入上游的EOF补样/CLEANUP分支。
    loop.body = ast.parse('yield self.t\nself.qf()').body+loop.body[1:]
    candidates = [(i,n) for i,n in enumerate(loop.body) if isinstance(n,ast.If) and 'q1 > self.c.pthr' in ast.unparse(n.test)]
    if len(candidates)!=1:
        raise ValueError('峰值分支锚点不唯一')
    peak_index,peak_if = candidates[0]
    new_peak = ast.Assign(targets=[ast.Name(id='new_peak',ctx=ast.Store())],value=peak_if.test)
    add_if = ast.If(test=ast.Name(id='new_peak',ctx=ast.Load()),body=peak_if.body[:2],orelse=[])
    drain_if = ast.If(test=ast.parse('new_peak or self.t % self.probe_samples == 0',mode='eval').body,
        body=peak_if.body[2:],orelse=peak_if.orelse)
    queue_loops = [n for n in drain_if.body if isinstance(n,ast.While)]
    if len(queue_loops)!=1:
        raise ValueError('峰队列分支锚点不唯一')
    queue_loop = queue_loops[0]
    drain_if.body.insert(0,ast.parse('drain_count = 0').body[0])
    queue_loop.test = ast.BoolOp(op=ast.And(),values=[queue_loop.test,ast.parse('drain_count < self.c._NPEAKS',mode='eval').body])
    queue_loop.body.insert(0,ast.parse('drain_count += 1').body[0])
    loop.body[peak_index:peak_index+1] = [new_peak,add_if,drain_if]
    # 上游仅用于画图的列表不参与决策；每步清空，避免随记录长度增长。
    loop.body.extend(ast.parse('self.SIG_SMOOTH.clear()\nself.SIG_QRS.clear()').body)
    ast.fix_missing_locations(function)
    header = ('# 派生自WFDB 4.3.1 GQRS.gqrs；Copyright (c) 2016 MIT Laboratory for Computational Physiology\n'
              '# MIT许可全文见同目录wfdb_license.txt；原实现及生成差异见gqrs_provenance.json。\n'
              '# 改动：逐步yield；去掉EOF补样；每50ms检查已成熟峰队列；循环有界；清理诊断列表。\n'
              'from wfdb.processing.qrs import GQRS\n\n')
    generated = header+ast.unparse(function)+'\n'
    license_path = Path(inspect.getfile(wfdb)).parent.parent/'wfdb-4.3.1.dist-info/licenses/LICENSE'
    license_text = license_path.read_text(encoding='utf-8')
    folder.mkdir(exist_ok=True)
    targets[0].write_text(generated,encoding='utf-8')
    targets[1].write_text(license_text,encoding='utf-8')
    provenance = dict(package='wfdb',version=wfdb.__version__,
        upstream_url='https://github.com/MIT-LCP/wfdb-python/blob/v4.3.1/wfdb/processing/qrs.py',
        upstream_module_sha256=hashlib.sha256(Path(inspect.getfile(GQRS)).read_bytes()).hexdigest(),
        upstream_method_sha256=hashlib.sha256(source.encode()).hexdigest(),
        generated_sha256=hashlib.sha256(targets[0].read_bytes()).hexdigest(),
        changes=['yield before each sample step','remove EOF padding and cleanup',
                 'probe mature peaks every configured interval, not only on a new peak',
                 'bound peak queue scan to 64 nodes','clear unused diagnostic arrays'])
    targets[2].write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    print('GENERATED',targets[0])


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=None)
    args = parser.parse_args()
    generate(args.output_dir)
