"""Build, verify and install the frozen November 4 keyword refresh."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

JOB = Path(__file__).resolve().parent
ROOT = JOB.parents[1]
AGGREGATE = JOB / 'aggregate.json'
CLUSTERS = JOB / 'clusters'
INDEX = JOB / 'index'
HEIGHTS = (0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
PRODUCER_PID = os.getpid()
SUMMARY = json.loads((JOB / "snapshot_summary.json").read_text())
STATE = JOB / 'refresh_status.json'
INDIA = timezone(timedelta(hours=5, minutes=30))


def inside_workspace(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f'Unsafe snapshot path: {path}')
    return path


def digest(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def status(stage, **details):
    value = dict(stage=stage, updated_at=datetime.now(INDIA).isoformat(),
                 producer_pid=PRODUCER_PID, keywords=SUMMARY['keywords'], mentions=SUMMARY['mentions'],
                 partial_years=[2017], **details)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(STATE)
    print(stage, flush=True)


def run(stage, arguments, env):
    status(stage)
    with (JOB / f'{stage}.log').open('w', encoding='utf-8') as log:
        subprocess.run([sys.executable, '-u', *arguments], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    if STATE.exists() and json.loads(STATE.read_text())['stage'] == 'complete':
        return
    fingerprint = digest(AGGREGATE)
    env = dict(os.environ, HF_HUB_OFFLINE='1', HF_HOME=str(ROOT / '.runtime/huggingface'), AICHE_INDEX_DIR=str(INDEX))
    if not (JOB / 'regression_passed.txt').exists():
        run('regression_tests', ['-m', 'unittest', 'discover', '-s', '05_webapp/tests', '-v'], env)
        (JOB / 'regression_passed.txt').write_text('Eight regression tests passed.\n')
    run('clustering', ['04_clustering/cluster_keywords.py', str(AGGREGATE), '--no-llm',
        '--output-dir', str(CLUSTERS), '--reuse-labels', '04_clustering/explorer_results',
        '--thresholds', *map(str, HEIGHTS)], env)
    run('preparing_indices', ['05_webapp/prepare_indices.py', '--aggregate', str(AGGREGATE),
        '--clusters-dir', str(CLUSTERS), '--output-dir', str(INDEX)], env)
    manifest = json.loads((JOB / 'input_manifest.json').read_text(encoding='utf-8'))
    (INDEX / 'data_coverage.json').write_text(json.dumps(dict(
        snapshot_date='2026-11-04', aggregate_sha256=fingerprint,
        extraction_records_by_year=manifest['years'], partial_years=[2017],
        note='2017 is a partial extraction. Wrongly filed 2022 duplicates were excluded from 2021.'
    ), indent=2), encoding='utf-8')
    run('verifying_indices', ['05_webapp/verify_indices.py'], env)
    run('verifying_institutions', ['05_webapp/verify_institutions.py', '--aggregate', str(AGGREGATE)], env)
    run('verifying_webapp', ['05_webapp/verify_app.py'], env)

    # Only publish if the installed aggregate is still the one this run started from.
    live_aggregate = inside_workspace(ROOT / '02_extraction/aggregate.json')
    if digest(live_aggregate) != digest(JOB / 'aggregate_before.json'):
        raise RuntimeError('Installed aggregate changed during rebuild; validated staged data retained for review')
    backup = inside_workspace(JOB / 'previous_snapshot')
    if backup.exists():
        raise RuntimeError('Previous publication backup already exists; inspect before rerunning')
    backup.mkdir()
    temp_aggregate = inside_workspace(ROOT / '02_extraction/aggregate.refresh.tmp')
    if temp_aggregate.exists():
        raise RuntimeError('Unexpected pending aggregate file')
    shutil.copy2(AGGREGATE, temp_aggregate)
    live_clusters = inside_workspace(ROOT / '04_clustering/explorer_results')
    live_index = inside_workspace(ROOT / '05_webapp/index')
    replacements = [(live_clusters, backup / 'explorer_results'), (CLUSTERS, live_clusters),
                    (live_index, backup / 'index'), (INDEX, live_index),
                    (live_aggregate, backup / 'aggregate.json'), (temp_aggregate, live_aggregate)]
    moved = []
    status('publishing_verified_snapshot', aggregate_sha256=fingerprint)
    try:
        for source, destination in replacements:
            source, destination = inside_workspace(source), inside_workspace(destination)
            if not source.exists() or destination.exists():
                raise ValueError(f'Publication precondition failed: {source} -> {destination}')
            os.replace(source, destination)
            moved.append((source, destination))
    except Exception:
        for source, destination in reversed(moved):
            os.replace(destination, source)
        raise

    themes = {str(height): json.loads((live_clusters / f'clusters_dt{height}.json').read_text(
        encoding='utf-8'))['meta']['num_clusters'] for height in HEIGHTS}
    institution_meta = json.loads((live_index / 'institution_meta.json').read_text(encoding='utf-8'))
    summary = dict(aggregate_sha256=fingerprint, keywords=SUMMARY['keywords'], added_keywords=SUMMARY['added_keywords'],
                   mentions=SUMMARY['mentions'], years=sorted(manifest['years']), themes_by_height=themes,
                   institutions=institution_meta, partial_years=[2017],
                   backup_directory=str(backup))
    (JOB / 'build_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    # Make the verified local demo available if port 8501 is not already in use.
    with socket.socket() as connection:
        connection.settimeout(2)
        running = connection.connect_ex(('127.0.0.1', 8501)) == 0
    webapp_pid = None
    if not running:
        web_env = dict(env)
        web_env.pop('AICHE_INDEX_DIR', None)
        with (JOB / 'webapp.log').open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run',
                '05_webapp/app.py', '--server.address', '127.0.0.1', '--server.port', '8501',
                '--server.headless', 'true', '--browser.gatherUsageStats', 'false'],
                cwd=ROOT, env=web_env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
            webapp_pid = process.pid
    status('complete', aggregate_sha256=fingerprint, themes_by_height=themes,
           backup_directory=str(backup), webapp_url='http://127.0.0.1:8501', webapp_pid=webapp_pid)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        status('failed', error=str(error), staged_snapshot_retained=True)
        raise
