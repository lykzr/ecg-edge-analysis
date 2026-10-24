"""链接图提取边界：缩进引用与LOAD不冒充已提取成员。"""
import sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sim'))
from check_binary_licenses import inspect_map

class MapTests(unittest.TestCase):
 def folder(self):
  base=ROOT/'tmp/license_tests';base.mkdir(parents=True,exist_ok=True);return tempfile.TemporaryDirectory(dir=base)
 def test_dependency_reference_and_load_only_not_selected(self):
  with self.folder() as folder:
   root=Path(folder);a=root/'liba.a';b=root/'libb.a';a.write_bytes(b'a');b.write_bytes(b'b')
   p=root/'link.map';p.write_text('Archive member included to satisfy reference by file (symbol)\n'+str(a)+'(used.o)\n                              '+str(b)+'(dependency.o) (symbol)\nDiscarded input sections\n'+str(a)+'(discarded.o)\nLOAD '+str(a)+'\nLOAD '+str(b)+'\n')
   rows={Path(x['path']).name:x for x in inspect_map(p)}
   self.assertEqual(rows['liba.a']['selected_members'],['used.o']);self.assertEqual(rows['libb.a']['selected_count'],0);self.assertTrue(rows['libb.a']['loaded'])
 def test_missing_archive_fails(self):
  with self.folder() as folder:
   p=Path(folder)/'link.map';p.write_text('LOAD '+str(Path(folder)/'missing.a')+'\n')
   with self.assertRaises(FileNotFoundError):inspect_map(p)
if __name__=='__main__':unittest.main()
