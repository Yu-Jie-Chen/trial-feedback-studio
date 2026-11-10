import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from docx import Document
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT/'scripts/build_report.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
class Reports(unittest.TestCase):
    def data(self):
        return dict(student='示例', subject='物理', lesson_date='2020-01-01', report_date='2020-01-02', sections=[dict(heading='一、学情概况', blocks=[dict(type='paragraph',text='本内容为虚构测试。')])])
    def test_types_and_subjects(self):
        with tempfile.TemporaryDirectory() as tmp:
            for subject in ['物理','数学','英语']:
                for kind in b.REPORT_TYPES:
                    d=self.data();d.update(subject=subject,report_type=kind)
                    out=b.build(d,output_dir=tmp);doc=Document(out)
                    title=f'示例同学{subject}{b.REPORT_TYPES[kind][0]}'
                    self.assertEqual(out.name,title+'.docx')
                    self.assertEqual(doc.paragraphs[0].text,title)
                    self.assertEqual(doc.core_properties.title,title)
                    self.assertIn(b.REPORT_TYPES[kind][1],doc.paragraphs[2].text)
                    self.assertEqual(doc.paragraphs[0].runs[0].font.size.pt,18)
                    self.assertTrue(doc.sections[0].header._element.xpath('.//w:drawing'))
                    self.assertTrue(doc.sections[0].footer._element.xpath('.//w:drawing'))
                    with self.assertRaises(FileExistsError):b.build(d,output_dir=tmp)
    def test_cli_override_and_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.data();out=b.build(d,output_dir=tmp)
            self.assertIn('试听课反馈报告',out.name)
            f=Path(tmp)/'data.json';f.write_text(json.dumps(d),encoding='utf-8')
            subprocess.run([sys.executable,str(ROOT/'scripts/build_report.py'),'--input',str(f),'--report-type','diagnostic','--output-dir',tmp],check=True,capture_output=True)
            self.assertTrue((Path(tmp)/'示例同学物理学情诊断反馈报告.docx').exists())
            d['report_type']='invalid'
            with self.assertRaises(ValueError):b.build(d,output_dir=tmp)
    def test_custom_path_and_safe_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.data();d['student']='A/B:C';d['report_type']='diagnostic'
            out=b.build(d,output_dir=tmp);self.assertEqual(out.parent,Path(tmp))
            self.assertNotIn(':',out.name)
            custom=b.build(d,Path(tmp)/'custom.docx')
            self.assertIn('学情诊断反馈报告',Document(custom).paragraphs[0].text)
            with self.assertRaises(ValueError):b.build(d,Path(tmp)/'bad.pdf')
            with self.assertRaises(ValueError):b.build(d,Path(tmp)/'x.docx',output_dir=tmp)
if __name__=='__main__':unittest.main()
