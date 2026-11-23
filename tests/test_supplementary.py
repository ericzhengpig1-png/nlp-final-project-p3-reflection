"""No-model safety and completeness checks; run with P3_EXPERIMENT=supplementary-4053."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_experiment as e
from scripts.merge_screening import merge_runs
from experiments.supplementary_4053.freeze_tasks import select, TYPES
from scripts.report_supplementary import make_report


class SupplementaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert e.SUPPLEMENTARY
        cls.inputs = e.load_inputs()

    def test_frozen_selection_is_disjoint_and_balanced(self):
        r = json.loads(e.REGISTRY_PATH.read_bytes())
        tasks = self.inputs[2]
        self.assertEqual(len(set(tasks)), 20)
        self.assertFalse(set(tasks) & set(r['held_out'] + r['original_development']))
        self.assertFalse({t.split('/')[-1] for t in tasks} & set(r['excluded_trial_ids']))
        counts = sorted(sum(t.split('/')[-2].split('-')[0] == k for t in tasks) for k in TYPES)
        self.assertEqual(counts, [3,3,3,3,4,4])
        candidates = [f'json_2.1.1/valid_seen/{k}-X/trial_T20000101_000000_{i}' for k in TYPES for i in range(8)]
        self.assertEqual(select(candidates, set()), select(list(reversed(candidates)), set()))
        self.assertNotIn(candidates[0], select(candidates, {candidates[0].split('/')[-1]}))

    def test_schedule_has_140_units_and_preserves_shard_order(self):
        tasks = self.inputs[2]
        full = e.make_schedule(tasks, [4053])
        parts = [u for i,t in enumerate(tasks) for u in e.make_schedule([t], [4053], task_offset=i)]
        self.assertEqual(full, parts)
        self.assertEqual(len(full), 140)
        for seed in (4051,4052):
            with self.assertRaises(ValueError):e.make_schedule(tasks,[seed])
        with self.assertRaises(ValueError):e.make_schedule(tasks,[4053],('A','B','S1'))

    def test_check_only_never_contacts_model(self):
        for i in (0,19):
            with patch.object(sys,'argv',['run_experiment.py','--check-only','--task-index',str(i),'--seeds','4053']), patch.object(e,'LlamaServer') as model, contextlib.redirect_stdout(io.StringIO()):
                e.main()
                model.assert_not_called()

    @staticmethod
    def fake_task(game, condition, config, assets, model, record, resets, reflection_instruction=None):
        record('model_request',kind='action',seed=config['seed']+1,prompt_sha256='same',attempt=1)
        record('model_response',kind='action',seed=config['seed']+1,output='look',attempt=1,input_tokens=10,output_tokens=1,inference_seconds=.01)
        record('attempt_end',success=False,reason='env_action_cap',env_actions=30,policy_turns=30,attempt=1)
        return [False, condition != 'A']

    def test_complete_merge_and_reject_partial_duplicate_or_bad_audit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(e,'LlamaServer'), patch.object(e,'run_task',side_effect=self.fake_task), patch.object(e,'git',side_effect=lambda *a:'' if a[0]=='status' else 'test'), contextlib.redirect_stdout(io.StringIO()):
            base=Path(tmp); paths=[]
            for i in range(20):
                p=base/str(i)
                e.execute(p,'http://unused',[4053],e.select_inputs(self.inputs,task_index=i),task_index=i)
                paths.append(p)
            s=merge_runs(paths,base/'merged')
            self.assertEqual(s['completed_units'],140)
            self.assertFalse(s['full_two_seed_screening'])
            self.assertEqual(s['per_seed']['4053']['B']['recovery_rate'],1)
            for i,p in enumerate(paths):
                f=p/'manifest.json'; manifest=json.loads(f.read_bytes())
                manifest['unischeduler_job_id']=str(100+i);f.write_text(json.dumps(manifest))
                job=Path(str(p)+'-job');job.mkdir()
                (job/'job.json').write_text(json.dumps({'exit_code':0,'unischeduler_job_id':str(100+i),'wrapper_seconds':2}))
            make_report(paths,base/'report')
            report=json.loads((base/'report/comparison.json').read_bytes())
            self.assertEqual(report['units'],140)
            self.assertEqual(report['wrapper_seconds'],40)
            self.assertEqual(report['paired']['S1']['A']['net'],20)
            self.assertEqual(report['held_out_units'],0)
            with self.assertRaises(FileExistsError):make_report(paths,base/'report')
            with self.assertRaisesRegex(ValueError,'Missing'):merge_runs(paths[:-1],base/'missing')
            with self.assertRaisesRegex(ValueError,'Duplicate'):merge_runs(paths+[paths[0]],base/'dup')
            f=paths[0]/'task_results.jsonl'; rows=[json.loads(x) for x in f.read_text().splitlines()]
            rows[0]['first_attempt_matches']=False
            f.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'audit'):merge_runs(paths,base/'bad')

    def test_first_attempt_mismatch_stops_batch(self):
        def mismatch(*args,**kwargs):
            result=self.fake_task(*args,**kwargs)
            if args[1]=='B':args[5]('thought',text='unexpected',attempt=1)
            return result
        with tempfile.TemporaryDirectory() as tmp, patch.object(e,'LlamaServer'), patch.object(e,'run_task',side_effect=mismatch), contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp)/'run'
            with self.assertRaisesRegex(RuntimeError,'First-attempt mismatch'):
                e.execute(p,'http://unused',[4053],e.select_inputs(self.inputs,task_index=0),task_index=0)
            self.assertEqual(json.loads((p/'summary.json').read_bytes())['status'],'failed')

    def test_all_20_tasks_have_identical_first_request_and_empty_memory(self):
        class StopBeforeInference(Exception):pass
        for task in self.inputs[2]:
            first=[]; resets={}
            for c in e.CONDITIONS:
                seen=[]
                class NoInference:
                    def generate(self,prompt,kind,seed,**context):
                        first.append((prompt,kind,seed))
                        raise StopBeforeInference()
                with self.assertRaises(StopBeforeInference):
                    e.run_task(self.inputs[4][task],c,{**self.inputs[1],'seed':4053},self.inputs[5],NoInference(),
                               lambda event,**fields:seen.append((event,fields)),resets,
                               self.inputs[3][c] if c.startswith('S') else None)
                self.assertEqual([v['memory'] for k,v in seen if k=='reset'],[[]])
            self.assertEqual(len(first),7)
            self.assertTrue(all(x==first[0] for x in first))


if __name__ == '__main__':unittest.main()
