import ast
from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn

root = Path(__file__).resolve().parents[2]
tree = ast.parse((root / 'tmp/pdfs/create_humanized.py').read_text())
paragraphs = next(ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'paragraphs' for t in n.targets))
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Pt(595.28), Pt(841.89)
sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Pt(56.69292)
style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)
style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
pf = style.paragraph_format
pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
pf.line_spacing = Pt(15)
pf.space_before = Pt(0)
pf.space_after = Pt(12)
for text in paragraphs:
    doc.add_paragraph(text)
doc.core_properties.title = 'PDA Q2 - Revised Answer'
doc.core_properties.author = ''
out = root / 'output/docx/PDA_Q2_Humanized.docx'
out.parent.mkdir(parents=True, exist_ok=True)
doc.save(out)
assert [p.text for p in Document(out).paragraphs] == paragraphs
print(out)
