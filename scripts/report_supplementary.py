"""Complete-only paired report for the 20-task, seed-4053 supplementary experiment."""
import argparse
import json
import math
from pathlib import Path

try:
    from scripts.merge_screening import merge_runs
    from scripts import run_experiment as experiment
except ModuleNotFoundError:
    from merge_screening import merge_runs
    import run_experiment as experiment


def make_report(paths, output):
    if not experiment.SUPPLEMENTARY:
        raise ValueError('Set P3_EXPERIMENT=supplementary-4053')
    # Validate scheduler completion and trace presence before creating any report.
    jobs = []
    for path in paths:
        job = json.loads(Path(str(path) + '-job/job.json').read_bytes())
        manifest = json.loads((path / 'manifest.json').read_bytes())
        if job['exit_code'] != 0 or job['unischeduler_job_id'] != manifest['unischeduler_job_id']:
            raise ValueError(f'Failed or mismatched GPU job: {path}')
        if manifest.get('experiment_label') != 'supplementary-development' or not (path / 'trace.jsonl').stat().st_size:
            raise ValueError(f'Wrong experiment or missing trace: {path}')
        jobs.append({**job, 'run': str(path)})
    if len(jobs) != 20 or len({j['unischeduler_job_id'] for j in jobs}) != 20:
        raise ValueError('Expected 20 unique completed jobs')
    summary = merge_runs(paths, output)
    rows = [json.loads(line) for line in (output / 'task_results.jsonl').read_text().splitlines()]
    for name in experiment.COST_KEYS:
        if not math.isclose(sum(r['cost'][name] for r in rows), summary['all_cost_including_incomplete'][name], abs_tol=1e-6):
            raise ValueError('Cost totals inconsistent')
    tasks = experiment.load_inputs()[2]
    indexed = {(r['task_id'], r['condition']): r for r in rows}
    per = summary['per_seed']['4053']
    pairs = {}
    for c in experiment.CONDITIONS[2:]:
        pairs[c] = {}
        for b in ('A', 'B'):
            wins, losses, detail = [], [], []
            for t in tasks:
                a, baseline = indexed[t, c], indexed[t, b]
                actual, ref = any(a['attempts']), any(baseline['attempts'])
                if actual and not ref: wins.append(t)
                if ref and not actual: losses.append(t)
                detail.append({'task_id': t, 'candidate_attempts': a['attempts'], 'baseline_attempts': baseline['attempts'],
                               'cost_delta': {k: a['cost'][k] - baseline['cost'][k] for k in experiment.COST_KEYS}})
            pairs[c][b] = {'wins': wins, 'losses': losses, 'ties': 20-len(wins)-len(losses),
                           'net': len(wins)-len(losses), 'tasks': detail,
                           'cost_change_pct': {k: 100*(per[c][k]/per[b][k]-1) if per[b][k] else None for k in experiment.COST_KEYS}}
    # Keep representative evidence selected by frozen task order, never best-looking gain.
    cases = []
    for c in experiment.CONDITIONS[2:]:
        for direction in ('wins', 'losses'):
            candidates = pairs[c]['B'][direction]
            if not candidates: continue
            task = candidates[0]
            shard = next(p for p in paths if json.loads((p / 'manifest.json').read_bytes())['schedule'][0]['task_id'] == task)
            events = []
            for number, line in enumerate((shard / 'trace.jsonl').read_text().splitlines(), 1):
                e = json.loads(line)
                if e.get('condition') not in (c, 'B'): continue
                if e['event'] in ('attempt_end', 'reflection') or (e['event'] == 'model_response' and e.get('kind') == 'reflection'):
                    events.append({'trace_line': number, **e})
            cases.append({'condition': c, 'direction_vs_B': direction, 'task_id': task,
                          'candidate_attempts': indexed[task, c]['attempts'], 'baseline_attempts': indexed[task, 'B']['attempts'],
                          'trace': str(shard / 'trace.jsonl'), 'events': events})
    comparison = {'label': 'supplementary-development', 'status': 'complete', 'seed': 4053, 'tasks': tasks,
                  'units': 140, 'held_out_units': 0, 'metrics': per, 'paired': pairs, 'cases': cases,
                  'jobs': jobs, 'wrapper_seconds': sum(j['wrapper_seconds'] for j in jobs),
                  'note': 'Within-campaign paired comparisons only. Tasks and seed both changed; no attribution to seed and no pooling with earlier scores.'}
    experiment.write_json(output / 'comparison.json', comparison)
    lines = ['# 补充开发实验：20 道新题 × 种子 4053 × 七组', '',
             '仅在本轮任务内配对比较；不使用原 10 道开发题和 30 道留出题，不与旧轮成绩混算。首次成功后停止，三次内成功为累计成功。', '',
             '| 组别 | 首次成功 | 三次内成功 | 首败恢复 | 调用数 | 输入 token | 输出 token | 推理秒 |',
             '| --- | --- | --- | --- | ---: | ---: | ---: | ---: |']
    for c, m in per.items():
        recovery = f"{m['recovered']}/{m['initial_failures']} ({m['recovery_rate']:.1%})" if m['initial_failures'] else '0/0（不适用）'
        lines.append(f"| {c} | {m['first_successes']}/20 ({m['first_success_rate']:.1%}) | {m['total_successes']}/20 ({m['cumulative_success_rate']:.1%}) | {recovery} | {m['model_calls']} | {m['input_tokens']} | {m['output_tokens']} | {m['inference_seconds']:.2f} |")
    lines += ['', '| 候选 | 对照 | 改善/退步/持平 | 净成功 | 调用变化 | 输入变化 | 输出变化 | 推理时间变化 |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for c, refs in pairs.items():
        for b, p in refs.items():
            d = p['cost_change_pct']
            lines.append(f"| {c} | {b} | {len(p['wins'])}/{len(p['losses'])}/{p['ties']} | {p['net']:+d} | {d['model_calls']:+.1f}% | {d['input_tokens']:+.1f}% | {d['output_tokens']:+.1f}% | {d['inference_seconds']:+.1f}% |")
    lines += ['', f"20 个 GPU 作业实际运行时间合计 {comparison['wrapper_seconds']/60:.2f} 分钟（A30 MIG 实例，含启动清理，非完整 GPU 卡时或计费时长）。逐作业时间见 comparison.json 的 jobs。", '',
              '每个作业由七组共享，作业时间不伪分摊至各组；各组成本以调用、token 和推理时间比较。', '',
              '## 具体案例', '', '按冻结题目顺序，为每个候选分别取相对 B 的第一个改善和第一个退步；所有逐题结果与成本差异见 comparison.json。']
    for case in cases:
        lines += ['', f"### {case['condition']}：{case['direction_vs_B']}", '', f"任务：`{case['task_id']}`",
                  f"尝试结果：B={case['baseline_attempts']}；候选={case['candidate_attempts']}。", f"轨迹：`{case['trace']}`"]
        for event in case['events']:
            if event['event'] == 'attempt_end':
                lines.append(f"- L{event['trace_line']} {event['condition']} 尝试 {event.get('attempt')}: {event.get('reason')}，动作 {event.get('env_actions')}。")
            elif event.get('kind') == 'reflection':
                text = event.get('output', '').replace('\n', ' ')
                lines.append(f"- L{event['trace_line']} {event['condition']} 反思原文：{text}")
    lines += ['', '这些是开发集探索结果，不能直接当作课程最终留出评测或统计显著性证明。', '']
    (output / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': 'complete', 'units': 140, 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('runs', type=Path, nargs='+')
    args = parser.parse_args()
    make_report(args.runs, args.output)
