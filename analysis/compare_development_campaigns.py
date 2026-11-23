"""Compare two complete development campaigns without running a model."""
import argparse
import hashlib
import json
import math
from pathlib import Path


SEEDS = (4051, 4052)
CONDITIONS = ('A', 'B', 'S1', 'S2', 'S3', 'S4', 'S5')
COHORTS = (('A', 'B', 'S1', 'S4'), ('A', 'B', 'S2', 'S3', 'S5'))
COST_KEYS = ('model_calls', 'input_tokens', 'output_tokens', 'inference_seconds', 'env_actions')
COMMON = ('git_commit', 'protocol', 'protocol_sha256', 'config', 'instructions',
          'python', 'alfworld', 'textworld', 'source_sha256', 'runtime_sha256', 'gpu_type_driver')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    return row['seed'], row['task_id'], row['condition']


def require(value, message):
    if not value:
        raise ValueError(message)


def baseline_trace_hashes(path):
    """Keep whole attempts; discard timings and cohort-dependent audit references."""
    hashes, counts, active = {}, {}, None
    with Path(path).open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            if row['event'] == 'unit_start':
                active = key(row)
                if active[2] in ('A', 'B'):
                    require(active not in hashes, 'Repeated baseline trace unit')
                    hashes[active] = hashlib.sha256()
                    counts[active] = 0
            if active not in hashes or row['event'] == 'first_attempt_audit':
                continue
            stable = {k: v for k, v in row.items() if k not in ('request_seconds', 'inference_seconds')}
            hashes[active].update((json.dumps(stable, sort_keys=True) + '\n').encode())
            counts[active] += row['event'] == 'model_response'
    require(all(counts.values()), 'Baseline trace lacks model responses')
    return {k: v.hexdigest() for k, v in hashes.items()}


def load_campaign(path, conditions, tasks):
    path = Path(path)
    manifest, summary = read_json(path / 'manifest.json'), read_json(path / 'summary.json')
    raw = read_rows(path / 'task_results.jsonl')
    expected = {(s, t, c) for s in SEEDS for t in tasks for c in conditions}
    require(manifest['mode'] == 'merged-screening' and summary['status'] == 'complete', 'Incomplete campaign')
    require(tuple(manifest['conditions']) == tuple(summary['conditions']) == conditions, 'Unexpected conditions')
    require(summary['completed_units'] == summary['expected_units'] == len(raw) == len(expected), 'Incomplete unit count')
    rows = {key(r): r for r in raw}
    require(len(rows) == len(raw) and set(rows) == expected, 'Unexpected, missing or duplicate task/seed/condition')
    require(len(manifest['sources']) == 20, 'Expected 20 source batches')
    common = {k: manifest[k] for k in COMMON}
    traces, shard_rows, allocations, games = {}, {}, [], {}
    for source in manifest['sources']:
        shard = Path(source['path'])
        require(digest(shard / 'manifest.json') == source['manifest_sha256'] and
                digest(shard / 'task_results.jsonl') == source['results_sha256'], 'Source hash mismatch')
        m, s = read_json(shard / 'manifest.json'), read_json(shard / 'summary.json')
        batch = read_rows(shard / 'task_results.jsonl')
        require(m['mode'] == 'shard' and not m['git_dirty'] and s['status'] == 'complete', 'Invalid source batch')
        require({k: m[k] for k in COMMON} == common and tuple(m['conditions']) == conditions, 'Source version mismatch')
        require(s['completed_units'] == s['expected_units'] == len(batch) == len(conditions), 'Incomplete source batch')
        require([key(r) for r in batch] == [key(r) for r in m['schedule']], 'Source schedule mismatch')
        require(len({(r['seed'], r['task_id']) for r in batch}) == 1 and
                {r['condition'] for r in batch} == set(conditions), 'Invalid batch pairing')
        require(all(r['first_attempt_matches'] for r in batch) and
                len({r['first_attempt_sha256'] for r in batch}) == 1, 'First-attempt mismatch')
        for task, checksum in m['game_sha256'].items():
            require(task in tasks and games.setdefault(task, checksum) == checksum, 'Task data changed between seeds')
        for row in batch:
            require(key(row) not in shard_rows, 'Duplicate source unit')
            shard_rows[key(row)] = row
        hashes = baseline_trace_hashes(shard / 'trace.jsonl')
        require(set(hashes) == {key(r) for r in batch if r['condition'] in ('A', 'B')}, 'Incomplete baseline traces')
        require(not (traces.keys() & hashes.keys()), 'Duplicate baseline traces')
        traces.update(hashes)
        job = read_json(Path(str(shard) + '-job') / 'job.json')
        require(job['exit_code'] == 0 and job['unischeduler_job_id'] == source['unischeduler_job_id'], 'Failed or mismatched GPU job')
        allocations.append({'job_id': job['unischeduler_job_id'], 'wrapper_seconds': job['wrapper_seconds']})
    require(shard_rows == rows, 'Merged rows differ from source batches')
    for name in COST_KEYS:
        total = sum(r['cost'][name] for r in raw)
        require(math.isclose(total, summary['all_cost_including_incomplete'][name], abs_tol=1e-6), 'Cost total mismatch')
    require(set(games) == set(tasks), 'Missing task data hashes')
    return {'path': str(path.resolve()), 'manifest': manifest, 'rows': rows, 'traces': traces, 'game_sha256': games,
            'allocations': allocations, 'cost': summary['all_cost_including_incomplete'],
            'manifest_sha256': digest(path / 'manifest.json'), 'results_sha256': digest(path / 'task_results.jsonl')}


