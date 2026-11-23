"""Validate complete short jobs before producing one paired screening summary."""
import argparse
import json
from pathlib import Path

try:
    from scripts import run_experiment as experiment
except ModuleNotFoundError:
    import run_experiment as experiment


def unit_key(row):
    return row['seed'], row['task_id'], row['condition']


def merge_runs(paths, output):
    protocol, config, tasks, instructions, games, _ = experiment.load_inputs()
    reference, sources, rows, costs = None, [], {}, dict.fromkeys(experiment.COST_KEYS, 0)
    common_fields = ('git_commit', 'protocol', 'protocol_sha256', 'config', 'instructions',
                     'python', 'alfworld', 'textworld', 'source_sha256', 'conditions', 'runtime_sha256', 'gpu_type_driver')
    for path in paths:
        path = Path(path)
        manifest = json.loads((path / 'manifest.json').read_bytes())
        summary = json.loads((path / 'summary.json').read_bytes())
        batch = [json.loads(line) for line in (path / 'task_results.jsonl').read_text().splitlines()]
        if manifest['mode'] != 'shard' or summary['status'] != 'complete' or manifest['git_dirty']:
            raise ValueError(f'Only complete, clean shard runs can be merged: {path}')
        common = {key: manifest[key] for key in common_fields}
        if reference is None:
            reference = common
        if common != reference or manifest['protocol'] != protocol or manifest['config'] != config or manifest['instructions'] != instructions:
            raise ValueError(f'Incompatible source/configuration/prompt versions: {path}')
        index = manifest['task_index']
        if type(index) is not int or not 0 <= index < len(tasks) or not batch:
            raise ValueError(f'Invalid shard task index or empty results: {path}')
        seed = batch[0]['seed']
        schedule = experiment.make_schedule([tasks[index]], [seed], manifest['conditions'], task_offset=index)
        if manifest['schedule'] != schedule or [unit_key(row) for row in batch] != [unit_key(row) for row in schedule]:
            raise ValueError(f'Incomplete or reordered shard: {path}')
        if summary['completed_units'] != len(schedule) or summary['expected_units'] != len(schedule):
            raise ValueError(f'Invalid shard completion counts: {path}')
        expected_game = {tasks[index]: experiment.sha256(games[tasks[index]].read_bytes())}
        if manifest['game_sha256'] != expected_game:
            raise ValueError(f'Task data differs from frozen input: {path}')
        if not all(row['first_attempt_matches'] for row in batch) or len({row['first_attempt_sha256'] for row in batch}) != 1:
            raise ValueError(f'First-attempt audit failed: {path}')
        for row in batch:
            key = unit_key(row)
            if key in rows:
                raise ValueError(f'Duplicate unit: {key}')
            rows[key] = row
        for key in costs:
            costs[key] += summary['all_cost_including_incomplete'][key]
        sources.append({'path': str(path.resolve()), 'run_id': manifest['run_id'],
                        'unischeduler_job_id': manifest['unischeduler_job_id'],
                        'manifest_sha256': experiment.sha256((path / 'manifest.json').read_bytes()),
                        'results_sha256': experiment.sha256((path / 'task_results.jsonl').read_bytes())})
    if reference is None:
        raise ValueError('No shard runs supplied')
    conditions = reference['conditions']
    expected = experiment.make_schedule(tasks, experiment.SEEDS, conditions)
    if set(rows) != {unit_key(row) for row in expected}:
        raise ValueError(f'Missing units: expected {len(expected)}, found {len(rows)}')
    ordered = [rows[unit_key(row)] for row in expected]
    summary = experiment.summarize(ordered, experiment.SEEDS, len(tasks), conditions)
    summary.update(status='complete', mode='merged-screening', conditions=conditions,
                   completed_units=len(ordered), expected_units=len(expected),
                   full_two_seed_screening=not experiment.SUPPLEMENTARY and tuple(conditions) == experiment.CONDITIONS,
                   experiment_label='supplementary-development' if experiment.SUPPLEMENTARY else 'original-development',
                   all_cost_including_incomplete=costs,
                   note='Complete for the listed conditions only. Smoke and other candidates are excluded. '
                        'Allocation cost and failed runs must be reported separately from scheduler records.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    experiment.write_json(output / 'manifest.json', {**reference, 'mode': 'merged-screening', 'sources': sources})
    experiment.write_json(output / 'summary.json', summary)
    (output / 'task_results.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in ordered), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('runs', nargs='+', type=Path)
    args = parser.parse_args()
    summary = merge_runs(args.runs, args.output)
    print(json.dumps({'status': summary['status'], 'conditions': summary['conditions'],
                      'units': summary['completed_units'], 'output': str(args.output)}, indent=2))


if __name__ == '__main__':
    main()
