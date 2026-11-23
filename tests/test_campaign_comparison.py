import json
import tempfile
import unittest
from pathlib import Path

from analysis import compare_development_campaigns as comparison


class CampaignComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / 'registry.json'
        self.tasks = [f'dev/{i}' for i in range(10)]
        self.write(self.registry, {'development': self.tasks, 'held_out': [f'held/{i}' for i in range(30)]})
        self.old = self.make_campaign('old', comparison.COHORTS[0], 1)
        self.new = self.make_campaign('new', comparison.COHORTS[1], 2)

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def make_campaign(self, name, conditions, timing):
        merged = self.root / name
        merged.mkdir()
        common = {k: 'fixed' for k in comparison.COMMON}
        sources, rows = [], []
        for seed in comparison.SEEDS:
            for index, task in enumerate(self.tasks):
                shard = self.root / f'{name}-{seed}-{index}'
                shard.mkdir()
                job = Path(str(shard) + '-job')
                job.mkdir()
                batch, trace = [], []
                for c in conditions:
                    unit = {'seed': seed, 'task_id': task, 'condition': c}
                    cost = {k: timing if k == 'inference_seconds' else 1 for k in comparison.COST_KEYS}
                    batch.append({**unit, 'attempts': [True], 'cost': cost,
                                  'first_attempt_matches': True, 'first_attempt_sha256': 'same'})
                    trace.extend([{**unit, 'event': 'unit_start'},
                                  {**unit, 'event': 'reset', 'initial_state_sha256': 'same'},
                                  {**unit, 'event': 'model_response', 'output': 'fixed', 'inference_seconds': timing, 'request_seconds': timing},
                                  {**unit, 'event': 'first_attempt_audit', 'reference': name}])
                self.write(shard / 'manifest.json', {**common, 'mode': 'shard', 'git_dirty': False,
                           'conditions': conditions, 'schedule': [{k: r[k] for k in ('seed', 'task_id', 'condition')} for r in batch],
                           'game_sha256': {task: 'data'}, 'task_index': index})
                self.write(shard / 'summary.json', {'status': 'complete', 'completed_units': len(batch), 'expected_units': len(batch)})
                (shard / 'task_results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in batch), encoding='utf-8')
                (shard / 'trace.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in trace), encoding='utf-8')
                job_id = f'{seed}{index}'
                self.write(job / 'job.json', {'exit_code': 0, 'unischeduler_job_id': job_id, 'wrapper_seconds': 10})
                sources.append({'path': str(shard), 'unischeduler_job_id': job_id,
                                'manifest_sha256': comparison.digest(shard / 'manifest.json'),
                                'results_sha256': comparison.digest(shard / 'task_results.jsonl')})
                rows.extend(batch)
        self.write(merged / 'manifest.json', {**common, 'mode': 'merged-screening', 'conditions': conditions, 'sources': sources})
        (merged / 'task_results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        self.write(merged / 'summary.json', {'status': 'complete', 'conditions': conditions,
                   'completed_units': len(rows), 'expected_units': len(rows),
                   'all_cost_including_incomplete': {k: sum(r['cost'][k] for r in rows) for k in comparison.COST_KEYS}})
        return merged

    def compare(self):
        return comparison.compare_campaigns(self.old, self.new, self.registry)

    def test_complete_comparison_deduplicates_results_but_counts_all_cost(self):
        report, rows = self.compare()
        self.assertEqual(len(rows), 140)
        self.assertEqual(report['actual_units'], 180)
        self.assertEqual(report['repeated_baseline_units_verified'], 40)
        self.assertEqual(report['actual_cost_including_repeated_baselines']['model_calls'], 180)
        self.assertEqual(report['actual_cost_including_repeated_baselines']['inference_seconds'], 280)
        self.assertEqual(report['wrapper_seconds_including_repeated_baselines'], 400)
        self.assertEqual(report['conditions']['B']['inference_seconds'], 20)
        self.assertEqual(report['baseline_repeats']['repeat']['B']['inference_seconds'], 40)
        self.assertEqual(report['conditions']['S2']['cost_change_vs_same_cohort_B_pct']['inference_seconds'], 0)
        self.assertIn('140', comparison.markdown(report))

    def test_incomplete_campaign_is_rejected(self):
        path = self.new / 'summary.json'
        value = comparison.read_json(path)
        value['status'] = 'running'
        self.write(path, value)
        with self.assertRaisesRegex(ValueError, 'Incomplete campaign'):
            self.compare()

    def test_held_out_task_is_rejected(self):
        path = self.new / 'task_results.jsonl'
        path.write_text(path.read_text().replace('dev/0', 'held/0'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unexpected, missing or duplicate'):
            self.compare()

    def test_source_mutation_is_rejected(self):
        path = self.root / 'new-4051-0/task_results.jsonl'
        path.write_text(path.read_text() + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.compare()

    def test_full_behavior_change_is_rejected_even_with_same_success(self):
        path = self.root / 'new-4051-0/trace.jsonl'
        path.write_text(path.read_text().replace('"output": "fixed"', '"output": "changed"', 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Repeated A/B behavior changed'):
            self.compare()

    def test_cross_campaign_runtime_change_is_rejected(self):
        manifest_path = self.new / 'manifest.json'
        manifest = comparison.read_json(manifest_path)
        manifest['runtime_sha256'] = 'different'
        for source in manifest['sources']:
            path = Path(source['path']) / 'manifest.json'
            value = comparison.read_json(path)
            value['runtime_sha256'] = 'different'
            self.write(path, value)
            source['manifest_sha256'] = comparison.digest(path)
        self.write(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, 'Campaign version mismatch'):
            self.compare()


if __name__ == '__main__':
    unittest.main()
