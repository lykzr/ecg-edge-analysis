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
        base=ROOT/'tmp/skill_tests';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'skill',self.root/'copied skills')
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

if __name__=='__main__':unittest.main()
