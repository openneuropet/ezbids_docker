import json
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from utilities import create_session, upload_files, mark_upload_complete, get_session_status, http_session, _http_sessions


class ClientCookieTest(unittest.TestCase):
    def test_guest_identity_and_relative_paths_survive_all_operations(self):
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, value, new_cookie=False):
                self.send_response(200)
                if new_cookie:
                    self.send_header('Set-Cookie', 'ezbids_guest=g1_fixture; Path=/; HttpOnly; SameSite=Lax')
                self.end_headers()
                self.wfile.write(json.dumps(value).encode())

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length)
                if self.path == '/session':
                    self.reply({'_id': 'fixture-session'}, new_cookie=True)
                    return
                observed.append(('upload', self.headers.get('Cookie')))
                message = BytesParser(policy=policy.default).parsebytes(
                    b'Content-Type: ' + self.headers['Content-Type'].encode() + b'\r\n\r\n' + body)
                observed.append(('paths', [part.get_content().strip() for part in message.iter_parts()
                                           if part.get_param('name', header='content-disposition') == 'paths']))
                self.reply('ok')

            def do_PATCH(self):
                observed.append(('complete', self.headers.get('Cookie')))
                self.reply('ok')

            def do_GET(self):
                observed.append(('status', self.headers.get('Cookie')))
                self.reply({'status': 'uploaded'})

        server = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with tempfile.TemporaryDirectory(prefix='ezbids-client-fixture-', dir='/tmp') as temporary:
                root = Path(temporary)
                file = root / 'subject' / 'image.dcm'
                file.parent.mkdir()
                file.write_text('disposable fixture')
                session = create_session(base + '/')
                upload_files(session['_id'], [str(file)], base, root_dir=root)
                mark_upload_complete(session['_id'], base + '/')
                self.assertEqual(get_session_status(session['_id'], base)['status'], 'uploaded')
                self.assertIn(('paths', ['subject/image.dcm']), observed)
                for operation in ['upload', 'complete', 'status']:
                    self.assertIn((operation, 'ezbids_guest=g1_fixture'), observed)
                with self.assertRaises(ValueError):
                    upload_files(session['_id'], [str(file)], base, root_dir=root / 'other')
        finally:
            _http_sessions.pop(base).close()
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_file_handles_close_when_upload_request_fails(self):
        opened = []
        class BrokenClient:
            def post(self, _url, **kwargs):
                opened.extend(file for _, file in kwargs['files'])
                raise RuntimeError('fixture connection failure')
        with tempfile.TemporaryDirectory(prefix='ezbids-client-fixture-', dir='/tmp') as temporary:
            file = Path(temporary) / 'image.dcm'
            file.write_text('fixture')
            with patch('utilities.http_session', return_value=BrokenClient()):
                with self.assertRaisesRegex(RuntimeError, 'fixture connection failure'):
                    upload_files('fixture', [str(file)], 'http://fixture.invalid')
            self.assertTrue(opened)
            self.assertTrue(all(file.closed for file in opened))


if __name__ == '__main__':
    unittest.main()
