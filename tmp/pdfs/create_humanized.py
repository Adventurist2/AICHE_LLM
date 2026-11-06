from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/PDA_Q2_Humanized.pdf'
paragraphs = [
'''Mulk Raj Anand's "The Cobbler and the Machine" and Karen Hao's "Empire of AI" both show how the centre exploits the periphery for economic gain. However, they show different ways of gaining control. In Anand's story, people accept this control because they are made to desire the centre's products and lifestyle. In Hao's account, the centre uses force and takes resources without people's consent.''',
'''In "The Cobbler and the Machine," the centre gains control by making people want its cultural products. This leads the periphery to accept its own exploitation. The young narrator tells Saudagar that an English sewing machine will improve his status and make him look like a "Sahib." Saudagar then borrows one thousand rupees from Lalla Sain Das to bring the machine from "Vilayat." This shows how cultural imperialism creates a desire that leads to economic exploitation. Saudagar accepts the idea that the centre's culture is superior. He willingly takes on a debt that ruins him, just to own something that represents that culture.''',
'''Hao, on the other hand, shows how the AI industry takes resources and labour from the Global South without consent. She explains that AI companies claim people's data and intellectual property by calling them part of the "free domain." These companies also take large amounts of fresh water from communities facing drought in Uruguay and Chile to cool their data centres. Saudagar chooses to buy the machine, but the people in Hao's account do not have the same choice. The centre takes the resources it needs without their permission. This is a direct form of physical and economic exploitation, where control is forced on the periphery.''',
'''Both texts also show how the centre uses the idea of progress to justify its economic control over the periphery. In Anand's story, the young boy sees the machine as a wonder of "modern times." He believes it is better than the ways of the "old fogies with jungly habits." Similarly, Hao explains that AI companies present their work as a "civilising mission." They promise "progress and modernity to all of humanity" to justify their rapid expansion. These claims spread the centre's values and make its control seem necessary for human progress. In this way, cultural imperialism helps hide the economic exploitation taking place.''',
'''In both texts, people in the periphery lose control over their lives and suffer serious harm. Saudagar is tied to the "chariot wheels of doom" and works himself to death to repay the machine's debt. Similarly, Hao describes a Kenyan content moderator who suffers deep trauma after viewing horrific internet content for an AI company. His family also falls apart. Whether people are drawn in by the desire for a superior culture or used for cheap labour and resources, the result is similar. The centre's machinery uses them up and treats their lives as disposable tools for its own economic benefit.''',
'''To conclude, Anand shows imperialism growing from the periphery's desire to copy the centre. Hao shows imperialism working through force and the taking of resources without consent. In both cases, the centre gains economic control and causes harm to the periphery. Both texts show how the promise of modernisation is used to hide this exploitation and destruction.'''
]

pdfmetrics.registerFont(TTFont('TimesNewRoman', r'C:\Windows\Fonts\times.ttf'))
style = ParagraphStyle('Original', fontName='TimesNewRoman', fontSize=12,
                       leading=15, alignment=TA_JUSTIFY, splitLongWords=False)
width, height = 595.28, 841.89
margin = 56.69292
c = canvas.Canvas(str(OUT), pagesize=(width, height))
c.setTitle('PDA Q2 - Revised Answer')
c.setAuthor('')
y = height - margin
for i, text in enumerate(paragraphs):
    p = Paragraph(escape(text), style)
    _, h = p.wrap(width - 2 * margin, height)
    print(f'Paragraph {i+1}: {len(text.split())} words, {h/15:.0f} lines')
    p.drawOn(c, margin, y-h)
    y -= h+12
assert y + 12 > margin, 'Text exceeds original page'
c.showPage()
c.save()
with pdfplumber.open(OUT) as doc:
    assert len(doc.pages) == 1
    extracted = doc.pages[0].extract_text()
    assert ' '.join(extracted.split()) == ' '.join(' '.join(paragraphs).split())
    print('Verified one page, all rewritten text, font:', set(c['fontname'] for c in doc.pages[0].chars))
    print('Bottom:', max(c['bottom'] for c in doc.pages[0].chars))
print(OUT)
