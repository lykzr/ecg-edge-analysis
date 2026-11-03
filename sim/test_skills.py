"""复用可独立复制技能包中的测试；不操作板卡或网页。"""
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'skill/tests/test_portable.py'
spec=importlib.util.spec_from_file_location('portable_skill_tests',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PortableSkills=module.PortableSkills

if __name__=='__main__':unittest.main()
