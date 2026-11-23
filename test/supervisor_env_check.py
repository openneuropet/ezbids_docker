"""Run only inside the disposable container created by deployment_config_test."""
import configparser
import json
import os
from pathlib import Path
import subprocess
import time

def main():
    text = Path('/tmp/EverythingDockerfile').read_text()
    block = text.split('COPY <<EOF /etc/supervisor/conf.d/ezbids.conf\n', 1)[1].split('\nEOF', 1)[0]
    source = configparser.ConfigParser(interpolation=None)
    source.read_string(block)
    config = configparser.ConfigParser(interpolation=None)
    config['supervisord'] = {'nodaemon': 'true', 'logfile': '/tmp/env-supervisor.log', 'pidfile': '/tmp/env-supervisor.pid'}
    keys = ['BRAINLIFE_AUTHENTICATION', 'EZBIDS_AUTH_MODE', 'EZBIDS_REGISTRATION_ENABLED',
            'EZBIDS_ALLOWED_ORIGINS', 'EZBIDS_SECURE_COOKIES', 'VITE_APIHOST']
    expected = {key: os.environ[key] for key in keys}
    Path('/tmp/capture-env.py').write_text('import os,json,sys; from pathlib import Path; Path("/tmp/"+sys.argv[1]+".json").write_text(json.dumps(dict(os.environ)))')
    for name in ['api', 'ui']:
        section = dict(source['program:' + name])
        section.update(command='/usr/bin/python3 /tmp/capture-env.py ' + name, directory='/tmp',
                       startsecs='0', autorestart='false', stdout_logfile='/tmp/' + name + '.out',
                       stderr_logfile='/tmp/' + name + '.err')
        config['program:' + name] = section
    with open('/tmp/env-supervisor.conf', 'w') as stream:
        config.write(stream)
    process = subprocess.Popen(['/usr/bin/supervisord', '-n', '-c', '/tmp/env-supervisor.conf'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if all(Path('/tmp/' + name + '.json').exists() for name in ['api', 'ui']):
                break
            if process.poll() is not None:
                raise RuntimeError('Supervisor exited before starting test processes')
            time.sleep(0.1)
        for name in ['api', 'ui']:
            actual = json.loads(Path('/tmp/' + name + '.json').read_text())
            for key, value in expected.items():
                assert actual.get(key) == value, (name, key, actual.get(key), value)
        print('PASS: Actual Supervisor API/UI subprocesses inherit runtime auth, origin, cookie, and API URL overrides.')
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    main()
