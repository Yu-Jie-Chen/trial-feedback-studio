"""Render reviewed report JSON using the retained reference's actual formatting."""
import argparse
import json
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]

def required_string(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{key} must be a nonempty string')
    return value.strip()

def date_text(value):
    d = date.fromisoformat(value)
    return f'{d.year}年{d.month}月{d.day}日'

def validate(data):
    for key in ('student', 'subject', 'lesson_date', 'report_date'):
        required_string(data, key)
    if data['subject'] not in ('物理', '数学', '英语'):
        raise ValueError('subject must be 物理, 数学 or 英语')
    date_text(data['lesson_date']); date_text(data['report_date'])
    if 'teacher' in data and not isinstance(data['teacher'], str):
        raise ValueError('teacher must be a string')
    sections = data.get('sections')
    if not isinstance(sections, list) or not sections:
        raise ValueError('sections must be a nonempty list')
    for section in sections:
        required_string(section, 'heading')
        blocks = section.get('blocks')
        if not isinstance(blocks, list) or not blocks:
            raise ValueError('each section needs blocks')
        for block in blocks:
            if block.get('type') not in ('paragraph', 'subheading'):
                raise ValueError('block type must be paragraph or subheading')
            required_string(block, 'text')
        if blocks[-1]['type'] == 'subheading':
            raise ValueError('a subheading must have following content')

def build(data, output, template=None):
    validate(data)
    doc = Document(template or ROOT / 'assets/reference.docx')
    samples = {}
    for p in doc.paragraphs:
        if p.text.strip() and p.style.name not in samples:
            samples[p.style.name] = deepcopy(p._p)
    needed = ('Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Normal')
    if any(n not in samples for n in needed):
        raise ValueError('Reference is missing required paragraph samples')
    for e in list(doc.element.body):
        if e.tag != qn('w:sectPr'):
            doc.element.body.remove(e)
    def add(text, style):
        p = doc.add_paragraph(style=style)
        sample = samples[style]
        if p._p.pPr is not None:
            p._p.remove(p._p.pPr)
        if sample.pPr is not None:
            props = deepcopy(sample.pPr)
            for tag in ('sectPr', 'pageBreakBefore', 'shd', 'pBdr'):
                for e in list(props.iter(qn('w:' + tag))):
                    e.getparent().remove(e)
            p._p.insert(0, props)
        p.style = doc.styles[style]
        run = p.add_run(text)
        sr = next((r for r in sample.findall(qn('w:r')) if r.find(qn('w:rPr')) is not None), None)
        if sr is not None:
            run._r.insert(0, deepcopy(sr.find(qn('w:rPr'))))
        if style in ('Title', 'Subtitle'):
            p.alignment = 1
        if style in ('Title', 'Heading 1', 'Heading 2'):
            p.paragraph_format.keep_with_next = True
        p.paragraph_format.widow_control = True
        return p
    add(f"{data['student']}同学{data['subject']}试听课学情分析报告", 'Title')
    teacher = data.get('teacher', '').strip()
    add('文源教育' + (f' ｜ 授课教师：{teacher}' if teacher else ''), 'Subtitle')
    add(f"试听日期：{date_text(data['lesson_date'])} ｜ 报告日期：{date_text(data['report_date'])}", 'Subtitle')
    for section in data['sections']:
        add(section['heading'], 'Heading 1')
        for block in section['blocks']:
            add(block['text'], 'Heading 2' if block['type'] == 'subheading' else 'Normal')
    for root in (doc.element, doc.styles.element):
        for tag in ('pBdr',):
            for e in list(root.iter(qn('w:' + tag))):
                e.getparent().remove(e)
    # Replace old author metadata. The retained source stays unchanged.
    doc.core_properties.title = f"{data['student']}同学{data['subject']}试听课学情分析报告"
    doc.core_properties.subject = '试听课学情分析'
    doc.core_properties.author = teacher or '文源教育'
    doc.core_properties.last_modified_by = '文源教育'
    doc.core_properties.comments = ''
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Output exists; choose a new name: {output}')
    doc.save(output)
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--template', type=Path)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    print(build(data, args.output, args.template))
