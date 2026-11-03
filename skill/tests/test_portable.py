"""只复制skill目录到独立位置，用CLI验证跨工程脚本；不连接板卡。"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PortableSkills(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='portable_skills_');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT,self.root/'copied skills')
        self.data=self.root/'other project';self.data.mkdir()

    def run_script(self,name,script,*args):
        result=subprocess.run([sys.executable,'-B',str(self.root/'copied skills'/name/'scripts'/script),*map(str,args)],cwd=self.data,capture_output=True,timeout=15)
        row=json.loads(result.stdout.decode('utf-8'));self.assertEqual(result.returncode,0 if row['passed'] else 1)
        return row

    def artifact(self,name='firmware.bin',value=b'\x00\xff\r\n'):
        p=self.data/'manifest.json';p.write_text(json.dumps(dict(files={name:dict(bytes=len(value),sha256=hashlib.sha256(value).hexdigest())})),encoding='utf-8');return p

    def check_files(self,p):return self.run_script('artifact-check','check_files.py','--root',self.data,'--manifest',p)

    def trace(self,actual,expected='cycle,value\n0,10\n1,-2\n',*extra):
        a=self.data/'golden.csv';b=self.data/'actual.csv';a.write_text(expected,encoding='utf-8');b.write_text(actual,encoding='utf-8')
        return self.run_script('trace-check','compare_csv.py','--reference',a,'--candidate',b,'--key','cycle',*extra)

    def test_intact_binary_from_other_directory(self):
        (self.data/'firmware.bin').write_bytes(b'\x00\xff\r\n');self.assertTrue(self.check_files(self.artifact())['passed'])

    def test_same_size_tampering(self):
        (self.data/'firmware.bin').write_bytes(b'\x00\xfe\r\n');self.assertFalse(self.check_files(self.artifact())['passed'])

    def test_missing_file(self):self.assertFalse(self.check_files(self.artifact())['passed'])

    def test_escape_absolute_and_drive_paths(self):
        for name in ('../outside.bin','/outside.bin','C:/outside.bin','a\\b.bin'):
            with self.subTest(name=name):self.assertFalse(self.check_files(self.artifact(name))['passed'])

    def test_newline_change_rejected(self):
        (self.data/'firmware.bin').write_bytes(b'\x00\xff\n');self.assertFalse(self.check_files(self.artifact())['passed'])

    def test_identical_integer_trace(self):self.assertTrue(self.trace('cycle,value\n0,10\n1,-2\n')['passed'])

    def test_first_mismatch_field(self):
        result=self.trace('cycle,value\n0,10\n1,-3\n');self.assertFalse(result['passed']);self.assertEqual((result['row'],result['field']),(2,'value'))

    def test_source_key_never_uses_float_tolerance(self):
        self.assertFalse(self.trace('cycle,value\n0,10\n2,-2\n','cycle,value\n0,10\n1,-2\n','--atol','100')['passed'])

    def test_declared_float_tolerance(self):
        self.assertTrue(self.trace('cycle,value\n0,1.00001\n','cycle,value\n0,1.0\n','--atol','0.0001')['passed'])
        self.assertFalse(self.trace('cycle,value\n0,1.00001\n','cycle,value\n0,1.0\n')['passed'])

    def test_row_header_and_missing_field(self):
        for value in ('cycle,value\n0,10\n','cycle,other\n0,10\n1,-2\n','cycle,value\n0,10\n1,\n','cycle,value\n'):
            with self.subTest(value=value):self.assertFalse(self.trace(value)['passed'])

    def test_nonfinite_and_negative_tolerance(self):
        for value in ('NaN','inf','-inf'):self.assertFalse(self.trace('cycle,value\n0,'+value+'\n','cycle,value\n0,'+value+'\n')['passed'])
        self.assertFalse(self.trace('cycle,value\n0,1\n','cycle,value\n0,1\n','--atol','-1')['passed'])

    def test_large_integer_does_not_round_to_equal(self):
        self.assertFalse(self.trace('cycle,value\n0,9007199254740993\n','cycle,value\n0,9007199254740992\n')['passed'])

    def reports(self, *, counts=None, values=None, state='Routed', design='demo', omit=None):
        identity='| Tool Version : Vivado v.2026.1\n| Design : demo\n| Device : xc7z020clg400-2\n| Design State : '+state+'\n'
        util=identity+'\n'.join('| '+name+' | '+used+' | 0 | 0 | '+available+' | '+percent+' |' for name,used,available,percent in (
            ('Slice LUTs','100','1000','10.00'),('Slice Registers','200','2000','10.00'),
            ('Block RAM Tile','12.5','140','8.93'),('DSPs','20','220','9.09')))
        checks=('no_clock','constant_clock','pulse_width_clock','unconstrained_internal_endpoints','no_input_delay','no_output_delay',
                'multiple_clock','generated_clocks','loops','partial_input_delay','partial_output_delay','latch_loops')
        timing=identity.replace('Design : demo','Design : '+design)
        timing+='\n'.join('checking '+name+' ('+str((counts or {}).get(name,0))+')' for name in checks if name!=omit)
        timing+='\n| Design Timing Summary\n WNS(ns) TNS WHS(ns) WPWS(ns)\n '+' '.join(['--------']*12)+'\n '
        timing+=' '.join(map(str,values or [.1,0,0,100,.03,0,0,100,3.8,0,0,50]))
        timing+='\n| Clock Summary\n clk {0.000 5.000} 10.000 100.000\n| Intra Clock Table\n'
        a=self.data/'util.rpt';b=self.data/'time.rpt';a.write_text(util,encoding='utf-8');b.write_text(timing,encoding='utf-8')
        return a,b

    def report_check(self, paths, *extra):
        return self.run_script('vivado-report-check','check_reports.py','--utilization',paths[0],'--timing',paths[1],*extra)

    def test_routed_reports_and_clock(self):
        row=self.report_check(self.reports(),'--device','xc7z020clg400-2','--clock','clk','--period-ns','10')
        self.assertTrue(row['passed']);self.assertEqual(row['resources']['bram36']['used'],12.5)
        self.assertTrue(row['constraints_clean']);self.assertEqual(set(row['inputs']),{'utilization','timing'})

    def test_all_negative_slacks_and_failing_endpoints(self):
        for index,value in ((0,-.1),(1,-.2),(2,1),(4,-.1),(5,-.2),(6,1),(8,-.1),(9,-.2),(10,1)):
            with self.subTest(index=index):
                values=[.1,0,0,100,.03,0,0,100,3.8,0,0,50];values[index]=value
                self.assertFalse(self.report_check(self.reports(values=values))['passed'])

    def test_unconstrained_paths_require_exact_explicit_review(self):
        paths=self.reports(counts={'no_output_delay':1})
        self.assertFalse(self.report_check(paths)['passed'])
        self.assertFalse(self.report_check(paths,'--reviewed-check','no_output_delay=1')['passed'])
        self.assertFalse(self.report_check(paths,'--reviewed-check','no_output_delay=2','--review-note','checked')['passed'])
        self.assertFalse(self.report_check(paths,'--reviewed-check','unknown=1','--review-note','checked')['passed'])
        row=self.report_check(paths,'--reviewed-check','no_output_delay=1','--review-note','checked fixture only')
        self.assertTrue(row['passed']);self.assertFalse(row['constraints_clean'])

    def test_missing_constraint_and_invalid_summary(self):
        self.assertFalse(self.report_check(self.reports(omit='no_clock'))['passed'])
        for value in ('NaN','inf','broken'):
            values=[value,0,0,100,.03,0,0,100,3.8,0,0,50]
            self.assertFalse(self.report_check(self.reports(values=values))['passed'])

    def test_report_identity_clock_and_device_mismatch(self):
        self.assertFalse(self.report_check(self.reports(state='Synthesized'))['passed'])
        self.assertFalse(self.report_check(self.reports(design='other'))['passed'])
        for extra in (('--device','other'),('--clock','absent','--period-ns','10'),('--clock','clk','--period-ns','5'),('--clock','clk')):
            self.assertFalse(self.report_check(self.reports(),*extra)['passed'])

    def test_resource_budget_and_unknown_resource(self):
        p=self.data/'budget.json'
        for limits,passed in (({'lut':10},True),({'lut':9.9},False),({'unknown':90},False),({'lut':float('nan')},False)):
            p.write_text(json.dumps({'max_percent':limits}),encoding='utf-8')
            self.assertEqual(self.report_check(self.reports(),'--budget',p)['passed'],passed)

    def test_truncated_resource_table(self):
        paths=self.reports();paths[0].write_text('| Tool Version : broken\n',encoding='utf-8')
        self.assertFalse(self.report_check(paths)['passed'])

    def test_report_device_alias_and_different_device(self):
        paths=self.reports();text=paths[1].read_text(encoding='utf-8')
        paths[1].write_text(text.replace('xc7z020clg400-2','7z020-clg400'),encoding='utf-8')
        self.assertTrue(self.report_check(paths)['passed'])
        paths[1].write_text(text.replace('xc7z020clg400-2','xc7z010clg400-2'),encoding='utf-8')
        self.assertFalse(self.report_check(paths)['passed'])

    def paired(self, rows='a,100,10,1\nb,100,100,1\n', **changes):
        pairs=self.data/'pairs.csv';meta=self.data/'metadata.json'
        pairs.write_text('sample_id,reference_ticks,accelerator_ticks,output_match\n'+rows,encoding='utf-8')
        contract=dict(input_sha256='a'*64,model_sha256='b'*64,precision='fp32',reference_label='cpu',accelerator_label='fpga',
                      reference_timer_hz=1000,accelerator_timer_hz=1000,scope='compute')
        contract.update(changes);meta.write_text(json.dumps(contract),encoding='utf-8')
        return self.run_script('acceleration-review','summarize_pairs.py','--pairs',pairs,'--metadata',meta)

    def test_cumulative_ratio_not_average_of_ratios(self):
        row=self.paired();self.assertTrue(row['passed']);self.assertAlmostEqual(row['speedup'],200/110)
        self.assertEqual(row['reference_total_ticks'],200);self.assertEqual(row['tasks'],2)

    def test_different_timer_frequencies(self):
        row=self.paired('a,1000,500,1\n',reference_timer_hz=1000,accelerator_timer_hz=10000)
        self.assertTrue(row['passed']);self.assertEqual(row['speedup'],20)

    def test_mismatch_cannot_produce_valid_speedup(self):
        row=self.paired('a,100,10,0\n');self.assertFalse(row['passed']);self.assertIsNone(row['speedup'])
        self.assertEqual(row['mismatches'],1);self.assertGreater(row['reference_total_ms'],0)

    def test_invalid_ticks_and_pairing(self):
        for rows in ('','a,0,10,1\n','a,-1,10,1\n','a,NaN,10,1\n','a,1.5,10,1\n','a,01,10,1\n',
                     'a,100,10,1\na,100,10,1\n','a,100,10,2\n','a,100,10\n','a,100,10,1,extra\n'):
            with self.subTest(rows=rows):self.assertFalse(self.paired(rows)['passed'])

    def test_missing_identity_or_invalid_frequency(self):
        for changes in ({'input_sha256':''},{'model_sha256':'bad'},{'precision':''},{'scope':''},
                        {'reference_timer_hz':0},{'accelerator_timer_hz':float('nan')},{'reference_timer_hz':True}):
            self.assertFalse(self.paired(**changes)['passed'])

if __name__=='__main__':unittest.main()
