"""Exercise the generation-to-archive hook against an isolated HTTP receiver."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from argparse import Namespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

class HookTests(unittest.TestCase):
    def test_hook(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"schema_version":1}')
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"ok":true,"student_id":"example","material_ids":["file"]}')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                work = Path(folder)
                token = work / 'token'; token.write_text('test-only')
                with patch.dict(os.environ, {'WENYUAN_WORKBENCH_URL': f'http://127.0.0.1:{server.server_port}', 'WENYUAN_WORKBENCH_TOKEN_FILE': str(token)}):
                    source = work / 'report.json'
                    source.write_text(json.dumps({'student':'示例学生','subject':'英语','lesson_date':'2020-01-01','report_date':'2020-01-02','sections':[{'heading':'一、测试','blocks':[{'type':'paragraph','text':'虚构测试内容'}]}]},ensure_ascii=False),encoding='utf-8')
                    manifest = work / 'result.archive.json'
                    proc = subprocess.run([sys.executable,str(ROOT/'scripts/build_report.py'),'--input',str(source),'--output-dir',str(work),'--report-type','diagnostic','--archive-manifest',str(manifest)],capture_output=True)
                    self.assertEqual(proc.returncode,0,proc.stderr)
                    self.assertEqual(received[0]['type'],'diagnostic-feedback')
                    self.assertTrue((work/'示例学生同学英语学情诊断反馈报告.docx').exists())
                    self.assertTrue(json.loads(manifest.with_suffix('.receipt.json').read_text('utf-8'))['ok'])
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
