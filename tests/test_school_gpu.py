"""Exercise the shell lifecycle with stub executables; never load model weights."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.school_gpu_device import assigned_device

ROOT = Path(__file__).resolve().parents[1]


class Phase1DeviceTest(unittest.TestCase):
    def test_single_mig_assignment_and_existing_cuda(self):
        device = 'MIG-8db09adc-7efd-5b05-9968-a7dcfadeadae'
        env = {'JH_JOBID': '30559', 'JH_GPU_RANK': f'1;g-node01:{device};'}
        self.assertEqual(assigned_device(env, 'g-node01'), device)
        self.assertEqual(assigned_device({**env, 'CUDA_VISIBLE_DEVICES': device}, 'g-node01.local'), device)
        self.assertEqual(assigned_device({'JH_JOBID': '1', 'CUDA_VISIBLE_DEVICES': '0'}, 'host'), '0')

    def test_reject_unassigned_wrong_host_multiple_or_conflicting_device(self):
        for env in ({}, {'JH_JOBID': '1'}, {'JH_JOBID': '1', 'CUDA_VISIBLE_DEVICES': '-1'},
                    {'JH_JOBID': '1', 'CUDA_VISIBLE_DEVICES': '0,1'},
                    {'JH_JOBID': '1', 'JH_GPU_RANK': '1;other:0;'},
                    {'JH_JOBID': '1', 'JH_GPU_RANK': '2;host:0,1;'},
                    {'JH_JOBID': '1', 'JH_GPU_RANK': '1;host:MIG-invalid;'},
                    {'JH_JOBID': '1', 'JH_GPU_RANK': '1;host:0;', 'CUDA_VISIBLE_DEVICES': '1'}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                assigned_device(env, 'host')


@unittest.skipUnless(sys.platform.startswith('linux'), 'School submission requires Bash')
class Phase1SubmissionTest(unittest.TestCase):
    def test_bounded_priority_chain_and_no_resubmission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('scripts', 'logs', 'bin'):
                (root / folder).mkdir()
            shutil.copyfile(ROOT / 'scripts/submit_priority_phase1.sh', root / 'scripts/submit_priority_phase1.sh')
            (root / 'bin/git').write_text('#!/bin/sh\nexit 0\n')
            (root / 'bin/jsub').write_text(f'#!{sys.executable}\n' + '''
import json, sys
from pathlib import Path
path = Path('calls.json')
calls = json.loads(path.read_text()) if path.exists() else []
calls.append(sys.argv[1:])
path.write_text(json.dumps(calls))
print(f'Job <{40000 + len(calls)}> is submitted to queue <test>')
''')
            for path in (root / 'bin').iterdir():
                path.chmod(0o755)
            env = {**os.environ, 'PATH': str(root / 'bin') + ':' + os.environ['PATH'],
                   'P3_CAMPAIGN': 'priority-test', 'P3_BUILD_JOB': '39999'}
            command = ['bash', str(root / 'scripts/submit_priority_phase1.sh')]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = json.loads((root / 'calls.json').read_text())
            self.assertEqual(len(calls), 22)
            for index, args in enumerate(calls):
                self.assertEqual(args[args.index('-w') + 1], f'done({39999 if index == 0 else 40000 + index})')
                if index < 21:
                    self.assertEqual(args[args.index('-gpgpu') + 1], '1 mig=2')
                    self.assertEqual(args[args.index('-q') + 1], 'ai')
                    self.assertEqual(args[args.index('-W') + 1], '10')
                    self.assertIn('P3_CONDITIONS=A,B,S1,S4', args)
            self.assertIn('P3_MODE=smoke', calls[0])
            self.assertIn('P3_SEEDS=4052', calls[20])
            self.assertIn('P3_TASK_INDEX=9', calls[20])
            self.assertNotIn('-gpgpu', calls[-1])
            again = subprocess.run(command, cwd=root, env=env, capture_output=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(json.loads((root / 'calls.json').read_text()), calls)


@unittest.skipUnless(sys.platform.startswith('linux'), 'School wrappers require Linux')
class SchoolWrapperTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'logs').mkdir()
        (self.root / 'bin').mkdir()
        shutil.copyfile(ROOT / 'scripts/run_school_gpu.sh', self.root / 'scripts/run_school_gpu.sh')
        for name, output in [('git', ''), ('nvidia-smi', 'fake GPU'), ('llama-server', 'CUDA0: fake device')]:
            path = self.root / 'bin' / name
            path.write_text('#!/bin/sh\nprintf "%s\\n" "' + output + '"\n')
            path.chmod(0o755)
        (self.root / 'scripts/serve_model.py').write_text('''
import os, subprocess, sys, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
Path('server.pid').write_text(str(os.getpid()))
if os.getenv('FAKE_START_FAIL'):
    sys.exit(17)
child = subprocess.Popen(['sleep', '300'])
Path('child.pid').write_text(str(child.pid))
if os.getenv('FAKE_TIMEOUT'):
    time.sleep(300)
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')
    def log_message(self, *args):
        pass
HTTPServer(('127.0.0.1', int(sys.argv[sys.argv.index('--port') + 1])), Health).serve_forever()
''')
        (self.root / 'scripts/run_experiment.py').write_text('''
import os, signal, sys, time
from pathlib import Path
if '--check-only' in sys.argv:
    print('{"check":"passed","model_requests":0}')
    sys.exit(0)
Path('runner.pid').write_text(str(os.getpid()))
if os.getenv('FAKE_WAIT'):
    def stop(*args):
        Path('interrupted.txt').write_text('saved partial result')
        sys.exit(130)
    signal.signal(signal.SIGTERM, stop)
    time.sleep(300)
sys.exit(int(os.getenv('FAKE_EXIT', '0')))
''')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.env = {**os.environ, 'PATH': str(self.root / 'bin') + ':' + os.environ['PATH'],
                    'P3_PYTHON': sys.executable, 'P3_SERVER': str(self.root / 'bin/llama-server'),
                    'P3_RUN_ID': 'fake-job', 'P3_PORT': str(port), 'P3_READY_TIMEOUT': '3', 'SLURM_JOB_ID': '123',
                    'CUDA_VISIBLE_DEVICES': '0'}
        self.env.pop('P3_CONTAINER', None)
        self.env.pop('JH_JOBID', None)
        self.env.pop('P3_MODE', None)
        self.env.pop('P3_CONDITIONS', None)
        self.env.pop('P3_TASK_INDEX', None)
        self.env.pop('P3_SEEDS', None)

    def command(self):
        return ['bash', str(self.root / 'scripts/run_school_gpu.sh')]

    def assert_stopped(self):
        for name in ('server.pid', 'child.pid', 'runner.pid'):
            path = self.root / name
            if path.exists():
                pid = path.read_text()
                state = Path('/proc') / pid / 'stat'
                if state.exists():
                    self.assertEqual(state.read_text().split()[2], 'Z', f'{name} process still running')

    def run_wrapper(self, expected):
        result = subprocess.run(self.command(), cwd=self.root, env=self.env, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assert_stopped()
        return result

    def test_refuses_without_allocation(self):
        self.env.pop('SLURM_JOB_ID')
        result = self.run_wrapper(2)
        self.assertIn('Refusing to start', result.stderr)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_success_and_cleanup(self):
        self.run_wrapper(0)
        record = json.loads((self.root / 'logs/fake-job-job/job.json').read_text())
        self.assertEqual((record['exit_code'], record['slurm_job_id']), (0, '123'))
        self.assertTrue((self.root / 'runner.pid').exists())

    def test_cpu_only_slurm_allocation_refused(self):
        self.env.pop('CUDA_VISIBLE_DEVICES')
        result = self.run_wrapper(2)
        self.assertIn('CUDA_VISIBLE_DEVICES', result.stderr)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_unischeduler_allocation_and_metadata(self):
        self.env.pop('SLURM_JOB_ID')
        self.env['JH_JOBID'] = '30530'
        self.run_wrapper(0)
        record = json.loads((self.root / 'logs/fake-job-job/job.json').read_text())
        self.assertEqual(record['unischeduler_job_id'], '30530')
        self.assertEqual(record['scheduler'], 'unischeduler')

    def test_unischeduler_cpu_job_refused(self):
        self.env.pop('SLURM_JOB_ID')
        self.env.pop('CUDA_VISIBLE_DEVICES')
        self.env['JH_JOBID'] = '30530'
        self.run_wrapper(2)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_smoke_arguments_and_invalid_mode(self):
        self.env['P3_MODE'] = 'invalid'
        self.run_wrapper(2)
        self.assertFalse((self.root / 'server.pid').exists())
        self.env['P3_MODE'] = 'smoke'
        path = self.root / 'scripts/run_experiment.py'
        path.write_text("import sys\nassert '--smoke' in sys.argv\nassert sys.argv[sys.argv.index('--seeds') + 1] == '4051'\n" + path.read_text())
        self.run_wrapper(0)

    def test_runner_failure_propagates(self):
        self.env['FAKE_EXIT'] = '7'
        self.run_wrapper(7)

    def test_priority_shard_arguments(self):
        self.env.update(P3_MODE='shard', P3_TASK_INDEX='3', P3_SEEDS='4052', P3_CONDITIONS='A B S1 S4')
        path = self.root / 'scripts/run_experiment.py'
        path.write_text("import sys\nassert sys.argv[sys.argv.index('--task-index') + 1] == '3'\n"
                        "assert sys.argv[sys.argv.index('--seeds') + 1] == '4052'\n"
                        "assert sys.argv[sys.argv.index('--conditions') + 1:sys.argv.index('--conditions') + 5] == ['A','B','S1','S4']\n"
                        + path.read_text())
        self.run_wrapper(0)

    def test_server_startup_failure(self):
        self.env['FAKE_START_FAIL'] = '1'
        self.run_wrapper(1)
        self.assertFalse((self.root / 'runner.pid').exists())

    def test_server_timeout(self):
        self.env['FAKE_TIMEOUT'] = '1'
        self.env['P3_READY_TIMEOUT'] = '1'
        self.run_wrapper(1)
        self.assertFalse((self.root / 'runner.pid').exists())

    def test_no_cuda_device_refused(self):
        (self.root / 'bin/llama-server').write_text('#!/bin/sh\necho "CPU only"\n')
        self.run_wrapper(2)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_duplicate_run_id_refused(self):
        (self.root / 'logs/fake-job').mkdir()
        self.run_wrapper(2)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_occupied_port_refused_before_server(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', int(self.env['P3_PORT'])))
            sock.listen()
            self.run_wrapper(1)
        self.assertFalse((self.root / 'server.pid').exists())

    def test_sigterm_preserves_runner_cleanup(self):
        self.env['FAKE_WAIT'] = '1'
        process = subprocess.Popen(self.command(), cwd=self.root, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not (self.root / 'runner.pid').exists() and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue((self.root / 'runner.pid').exists())
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 143, stdout + stderr)
            self.assertTrue((self.root / 'interrupted.txt').exists())
            self.assert_stopped()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


class ServePortTest(unittest.TestCase):
    def test_port_forwarding_without_model(self):
        # serve_model historically imports setup_baseline as a sibling script.
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            from scripts import serve_model
        finally:
            sys.path.pop(0)
        with patch('sys.argv', ['serve_model.py', '--llama-server', '/fake/server', '--device', 'CUDA0', '--port', '23901']), \
                patch.object(serve_model.subprocess, 'check_output', return_value='build 12244, test'), \
                patch.object(serve_model, 'digest', return_value=json.loads((ROOT / 'configs/baseline.json').read_text())['model']['sha256']), \
                patch.object(serve_model.os, 'execv', side_effect=SystemExit(0)) as execute:
            with self.assertRaises(SystemExit):
                serve_model.main()
            command = execute.call_args.args[1]
            self.assertEqual(command[command.index('--port') + 1], '23901')


if __name__ == '__main__':
    unittest.main()
