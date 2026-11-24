"""Keep the interrupted batch separate and include its actual cost in the final report."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


PREFIX = 'supplementary-dev-4053-20261123'
COSTS = ('model_calls', 'input_tokens', 'output_tokens', 'inference_seconds', 'env_actions')


def read(path):
    return json.loads(Path(path).read_bytes())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def trace_hashes(path, completed):
    hashes, active = {}, None
    with Path(path).open() as source:
        for line in source:
            event = json.loads(line)
            if event['event'] == 'unit_start':
                active = event['condition']
                if active in completed:
                    if active in hashes:
                        raise ValueError('Repeated trace unit')
                    hashes[active] = hashlib.sha256()
            if active not in completed or event['event'] == 'first_attempt_audit':
                continue
            stable = {k: v for k, v in event.items() if k not in ('request_seconds', 'inference_seconds')}
            hashes[active].update((json.dumps(stable, sort_keys=True) + '\n').encode())
    if set(hashes) != set(completed):
        raise ValueError('Incomplete source trace')
    return {k: h.hexdigest() for k, h in hashes.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    root = args.repo.resolve()
    failed = root / 'logs' / f'{PREFIX}-s4053-t2'
    retry = root / 'logs' / f'{PREFIX}-s4053-t2-r1'
    summary = read(failed / 'summary.json')
    job = read(Path(str(failed) + '-job') / 'job.json')
    completed = {r['condition']: r for r in rows(failed / 'task_results.jsonl')}
    if summary['status'] != 'interrupted' or summary['completed_units'] != 6 or job['exit_code'] != 130:
        raise ValueError('Unexpected interrupted batch; inspect before reporting')
    old_hashes = trace_hashes(failed / 'trace.jsonl', completed)
    if args.check_only:
        print(json.dumps({'check': 'passed', 'preserved_completed_units': len(completed), 'failed_job': job['unischeduler_job_id'], 'model_requests': 0}))
        return
    before, after = read(failed / 'manifest.json'), read(retry / 'manifest.json')
    for key in ('git_commit', 'protocol', 'config', 'instructions', 'game_sha256', 'schedule', 'source_sha256', 'runtime_sha256', 'gpu_type_driver'):
        if before[key] != after[key]:
            raise ValueError(f'Retry changed frozen condition: {key}')
    new_hashes = trace_hashes(retry / 'trace.jsonl', completed)
    differences = [c for c in completed if old_hashes[c] != new_hashes[c]]
    paths = [root / 'logs' / (f'{PREFIX}-s4053-t{i}' + ('-r1' if i == 2 else '')) for i in range(20)]
    output = root / 'logs' / f'{PREFIX}-merged'
    subprocess.run([str(root / '.venv/bin/python'), str(root / 'scripts/report_supplementary.py'),
                    '--output', str(output), *map(str, paths)], cwd=root,
                   env={**os.environ, 'P3_EXPERIMENT': 'supplementary-4053'}, check=True)
    comparison = read(output / 'comparison.json')
    merged = read(output / 'summary.json')
    comparison['interrupted_batch'] = {'path': str(failed), 'job': job, 'summary': summary,
                                      'excluded_completed_units': 6, 'excluded_partial_units': 1,
                                      'repeat_behavior_differences': differences,
                                      'selection_rule': 'Always use the entire completed retry batch, fixed before retry; never select outcomes by condition.'}
    comparison['actual_wrapper_seconds_including_interruption'] = comparison['wrapper_seconds'] + job['wrapper_seconds']
    comparison['actual_logged_cost_including_interruption'] = {
        k: merged['all_cost_including_incomplete'][k] + summary['all_cost_including_incomplete'][k] for k in COSTS}
    comparison['interruption_cost_note'] = 'Interrupted in-flight response may be absent from token/inference counters; these are recorded-cost lower bounds. Job runtime includes it.'
    (output / 'comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    note = (f'\n## 超时恢复与实际成本\n\n原第三批作业 30642 触及 10 分钟时限，中断前完成 6 组、另 1 组未完成；原始日志完整保留。'
            f'正式比较固定采用完整重跑的七组，不按结果挑选，仍为 20 道唯一任务、140 个有效单元。剩余作业时限调整为 20 分钟，模型/任务/种子/提示词/三次尝试和动作预算均不变。\n\n'
            f'上面的 20 批耗时是有效结果的运行时间；另计中断作业 {job["wrapper_seconds"]} 秒。'
            f'实际总运行时间为 {comparison["actual_wrapper_seconds_including_interruption"]/60:.2f} MIG 实例分钟。'
            f'中断批次的调用与已收到响应的 token、推理时间已另计在 comparison.json；终止瞬间尚未返回的响应无法完整计入 token，所以这部分计数是下界。\n\n'
            f'重跑与中断前已完成六组的完整行为差异组别：{differences or "无"}。原始与重跑轨迹均保留。\n')
    with (output / 'report.md').open('a', encoding='utf-8') as report:
        report.write(note)
    print(json.dumps({'status': 'complete', 'unique_units': 140, 'extra_completed_units': 6, 'extra_partial_units': 1, 'output': str(output)}))


if __name__ == '__main__':
    main()
