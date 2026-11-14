"""Render an actual CLI run into a portable terminal demo GIF (Pillow optional).

This is a recording of program output, not a screenshot of a GUI terminal.
"""
from pathlib import Path
import json
import subprocess
import sys
import textwrap
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
command = [sys.executable, '-m', 'budgetladder', 'examples/field-notes.json',
           '--budgets', '32,64,96', '--size', '32', '--overlap', '16',
           '--output', 'assets/demo-manifest.json']
output = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout
(root/'assets/demo.txt').write_text(output)
font = ImageFont.load_default(size=17)
for path in ['/System/Library/Fonts/Menlo.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']:
    if Path(path).exists():
        font = ImageFont.truetype(path, 16)
        break
lines = ['$ python -m budgetladder examples/field-notes.json', '  --budgets 32,64,96 --size 32 --overlap 16', '']
for line in output.splitlines():
    lines.extend(textwrap.wrap(line, width=114, subsequent_indent='  ', replace_whitespace=False) or [''])
w, h = 1240, 100 + 23*len(lines)
frames = []
ends = [min(len(lines),9), next(i for i,l in enumerate(lines) if l.startswith('Budget   64')), next(i for i,l in enumerate(lines) if l.startswith('Budget   96')), len(lines)]
for end in ends:
    im = Image.new('RGB', (w,h), '#0b1220')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((18,16,w-18,58), radius=10, fill='#172235')
    d.text((36,27),'BudgetLadder / actual CLI output / source-word budgets',font=font,fill='#dce7f7')
    for i,line in enumerate(lines[:end]):
        color = '#6ee7b7' if line.startswith(('Budget','Audit:','$')) else '#cbd5e1'
        d.text((32,80+23*i),line,font=font,fill=color)
    frames.append(im)
frames[-1].save(root/'assets/demo.png')
frames[0].save(root/'assets/demo.gif',save_all=True,append_images=frames[1:],duration=[1200,1600,1800,4500],loop=0,optimize=True)
print('Rendered verified command output:',w,h)