def metrics(rows):
    rows = list(rows)
    first = sum(r['attempts'][0] for r in rows)
    success = sum(any(r['attempts']) for r in rows)
    return {'units': len(rows), 'successes': success, 'success_rate': success / len(rows),
            'first_successes': first, 'initial_failures': len(rows) - first,
            'recovered': success - first,
            **{k: sum(r['cost'][k] for r in rows) for k in COST_KEYS}}


def compare_campaigns(old_path, new_path, registry_path):
    registry = read_json(registry_path)
    tasks = registry['development']
    require(len(tasks) == len(set(tasks)) == 10 and not set(tasks) & set(registry['held_out']), 'Invalid development registry')
    old, new = [load_campaign(p, c, tasks) for p, c in zip((old_path, new_path), COHORTS)]
    require(all(old['manifest'][k] == new['manifest'][k] for k in COMMON), 'Campaign version mismatch')
    require(old['game_sha256'] == new['game_sha256'], 'Task data changed between campaigns')
    require(old['traces'] == new['traces'], 'Repeated A/B behavior changed; do not combine rankings')
    duplicates = old['rows'].keys() & new['rows'].keys()
    require(len(duplicates) == 40 and all(k[2] in ('A', 'B') for k in duplicates), 'Unexpected overlap')
    for k in duplicates:
        a, b = old['rows'][k], new['rows'][k]
        require(a['attempts'] == b['attempts'] and a['first_attempt_sha256'] == b['first_attempt_sha256'] and
                all(a['cost'][c] == b['cost'][c] for c in COST_KEYS if c != 'inference_seconds'), 'Repeated A/B results changed')
    # Original A/B are the fixed display reference, never selected by later scores.
    combined = {**new['rows'], **old['rows']}
    require(len(combined) == 140, 'Expected 140 unique seven-condition units')
    results = {}
    for condition in CONDITIONS:
        cohort = old if condition in COHORTS[0] else new
        rows = [combined[(seed, task, condition)] for seed in SEEDS for task in tasks]
        value = metrics(rows)
        value['cohort'] = cohort['path']
        value['per_seed'] = {str(seed): metrics(r for r in rows if r['seed'] == seed) for seed in SEEDS}
        value['paired'] = {}
        for baseline in ('A', 'B'):
            per_seed = {}
            for seed in SEEDS:
                wins, losses = [], []
                for task in tasks:
                    actual = any(combined[(seed, task, condition)]['attempts'])
                    reference = any(cohort['rows'][(seed, task, baseline)]['attempts'])
                    if actual and not reference:
                        wins.append(task)
                    if reference and not actual:
                        losses.append(task)
                per_seed[str(seed)] = {'wins': wins, 'losses': losses, 'net': len(wins) - len(losses)}
            value['paired'][baseline] = per_seed
        b_cost = metrics(r for r in cohort['rows'].values() if r['condition'] == 'B')
        value['cost_change_vs_same_cohort_B_pct'] = {k: (value[k] / b_cost[k] - 1) * 100 for k in COST_KEYS}
        value['both_seeds_net_positive_vs_B'] = all(x['net'] > 0 for x in value['paired']['B'].values())
        results[condition] = value
    all_rows = [combined[(s, t, c)] for s in SEEDS for t in tasks for c in CONDITIONS]
    report = {'status': 'complete', 'unique_tasks': 10, 'seeds': list(SEEDS), 'unique_units': 140,
              'actual_units': 180, 'repeated_baseline_units_verified': 40, 'held_out_units': 0,
              'git_commit': old['manifest']['git_commit'], 'conditions': results,
              'baseline_repeats': {label: {c: metrics(r for r in cohort['rows'].values() if r['condition'] == c)
                                          for c in ('A', 'B')} for label, cohort in [('original', old), ('repeat', new)]},
              'actual_cost_including_repeated_baselines': {k: old['cost'][k] + new['cost'][k] for k in COST_KEYS},
              'wrapper_seconds_including_repeated_baselines': sum(j['wrapper_seconds'] for c in (old, new) for j in c['allocations']),
              'sources': [{k: c[k] for k in ('path', 'manifest_sha256', 'results_sha256', 'allocations')} for c in (old, new)],
              'note': 'Development screening only: 10 distinct tasks, not 20 independent tasks. '
                      'Original A/B are displayed once; each candidate cost delta uses its own cohort B. '
                      'All 180 actual units count toward cost. Smoke/debug runs are separate. '
                      'The two-seed positive-net rule is a screening heuristic, not statistical significance.'}
    return report, all_rows


