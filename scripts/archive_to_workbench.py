#!/usr/bin/env python3
"""Portable archive client, vendored unchanged into the three skills. Stdlib only."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

SUBJECTS = {'physics': '物理', 'mathematics': '数学', 'math': '数学', 'english': '英语', 'chemistry': '化学', 'biology': '生物', 'geography': '地理', 'history': '历史', 'politics': '政治', 'chinese': '语文', 'other': '其他'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def blob(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    if not raw or len(raw) > 30 * 1024 * 1024:
        raise ValueError('文件为空或超过30MB：' + path.name)
    return {'name': path.name, 'data': base64.b64encode(raw).decode(),
            'mime': mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
            'sha256': hashlib.sha256(raw).hexdigest()}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('归档服务不得重定向')


def connection(args):
    config_path = Path(os.environ.get('WENYUAN_ARCHIVE_CONFIG', Path.home() / '.wenyuan-workbench.json'))
    config = read(config_path) if config_path.exists() else {}
    url = (args.url or os.environ.get('WENYUAN_WORKBENCH_URL') or config.get('url') or 'http://127.0.0.1:8765').rstrip('/')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('只允许本机工作台 HTTP 地址，不向远程服务发送学生资料或令牌')
    token_file = args.token_file or os.environ.get('WENYUAN_WORKBENCH_TOKEN_FILE') or config.get('token_file')
    root = args.workbench_root or os.environ.get('WENYUAN_WORKBENCH_ROOT') or config.get('workbench_root')
    if not token_file and root:
        token_file = str(Path(root) / '.local-session-token')
    if not token_file:
        token_file = str(Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'WenyuanWorkbench/data/.local-session-token')
    token = Path(token_file).read_text(encoding='utf-8').strip()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(path, payload=None):
        req = urllib.request.Request(url + path, data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
            headers={'X-Local-Token': token, 'Content-Type': 'application/json'})
        try:
            with opener.open(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            raise ValueError(f'工作台返回 {exc.code}: {body[:500]}') from None
    return call


def prepare(args):
    data = read(args.input) if args.input else {}
    kind = args.type
    if kind == 'feedback':
        report_type = data.get('report_type', 'trial')
        if report_type not in ('trial', 'diagnostic'):
            raise ValueError('未知 report_type')
        kind = 'diagnostic-feedback' if report_type == 'diagnostic' else 'trial-feedback'
    student = data.get('student') or {}
    name = args.student_name or (student.get('name') if isinstance(student, dict) else student)
    subject = args.subject or data.get('subject')
    subject = SUBJECTS.get(subject, subject)
    result = {'schema_version': 1, 'artifact_id': args.artifact_id or str(uuid.uuid4()),
        'type': kind, 'student_id': args.student_id or '', 'student_name': name or '',
        'subject': subject, 'title': args.title or '', 'report_id': args.report_id or '',
        'files': [blob(p) for p in (args.file or [])]}
    if kind == 'exam-analysis':
        result['draft'] = data
    if kind == 'mistake-question':
        q = dict(data.get('question') or {})
        meta, diagnosis = data.get('meta') or {}, data.get('diagnosis') or {}
        analysis = data.get('analysis') or {}
        q.update(answer_md=(data.get('answer') or {}).get('final_md'),
            analysis_md='\n\n'.join(filter(None, [analysis.get('steps_md'),
                '\n'.join(analysis.get('key_points') or []), '\n'.join(analysis.get('pitfalls') or [])])),
            kp=meta.get('knowledge_points') or [], difficulty=meta.get('difficulty', 3), variant_md=meta.get('variant_md', ''))
        figures = []
        work = Path(args.input).resolve().parent.parent
        for f in data.get('figures') or []:
            if not f.get('path'):
                raise ValueError('题图缺少 path')
            figure = dict(f, **blob(work / f['path']))
            figures.append(figure)
        result['question_payload'] = {'question': q, 'error': diagnosis, 'figures': figures,
            'rights': (data.get('source') or {}).get('rights', 'unknown')}
    if not result['student_id'] and not result['student_name']:
        raise ValueError('需要学生姓名或 student_id')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--type', choices=['feedback', 'trial-feedback', 'diagnostic-feedback', 'exam-analysis', 'mistake-question'])
    parser.add_argument('--input', help='report.json / draft.json / text/question.json')
    parser.add_argument('--file', action='append', help='Validated output file; repeat for multiple files')
    for key in ('student-id', 'student-name', 'subject', 'artifact-id', 'title', 'report-id', 'url', 'token-file', 'workbench-root'):
        parser.add_argument('--' + key)
    parser.add_argument('--manifest', type=Path, help='Saved wire payload; reuse this path for retries')
    parser.add_argument('--retry', type=Path, help='Retry existing pending payload without rebuilding')
    parser.add_argument('--students', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.students:
            print(json.dumps(connection(args)('/api/teaching/archive-students'), ensure_ascii=False, indent=2))
            return 0
        if args.retry:
            path, payload = args.retry.resolve(), read(args.retry)
            if args.student_id:
                receipt = path.with_suffix('.receipt.json')
                if receipt.exists() and read(receipt).get('ok') and read(receipt).get('student_id') != args.student_id:
                    raise ValueError('已成功归档的成果不能改挂其他学生')
                payload['student_id'] = args.student_id
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            if not args.type or not args.manifest:
                parser.error('新归档需要 --type 与 --manifest；重试使用 --retry')
            path = args.manifest.resolve()
            if path.exists():
                raise ValueError('归档清单已存在；原样重试使用 --retry，新版本使用新清单路径')
            payload = prepare(args)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        receipt_path = path.with_suffix('.receipt.json')
        try:
            call = connection(args)
            capabilities = call('/api/teaching/archive-capabilities')
            if capabilities.get('schema_version') != 1:
                raise ValueError('工作台需更新统一归档接口并重启')
            receipt = call('/api/teaching/archive', payload)
            if receipt.get('ok') is not True or not receipt.get('student_id'):
                raise ValueError('未收到有效归档回执')
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError) as exc:
            receipt_path.write_text(json.dumps({'ok': False, 'pending': True, 'error': str(exc)}, ensure_ascii=False), encoding='utf-8')
            print(f'文件已保留，归档待完成：{exc}\n重试：--retry "{path}"', file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
