"""流式比较同一时轴CSV，报告首个差异；容差必须在比较前确定。"""
import argparse
import csv
import itertools
import json
import math
import re
from pathlib import Path
import sys


def numeric(value):
    if re.fullmatch(r'[+-]?\d+',value):return int(value)
    try:number=float(value)
    except ValueError:return None
    if not math.isfinite(number):raise ValueError('NaN/Infinity不作为有效比较值')
    return number


def compare(reference,candidate,keys=(),atol=0.0,rtol=0.0):
    if not all(math.isfinite(x) and x>=0 for x in (atol,rtol)):
        raise ValueError('容差必须是非负有限数')
    with Path(reference).open(encoding='utf-8-sig',newline='') as a, Path(candidate).open(encoding='utf-8-sig',newline='') as b:
        left=csv.DictReader(a);right=csv.DictReader(b)
        fields=left.fieldnames
        if not fields or fields!=right.fieldnames or len(set(fields))!=len(fields) or any(not f for f in fields):
            raise ValueError('表头缺失、重复或顺序不同')
        if not set(keys)<=set(fields):raise ValueError('键列不存在')
        count=0
        for index,(expected,actual) in enumerate(itertools.zip_longest(left,right),1):
            if expected is None or actual is None:
                return dict(passed=False,row=index,error='行数不同')
            if None in expected or None in actual or any(v is None or not v.strip() for v in itertools.chain(expected.values(),actual.values())):
                raise ValueError('缺失或多余CSV字段，行='+str(index))
            for field in fields:
                x,y=expected[field],actual[field]
                nx,ny=numeric(x),numeric(y)
                if field in keys or nx is None or ny is None:equal=x==y
                elif atol==0 and rtol==0:equal=nx==ny
                else:equal=abs(nx-ny)<=atol+rtol*abs(nx)
                if not equal:
                    return dict(passed=False,row=index,field=field,expected=x,actual=y,error='字段不同')
            count+=1
        if count==0:raise ValueError('没有数据行，不能报告通过')
    return dict(passed=True,rows=count,columns=len(fields),keys=list(keys),atol=atol,rtol=rtol,scope='same-axis numeric/text comparison; not algorithm accuracy')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',required=True);p.add_argument('--candidate',required=True)
    p.add_argument('--key',action='append',default=[])
    p.add_argument('--atol',type=float,default=0.0);p.add_argument('--rtol',type=float,default=0.0)
    args=p.parse_args()
    try:result=compare(args.reference,args.candidate,args.key,args.atol,args.rtol)
    except (OSError,ValueError,TypeError,OverflowError,csv.Error) as error:result=dict(passed=False,error=str(error))
    print(json.dumps(result,ensure_ascii=True));sys.exit(0 if result['passed'] else 1)
