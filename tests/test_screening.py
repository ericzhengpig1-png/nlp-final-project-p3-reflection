import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_experiment as experiment
from scripts.run_baseline import ROOT, reflexion_assets, run_task
from src.reflection.instructions import reflection_prompt
from tests.test_baseline import ScriptedModel


class ScreeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.config, cls.tasks, cls.instructions, cls.games, cls.assets = experiment.load_inputs()

    def test_only_instruction_changes(self):
        query = self.assets[1]
        scenario = 'Here is the task: test failed trajectory\nSTATUS: FAIL'
        memory = ['Previous plan with evidence']
        original = query(scenario, memory)
        self.assertEqual(reflection_prompt(query, scenario, memory, None), original)
        base = self.instructions['B']
        for condition in experiment.CONDITIONS[2:]:
            candidate = reflection_prompt(query, scenario, memory, self.instructions[condition])
            self.assertEqual(candidate, self.instructions[condition] + original[len(base):])
        with self.assertRaisesRegex(ValueError, 'prefix'):
            reflection_prompt(lambda *_: 'Changed upstream query', scenario, memory, self.instructions['S1'])

    def test_frozen_files_reject_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'instruction.txt'
            path.write_text('wrong instruction', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                experiment.read_frozen(path, '0' * 64)

    def test_schedule_and_second_seed_alone(self):
        schedule = experiment.make_schedule(self.tasks, [4051, 4052])
        self.assertEqual(len(schedule), 140)
        self.assertEqual(len({(u['seed'], u['task_id'], u['condition']) for u in schedule}), 140)
        self.assertEqual([u['condition'] for u in schedule[:7]], list(experiment.CONDITIONS))
        self.assertEqual([u['condition'] for u in schedule[7:14]], list(experiment.CONDITIONS[1:] + experiment.CONDITIONS[:1]))
        self.assertEqual(experiment.make_schedule(self.tasks, [4052]), schedule[70:])
        for seeds in ([1], [4051, 4051], [4052, 4051], []):
            with self.assertRaises(ValueError):
                experiment.make_schedule(self.tasks, seeds)

    def test_recovery_and_paired_denominators(self):
        results = [dict(seed=4051, condition=c, task_id=t, attempts=a)
                   for c, t, a in [('A', 'one', [True]), ('B', 'one', [False, False, False]),
                                   ('B', 'two', [False, True]), ('S1', 'one', [False, True]),
                                   ('S1', 'two', [False, False, False])]]
        summary = experiment.summarize(results, [4051], 10)
        self.assertIsNone(summary['per_seed']['4051']['A']['recovery_rate'])
        self.assertEqual(summary['per_seed']['4051']['B']['recovery_rate'], .5)
        self.assertEqual(summary['paired']['4051']['S1']['B'],
                         {'paired_tasks': 2, 'wins': 1, 'losses': 1, 'ties': 0, 'net_successes': 0})
        self.assertEqual(summary['per_seed']['4051']['S5']['completed_tasks'], 0)
        self.assertIsNone(summary['per_seed']['4051']['S5']['cumulative_success_rate'])

    def test_real_environment_all_groups_isolate_memory(self):
        def actions(context):
            turn = context['policy_turn']
            if turn <= 2:
                return ('go to bed 1', 'take book 1 from bed 1')[turn - 1]
            return ('inventory', 'look')[turn % 2]

        resets, first_calls = {}, []
        for condition in experiment.CONDITIONS:
            trace, model = [], ScriptedModel(actions)
            results = run_task(self.games[self.tasks[0]], condition, self.config, self.assets,
                               model, lambda event, **fields: trace.append((event, fields)), resets,
                               reflection_instruction=self.instructions[condition] if condition.startswith('S') else None)
            self.assertEqual(results, [False, False, False])
            starts = [f for e, f in trace if e == 'reset']
            self.assertEqual(starts[0]['memory'], [])
            self.assertEqual(len(starts[-1]['memory']), 0 if condition == 'A' else 2)
            self.assertEqual(len({s['initial_state_sha256'] for s in starts}), 1)
            self.assertEqual([f['env_actions'] for e, f in trace if e == 'attempt_end'], [30] * 3)
            reflections = [call for call in model.calls if call[0] == 'reflection']
            self.assertEqual(len(reflections), 0 if condition == 'A' else 2)
            for call in reflections:
                self.assertTrue(call[2].startswith(self.instructions[condition] + ' Here are two examples:'))
            first_calls.append(model.calls[:30])
        self.assertTrue(all(calls == first_calls[0] for calls in first_calls))

    def fake_task(self, game, condition, config, assets, model, record, resets, reflection_instruction=None):
        record('model_request', kind='action', seed=config['seed'] + 1, prompt_sha256='same', attempt=1)
        record('model_response', kind='action', seed=config['seed'] + 1, output='look', attempt=1,
               input_tokens=10, output_tokens=1, inference_seconds=.01)
        record('attempt_end', success=False, reason='env_action_cap', env_actions=30, policy_turns=30, attempt=1)
        return [False, condition != 'A'] if condition != 'A' else [False, False, False]

    def run_fake(self, run, task=None):
        inputs = self.protocol, self.config, self.tasks, self.instructions, self.games, self.assets
        with patch.object(experiment, 'LlamaServer') as server, \
                patch.object(experiment, 'run_task', side_effect=task or self.fake_task), \
                contextlib.redirect_stdout(io.StringIO()):
            experiment.execute(run, 'http://unused', [4051, 4052], inputs)
            self.assertEqual(server.call_count, 1)

    def test_complete_mock_run_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'mock'
            self.run_fake(run)
            summary = json.loads((run / 'summary.json').read_text())
            self.assertEqual((summary['status'], summary['completed_units']), ('complete', 140))
            self.assertTrue(summary['full_two_seed_screening'])
            self.assertEqual(summary['mean_over_requested_seeds']['S1']['net_successes_vs_A'], 10)
            rows = [json.loads(line) for line in (run / 'task_results.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 140)
            self.assertTrue(all(row['first_attempt_matches'] for row in rows))
            self.assertEqual(summary['all_cost_including_incomplete']['model_calls'], 140)
            with self.assertRaises(FileExistsError):
                self.run_fake(run)

    def test_failure_and_interrupt_preserve_partial_results(self):
        for failure in (RuntimeError('injected failure'), KeyboardInterrupt('injected SIGTERM')):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                calls = 0

                def fail_second(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        args[5]('model_request', kind='action', seed=4052, prompt_sha256='same', attempt=1)
                        raise failure
                    return self.fake_task(*args, **kwargs)

                run = Path(directory) / 'mock'
                with self.assertRaises(type(failure)):
                    self.run_fake(run, fail_second)
                summary = json.loads((run / 'summary.json').read_text())
                self.assertEqual(summary['completed_units'], 1)
                self.assertEqual(summary['all_cost_including_incomplete']['model_calls'], 2)
                self.assertEqual(summary['status'], 'interrupted' if isinstance(failure, KeyboardInterrupt) else 'failed')
                self.assertIsNone(summary['mean_over_requested_seeds'])
                self.assertEqual(len((run / 'task_results.jsonl').read_text().splitlines()), 1)
                self.assertIn('run_error', (run / 'trace.jsonl').read_text())

    def test_first_attempt_mismatch_stops_run(self):
        def different_first(*args, **kwargs):
            result = self.fake_task(*args, **kwargs)
            if args[1] == 'B':
                args[5]('thought', text='unexpected divergence', attempt=1)
            return result

        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'mock'
            with self.assertRaisesRegex(RuntimeError, 'First-attempt mismatch'):
                self.run_fake(run, different_first)
            summary = json.loads((run / 'summary.json').read_text())
            self.assertEqual((summary['status'], summary['completed_units']), ('failed', 2))
            rows = [json.loads(line) for line in (run / 'task_results.jsonl').read_text().splitlines()]
            self.assertFalse(rows[-1]['first_attempt_matches'])

    def test_check_only_never_connects_to_model(self):
        with patch('sys.argv', ['run_experiment.py', '--check-only']), \
                patch.object(experiment, 'LlamaServer') as server, contextlib.redirect_stdout(io.StringIO()):
            experiment.main()
            server.assert_not_called()

    def test_success_and_policy_turn_cap_for_candidate(self):
        for actions, expected, reason in ((iter((ROOT / 'configs/tutorial_actions.txt').read_text().splitlines()), [True], 'won'),
                                          (None, [False] * 3, 'policy_turn_cap')):
            model = ScriptedModel(lambda context: next(actions) if actions else f'think: consider step {context["policy_turn"]}')
            trace = []
            result = run_task(self.games[self.tasks[0]], 'S5', self.config, self.assets, model,
                              lambda event, **fields: trace.append((event, fields)), {}, self.instructions['S5'])
            self.assertEqual(result, expected)
            self.assertEqual([f['reason'] for e, f in trace if e == 'attempt_end'], [reason] * len(expected))
            if actions:
                self.assertEqual(len(model.calls), 4)
            else:
                self.assertEqual([f['policy_turns'] for e, f in trace if e == 'attempt_end'], [49] * 3)


if __name__ == '__main__':
    unittest.main()
