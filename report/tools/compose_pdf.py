from pathlib import Path
import ast,io,json
import pdfplumber
from pypdf import PdfReader,PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import argparse
parser=argparse.ArgumentParser(description='为Word导出的占位PDF叠加原始实物照片和矢量标注。')
parser.add_argument('--base',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
P=Path(__file__).resolve().parents[1]
F=P/'attachments/figures'
labels=json.loads(Path(__file__).with_name('photo_labels.json').read_text(encoding='utf-8'))
args.output.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('Chinese','C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
captions=['（a）心电采集端与USB无线接收器','（b）Zynq开发板与JTAG下载器'];names=['capture_hardware_original_20261103.jpg','zynq_hardware_original_20261103.jpg']
r=PdfReader(args.base);writer=PdfWriter();receipt=[]
with pdfplumber.open(args.base) as pdf:
 for pi,page in enumerate(pdf.pages):
  matches=[(k,page.search(s,regex=False,return_chars=False)) for k,s in enumerate(captions)]
  matches=[(k,v[0]) for k,v in matches if v]
  if matches:
   b=io.BytesIO();c=canvas.Canvas(b,pagesize=(page.width,page.height))
   for k,match in matches:
    w,h=360,270;x=(page.width-w)/2;top=match['bottom']+5;y=page.height-top-h
    assert y>77,(pi,y)
    occupied=[ch for ch in page.chars if ch['text'].strip() and ch['top']>top and ch['bottom']<top+h]
    assert not occupied,(pi,occupied)
    c.saveState();c.translate(x,y+h);c.rotate(-90);c.drawImage(str(F/names[k]),0,0,width=h,height=w);c.restoreState()
    for title,rx,ry,ax,ay in labels[k]:
     fs=8.4;bw=pdfmetrics.stringWidth(title,'Chinese',fs)+8;bh=14
     lx=min(x+rx*w,x+w-bw-2);ly=y+h-ry*h-bh;tx=x+(1-ay)*w;ty=y+h-ax*h
     sx=max(lx+3,min(tx,lx+bw-3));sy=max(ly+2,min(ty,ly+bh-2))
     c.setStrokeColorRGB(.95,.60,.08);c.setLineWidth(.85);c.line(sx,sy,tx,ty);c.setFillColorRGB(.95,.60,.08);c.circle(tx,ty,1.8,stroke=0,fill=1)
     c.setFillColorRGB(1,1,.96);c.setStrokeColorRGB(.12,.32,.32);c.roundRect(lx,ly,bw,bh,2,stroke=1,fill=1);c.setFillColorRGB(.04,.20,.20);c.setFont('Chinese',fs);c.drawString(lx+4,ly+3.4,title)
    receipt.append({'photo':k+1,'page':pi+1,'rect':[x,top,w,h],'labels':[v[0] for v in labels[k]]})
   c.save();r.pages[pi].merge_page(PdfReader(b).pages[0])
  writer.add_page(r.pages[pi])
assert len(receipt)==2
writer.add_metadata({'/Title':'基于FPGA的心电边缘分析系统 技术文档'})
with (args.output).open('wb') as f:writer.write(f)
(args.output.with_suffix('.annotations.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(receipt)
