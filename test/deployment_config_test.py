"""Check deployment settings without starting application services or generating keys."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = ('docker-compose.yml', 'docker-compose-dev.yaml', 'docker-compose-nginx.yml')
SETTINGS = ('EZBIDS_ALLOWED_ORIGINS', 'EZBIDS_SECURE_COOKIES', 'EZBIDS_AUTH_MODE',
            'EZBIDS_REGISTRATION_ENABLED', 'VITE_APIHOST', 'VITE_BRAINLIFE_AUTHENTICATION',
            'VITE_EZBIDS_AUTH_MODE', 'EZBIDS_TRUSTED_PROXIES', 'EZBIDS_TRUSTED_PROXY_NAMES')


class DeploymentConfigTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ezbids-deploy-test-', dir='/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.bin = self.directory / 'bin'
        self.bin.mkdir()
        self.capture = self.directory / 'captured'
        self.env = dict(os.environ)
        for key in (*SETTINGS, 'SERVER_NAME', 'BRAINLIFE_AUTHENTICATION', 'BRAINLIFE_USE_NGINX',
                    'BRAINLIFE_DEVELOPMENT', 'COMPOSE_FILE', 'COMPOSE_PROFILES', 'EZBIDS_TMP_DIR'):
            self.env.pop(key, None)
        self.env.update(PATH=str(self.bin) + ':' + os.environ['PATH'], TEST_CAPTURE=str(self.capture))

    def stub(self, name, body):
        script = self.bin / name
        script.write_text('#!/bin/bash\n' + body + '\n')
        script.chmod(0o755)

    def capture_stub(self, name):
        commands = '\n'.join(f'printf \'%s=%s\\n\' {key} "${{{key}:-}}"' for key in SETTINGS)
        self.stub(name, '{\n' + commands + '\n} > "$TEST_CAPTURE"')

    def captured(self):
        return dict(line.split('=', 1) for line in self.capture.read_text().splitlines())

    def run_script(self, script, *args, env=None):
        subprocess.run(['bash', str(ROOT / script), *args], cwd=self.directory,
                       env=env or self.env, check=True, capture_output=True, text=True)

    def compose(self, file, content='', overrides=None):
        if not shutil.which('docker'):
            self.skipTest('Docker Compose is required for configuration rendering')
        env_file = self.directory / 'compose.env'
        env_file.write_text(content)
        result = subprocess.run(['docker', 'compose', '--env-file', str(env_file),
                                 '-f', str(ROOT / file), 'config', '--format', 'json'],
                                env=dict(self.env, **(overrides or {})),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['services']

    def test_direct_compose_defaults(self):
        for file in COMPOSE_FILES:
            with self.subTest(file=file):
                services = self.compose(file, 'SERVER_NAME=deploy.example.org\n')
                api = services['api']['environment']
                if file == 'docker-compose-nginx.yml':
                    self.assertEqual(api['EZBIDS_ALLOWED_ORIGINS'], 'https://deploy.example.org')
                    self.assertEqual(api['EZBIDS_SECURE_COOKIES'], 'true')
                else:
                    self.assertIn('http://deploy.example.org:3000', api['EZBIDS_ALLOWED_ORIGINS'].split(','))
                    self.assertEqual(api['EZBIDS_SECURE_COOKIES'], 'false')
                self.assertEqual(api['EZBIDS_TRUSTED_PROXY_NAMES'], 'nginx' if file == 'docker-compose-nginx.yml' else '')
                self.assertEqual(api['EZBIDS_TRUSTED_PROXIES'], '')
                self.assertIn('handler', services)
                self.assertEqual(Path(services['api']['volumes'][0]['source']),
                                 Path(services['handler']['volumes'][0]['source']))

    def test_explicit_settings_reach_all_compose_deployments(self):
        expected = dict(EZBIDS_ALLOWED_ORIGINS='https://one.example.org,https://two.example.org',
                        EZBIDS_SECURE_COOKIES='false', EZBIDS_AUTH_MODE='local',
                        EZBIDS_REGISTRATION_ENABLED='false',
                        EZBIDS_TRUSTED_PROXIES='192.0.2.10/32', EZBIDS_TRUSTED_PROXY_NAMES='edge')
        content = '\n'.join(f'{key}={value}' for key, value in expected.items()) + '\n'
        for file in COMPOSE_FILES:
            with self.subTest(file=file):
                api = self.compose(file, content)['api']['environment']
                for key, value in expected.items():
                    self.assertEqual(api[key], value)

    def test_new_template_selects_defaults_for_each_compose(self):
        content = (ROOT / 'example.env').read_text()
        for file in COMPOSE_FILES:
            with self.subTest(file=file):
                api = self.compose(file, content)['api']['environment']
                self.assertEqual(api['EZBIDS_SECURE_COOKIES'],
                                 'true' if file == 'docker-compose-nginx.yml' else 'false')
                self.assertEqual(api['EZBIDS_ALLOWED_ORIGINS'].startswith('https://'),
                                 file == 'docker-compose-nginx.yml')

    def test_launcher_handles_old_env_and_preserves_overrides(self):
        self.stub('git', 'exit 0')
        self.capture_stub('docker')
        self.capture_stub('docker-compose')
        for nginx, explicit in ((False, False), (True, False), (True, True)):
            with self.subTest(nginx=nginx, explicit=explicit):
                content = (f'SERVER_NAME=deploy.example.org\nBRAINLIFE_USE_NGINX={str(nginx).lower()}\n'
                           f'BRAINLIFE_DEVELOPMENT=false\nEZBIDS_TMP_DIR={self.directory}/work\n')
                if explicit:
                    content += 'EZBIDS_ALLOWED_ORIGINS=https://custom.example.org\nEZBIDS_SECURE_COOKIES=false\n'
                (self.directory / '.env').write_text(content)
                self.run_script('launch.sh', '--daemon')
                captured = self.captured()
                if explicit:
                    self.assertEqual(captured['EZBIDS_ALLOWED_ORIGINS'], 'https://custom.example.org')
                    self.assertEqual(captured['EZBIDS_SECURE_COOKIES'], 'false')
                else:
                    self.assertEqual(captured['EZBIDS_SECURE_COOKIES'], str(nginx).lower())
                    self.assertIn(('https://deploy.example.org' if nginx else 'http://deploy.example.org:3000'),
                                  captured['EZBIDS_ALLOWED_ORIGINS'].split(','))

    def test_certificate_setup_generates_https_env(self):
        self.stub('openssl', 'touch sslcert.key sslcert.cert')
        (self.directory / 'nginx' / 'ssl').mkdir(parents=True)
        self.run_script('create_self_signed_certs.sh', 'deploy.example.org')
        env = dict(line.split('=', 1) for line in (self.directory / '.env').read_text().splitlines()
                   if line and not line.startswith('#'))
        self.assertEqual(env['EZBIDS_ALLOWED_ORIGINS'], 'https://deploy.example.org')
        self.assertEqual(env['EZBIDS_SECURE_COOKIES'], 'true')
        self.assertEqual(env['EZBIDS_AUTH_MODE'], '')
        self.assertEqual(env['EZBIDS_REGISTRATION_ENABLED'], 'true')

    def test_ui_entrypoint_defaults_and_runtime_overrides(self):
        self.capture_stub('npm')
        cases = [({}, {'VITE_APIHOST': 'http://localhost:8082', 'VITE_BRAINLIFE_AUTHENTICATION': 'false',
                       'VITE_EZBIDS_AUTH_MODE': ''}),
                 ({'SERVER_NAME': 'deploy.example.org', 'BRAINLIFE_AUTHENTICATION': 'true'},
                  {'VITE_APIHOST': 'http://deploy.example.org:8082', 'VITE_BRAINLIFE_AUTHENTICATION': 'true'}),
                 ({'EZBIDS_AUTH_MODE': 'disabled'}, {'VITE_EZBIDS_AUTH_MODE': 'disabled'}),
                 ({'VITE_APIHOST': '/api', 'EZBIDS_AUTH_MODE': 'local', 'VITE_EZBIDS_AUTH_MODE': 'brainlife'},
                  {'VITE_APIHOST': '/api', 'VITE_EZBIDS_AUTH_MODE': 'brainlife'})]
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                self.run_script('ui/entrypoint.sh', env=dict(self.env, **overrides))
                captured = self.captured()
                for key, value in expected.items():
                    self.assertEqual(captured[key], value)

    @unittest.skipUnless(os.environ.get('EZBIDS_TEST_COMBINED_IMAGE'),
                         'Set EZBIDS_TEST_COMBINED_IMAGE to a locally built combined image')
    def test_supervisor_preserves_runtime_environment(self):
        command = ['docker', 'run', '--rm', '--network', 'none']
        settings = dict(BRAINLIFE_AUTHENTICATION='true', EZBIDS_AUTH_MODE='local',
                        EZBIDS_REGISTRATION_ENABLED='false', EZBIDS_SECURE_COOKIES='true',
                        EZBIDS_ALLOWED_ORIGINS='https://deploy.example.org',
                        VITE_APIHOST='https://deploy.example.org/api')
        for key, value in settings.items():
            command.extend(['-e', f'{key}={value}'])
        command.extend(['-v', f'{ROOT / "test/supervisor_env_check.py"}:/tmp/check.py:ro',
                        '-v', f'{ROOT / "EverythingDockerfile"}:/tmp/EverythingDockerfile:ro',
                        '--entrypoint', 'python3', os.environ['EZBIDS_TEST_COMBINED_IMAGE'],
                        '/tmp/check.py'])
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)


if __name__ == '__main__':
    unittest.main()
