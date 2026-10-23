"""Rebuild portable, explicitly invented static writing regression artifacts.

Run after changing the bundled rules or publication sanitization. This uses the
real compute/export/import path and replays it again after path normalization;
it never changes production gates or claims to review fictional-canon evidence.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]

from rating_fixtures import with_executed_ratings
from rating_pipeline import HASH_FIELDS, _read, _write, file_hash, run, verify_execution


def portable(value):
    """Installation paths are transport metadata, never rule-byte identities."""
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, str):
        for prefix in (str(ROOT), ROOT.as_posix()):
            if value.startswith(prefix + '/') or value.startswith(prefix + '\\'):
                return 'SKILL_ROOT/' + value[len(prefix) + 1:].replace('\\', '/')
    return value


def rebuild(name):
    path = ROOT / 'assets/cases' / (name + '.json')
    request = _read(path)
    expected_kind = {
        'writing-battle-synthetic': 'synthetic_author_settings_not_character_evidence',
        'writing-fidelity-synthetic': 'invented_canon_profile_regression_not_real_character_evidence',
    }.get(name)
    if not expected_kind or request.get('fixture_kind') != expected_kind:
        raise ValueError('Only explicitly authored synthetic fixtures may be rebuilt')
    had_mode = 'mode' in request
    request.pop('rating_execution', None)
    directory = ROOT / 'assets/rating-fixtures' / name
    executed = with_executed_ratings(request, directory)
    artifacts = executed['rating_execution']['artifacts']
    for artifact in artifacts:
        out = ROOT / artifact['artifact_dir']
        for filename in ('analysis.json', 'rules-snapshot.json', 'manifest.json'):
            target = out / filename
            _write(target, portable(_read(target)))
        acceptance = _read(out / 'host-acceptance.json')
        if acceptance.get('fixture_kind') != 'explicit_authored_test_acceptance_not_canon':
            raise ValueError('Refusing to regenerate any real-canon host acceptance')
        acceptance.update({field: file_hash(out / filename)
                           for filename, field in HASH_FIELDS.items()})
        _write(out / 'host-acceptance.json', acceptance)
        manifest = _read(out / 'manifest.json')
        for filename in manifest['files']:
            target = out / filename
            manifest['files'][filename] = {'bytes': target.stat().st_size,
                                           'sha256': file_hash(target)}
        _write(out / 'manifest.json', manifest)
    # The production importer checks the normalized bytes and actually replays
    # their CASE analysis; new hashes alone are insufficient for admission.
    assembled = run({'operation': 'assemble', 'writing_request': executed,
        'artifacts': [{'character_id': row['character_id'], 'artifact_dir': row['artifact_dir']}
                      for row in artifacts]})
    if assembled['status'] != 'assembled':
        raise AssertionError(assembled.get('needs', assembled))
    rebuilt = assembled['writing_request']
    check = verify_execution(rebuilt)
    if check['status'] != 'ready' or check['semantic_rating_verified']:
        raise AssertionError(check)
    if not had_mode:
        rebuilt.pop('mode', None)  # Preserve explicit historical-replay tests.
    _write(path, rebuilt)
    return {'fixture': name, 'artifacts': len(artifacts),
            'status': 'real_analysis_replayed_and_portable',
            'semantic_rating_verified': False}


if __name__ == '__main__':
    results = [rebuild(name) for name in
               ('writing-battle-synthetic', 'writing-fidelity-synthetic')]
    print(json.dumps(results, ensure_ascii=False))
