"""Render the report set from the computed result tables."""
from pathlib import Path
import sys
import re
from html import escape

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/".python_packages"))
sys.path.insert(0,str(ROOT))
from src.reporting import write_reports


def make_pdfs(only=None):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib.pagesizes import A4
    pdfmetrics.registerFont(TTFont("Yahei", "C:/Windows/Fonts/msyh.ttc",subfontIndex=0))
    pdfmetrics.registerFont(TTFont("YaheiBold", "C:/Windows/Fonts/msyhbd.ttc",subfontIndex=0))
    pdfmetrics.registerFontFamily("Yahei",normal="Yahei",bold="YaheiBold",italic="Yahei",boldItalic="YaheiBold")
    burgundy=colors.HexColor("#7e0909"); olive=colors.HexColor("#5d5d2a")
    styles={
      "body":ParagraphStyle("body",fontName="Yahei",fontSize=9,leading=15,spaceAfter=7,wordWrap="CJK"),
      "title":ParagraphStyle("title",fontName="YaheiBold",fontSize=20,leading=29,textColor=burgundy,spaceAfter=18,wordWrap="CJK"),
      "h2":ParagraphStyle("h2",fontName="YaheiBold",fontSize=13,leading=20,textColor=burgundy,spaceBefore=12,spaceAfter=8,keepWithNext=True,wordWrap="CJK"),
      "h3":ParagraphStyle("h3",fontName="YaheiBold",fontSize=11,leading=17,textColor=olive,spaceBefore=9,spaceAfter=6,keepWithNext=True,wordWrap="CJK"),
      "cell":ParagraphStyle("cell",fontName="Yahei",fontSize=7,leading=11,wordWrap="CJK"),
    }
    def inline(text):
        text=escape(text)
        text=re.sub(r"\[([^\]]+)\]\(([^)]+)\)",lambda m: ('<link href="'+m[2]+'" color="#7e0909">'+m[1]+'</link>') if m[2].startswith('http') else m[1],text)
        text=re.sub(r"\*\*(.+?)\*\*",r"<b>\1</b>",text)
        text=re.sub(r"`([^`]+)`",r'<font color="#5d5d2a">\1</font>',text)
        return text
    def foot(canvas,doc):
        canvas.setStrokeColor(colors.HexColor("#C7C3AC"));canvas.line(40,37,A4[0]-40,37)
        canvas.setFont("Yahei",7);canvas.setFillColor(olive)
        canvas.drawString(40,25,"任务一 · 目标皮肤层递送潜力评估")
        canvas.drawRightString(A4[0]-40,25,str(doc.page))
    for md in sorted((ROOT/"output").glob("*报告.md")):
        if only and only not in md.stem:continue
        story=[]; lines=md.read_text(encoding="utf-8").splitlines();i=0
        while i<len(lines):
            line=lines[i].strip();i+=1
            if not line or line=='---': continue
            if line.startswith('|'):
                block=[line]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    block.append(lines[i].strip());i+=1
                data=[]
                for row in block:
                    cells=[x.strip() for x in row.strip('|').split('|')]
                    if all(re.fullmatch(r'[:\- ]+',x) for x in cells):continue
                    data.append([Paragraph(inline(x.replace('_',' ')),styles['cell']) for x in cells])
                n=len(data[0]); widths=[(A4[0]-80)/n]*n
                t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
                t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#efe4dd')),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.8,burgundy),
                    ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#ddd8cb')),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#fffaf5')]),
                    ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                    ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
                story.extend([t,Spacer(1,9)]);continue
            match=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',line)
            if match:
                p=(md.parent/match[2]).resolve()
                if not p.exists():raise FileNotFoundError(p)
                im=Image(str(p));ratio=min((A4[0]-80)/im.imageWidth,580/im.imageHeight)
                im.drawWidth=im.imageWidth*ratio;im.drawHeight=im.imageHeight*ratio
                story.extend([im,Spacer(1,9)]);continue
            if line.startswith('# '):kind='title';line=line[2:]
            elif line.startswith('## '):kind='h2';line=line[3:]
            elif line.startswith('### '):kind='h3';line=line[4:]
            else:kind='body'
            story.append(Paragraph(inline(line),styles[kind]))
        doc=SimpleDocTemplate(str(md.with_suffix('.pdf')),pagesize=A4,leftMargin=40,rightMargin=40,
                              topMargin=42,bottomMargin=49,title=lines[0].lstrip('# '),author="iGEM JLU-NBBMS")
        doc.build(story,onFirstPage=foot,onLaterPages=foot)
        print(md.with_suffix('.pdf').name,flush=True)


if __name__=='__main__':
    only='完整' if '--full-only' in sys.argv else ('简要' if '--brief-only' in sys.argv else ('图解' if '--graph-only' in sys.argv else None))
    write_reports(ROOT,only=only)
    if '--pdf' in sys.argv:make_pdfs(only=only)