def markdown(report):
    lines = ['# 五个反思方案：开发集完整比较', '',
             '10 道开发题、两个固定种子；30 道留出题未参与。两轮 40 个重复 A/B 单元的完整行为记录已核对一致。',
             '统一表为 140 个唯一单元，实际运行与成本按 180 个单元计算。首次成功后停止，累计成功指三次内成功。', '',
             '| 组别 | 4051 | 4052 | 平均成功率 | 相对同轮 B 配对净成功（4051 / 4052） |',
             '| --- | ---: | ---: | ---: | ---: |']
    for c, value in report['conditions'].items():
        seeds = value['per_seed']; paired = value['paired']['B']
        lines.append(f"| {c} | {seeds['4051']['successes']}/10 | {seeds['4052']['successes']}/10 | {value['success_rate']:.0%} | {paired['4051']['net']:+d} / {paired['4052']['net']:+d} |")
    lines += ['', '| 组别 | 调用数 | 输入 token | 输出 token | 推理秒 | 相对同轮 B 推理时间变化 |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for c, value in report['conditions'].items():
        lines.append(f"| {c} | {value['model_calls']} | {value['input_tokens']} | {value['output_tokens']} | {value['inference_seconds']:.2f} | {value['cost_change_vs_same_cohort_B_pct']['inference_seconds']:+.1f}% |")
    lines += ['', 'S1/S4 的成本变化对照第一轮 B，S2/S3/S5 对照补跑 B；重复对照的原始成本保存在 comparison.json。',
              f"40 个 GPU 作业的 wrapper 时间合计 {report['wrapper_seconds_including_repeated_baselines'] / 60:.2f} 分钟，含启动清理。此为 MIG 实例运行时间，不等同于实际计费或完整 GPU 卡时；冒烟与调试另计。", '',
              '两种子都净多成功至少一题是预先约定的开发筛选门槛，不代表统计显著或泛化成立。完整逐题记录见 task_results.jsonl，仍需人工结合改善与退步轨迹解释结果。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--remaining', required=True, type=Path)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists; refusing overwrite')
    report, rows = compare_campaigns(args.original, args.remaining, args.registry)
    report['analysis_script_sha256'] = digest(__file__)
    args.output.mkdir(parents=True)
    (args.output / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'task_results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    (args.output / 'report.md').write_text(markdown(report), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'unique_units': 140, 'actual_units': 180, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
