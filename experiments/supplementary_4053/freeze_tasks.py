"""Record prior exposure, then freeze a balanced, outcome-blind task sample."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

TAG = 'supplementary-development-4053-v1'
TRIAL = re.compile(rb'trial_T\d{8}_\d{6}_\d+')
TYPES = ('look_at_obj_in_light', 'pick_and_place_simple', 'pick_clean_then_place_in_recep',
         'pick_cool_then_place_in_recep', 'pick_heat_then_place_in_recep', 'pick_two_obj_and_place')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def audit(roots):
    sources, trials, count = [], set(), 0
    for root in map(Path, roots):
        for p in sorted(root.rglob('*')):
            if not p.is_file() or any(x in p.parts for x in ('.git', '.venv', '__pycache__', 'models', 'checkpoints')):
                continue
            # Dataset contents are the sampling universe, not evidence of use.
            if 'alfworld' in p.parts or p.suffix.lower() not in ('.md', '.py', '.json', '.jsonl', '.txt', '.log', '.csv', '.tsv', '.yaml'):
                continue
            data = p.read_bytes()
            count += 1
            found = sorted({x.decode() for x in TRIAL.findall(data)})
            if found:
                trials.update(found)
                sources.append({'path': str(p), 'sha256': digest(data), 'trials': found})
    return {'roots': list(map(str, roots)), 'scanned_text_files': count,
            'trial_ids': sorted(trials), 'sources': sources,
            'rule': 'Conservatively exclude every trial ID mentioned in project code/config/docs/prompts/logs/helpers; no outcome filtering.'}


def select(candidates, excluded):
    order = sorted(TYPES, key=lambda t: digest(f'{TAG}:type:{t}'.encode()))
    chosen = {}
    for index, kind in enumerate(order):
        pool = [t for t in candidates if t.split('/')[-2].split('-')[0] == kind and t.split('/')[-1] not in excluded]
        pool.sort(key=lambda t: digest(f'{TAG}:task:{t}'.encode()))
        quota = 4 if index < 2 else 3
        if len(pool) < quota:
            raise ValueError(f'Insufficient unused tasks: {kind}')
        chosen[kind] = pool[:quota]
    return [chosen[kind][i] for i in range(4) for kind in order if i < len(chosen[kind])]


def freeze(archive, original, audits, output):
    original = json.loads(Path(original).read_bytes())
    histories = [json.loads(Path(p).read_bytes()) for p in audits]
    excluded = {t.split('/')[-1] for t in original['development'] + original['held_out']}
    excluded.update(t for a in histories for t in a['trial_ids'])
    candidates, hashes = [], {}
    with ZipFile(archive) as z:
        for name in sorted(z.namelist()):
            if '/valid_seen/' not in name or not name.endswith('/game.tw-pddl'):
                continue
            data = z.read(name)
            if json.loads(data)['solvable']:
                task = name.removesuffix('/game.tw-pddl')
                candidates.append(task)
                hashes[task] = digest(data)
    tasks = select(candidates, excluded)
    registry = {'label': 'supplementary-development', 'selection_seed': 4053,
                'development': tasks, 'held_out': original['held_out'],
                'original_development': original['development'], 'excluded_trial_ids': sorted(excluded)}
    selection = {'rule': TAG, 'fixed_before_execution': True,
                 'algorithm': 'SHA256(tag:type:type_name) orders six types; first two get 4 tasks, others 3. Within each type sort SHA256(tag:task:canonical_task_id), select quota, interleave types. No outcome or walkthrough filtering.',
                 'archive_sha256': digest(Path(archive).read_bytes()), 'eligible_solvable_valid_seen': len(candidates),
                 'excluded_valid_seen': [t for t in candidates if t.split('/')[-1] in excluded],
                 'remaining_valid_seen': sum(t.split('/')[-1] not in excluded for t in candidates),
                 'quotas': dict(Counter(t.split('/')[-2].split('-')[0] for t in tasks)),
                 'tasks': tasks, 'game_sha256': {t: hashes[t] for t in tasks},
                 'audit_sha256': {Path(p).name: digest(Path(p).read_bytes()) for p in audits}}
    write(Path(output) / 'registry.json', registry)
    write(Path(output) / 'selection.json', selection)
    print(json.dumps({k: selection[k] for k in ('eligible_solvable_valid_seen', 'remaining_valid_seen', 'quotas')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='mode', required=True)
    a = subs.add_parser('audit'); a.add_argument('--roots', nargs='+', required=True); a.add_argument('--output', required=True)
    f = subs.add_parser('freeze'); f.add_argument('--archive', required=True); f.add_argument('--original', required=True)
    f.add_argument('--audits', nargs='+', required=True); f.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.mode == 'audit':
        result = audit(args.roots); write(args.output, result)
        print(json.dumps({'files': result['scanned_text_files'], 'exposed_trial_ids': len(result['trial_ids'])}))
    else:
        freeze(args.archive, args.original, args.audits, args.output)
