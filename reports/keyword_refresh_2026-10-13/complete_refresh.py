"""Finish the frozen October 13 rebuild, validate it, then replace the local snapshot.

The Ward producer is already running as PID 13476. This worker never substitutes
an older tree, and preserves a recoverable copy of the previously installed data.
"""
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
HEIGHTS = (0.5, 0.75, 1.0, 1.25, 1.5)
PRODUCER_PID = 13476
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
                 producer_pid=PRODUCER_PID, keywords=173438, mentions=313858,
                 partial_years=[2021], **details)
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(STATE)
    print(stage, flush=True)


def producer_alive():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, PRODUCER_PID)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError('Cannot inspect clustering worker status')
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)


def run(stage, arguments, env):
    status(stage)
    with (JOB / f'{stage}.log').open('w', encoding='utf-8') as log:
        subprocess.run([sys.executable, '-u', *arguments], cwd=ROOT, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    if STATE.exists() and json.loads(STATE.read_text())['stage'] == 'complete':
        return
    fingerprint = digest(AGGREGATE)
    status('waiting_for_ward', aggregate_sha256=fingerprint)
    deadline = time.monotonic() + 24 * 3600
    while True:
        paths = [CLUSTERS / f'clusters_dt{height}.json' for height in HEIGHTS]
        if all(path.exists() for path in paths):
            for path in paths:
                meta = json.loads(path.read_text(encoding='utf-8'))['meta']
                if meta['aggregate_sha256'] != fingerprint or meta['num_keywords'] != 173438:
                    raise ValueError(f'Unexpected clustering snapshot: {path}')
            break
        if not producer_alive():
            raise RuntimeError('Ward producer stopped before all five cuts were written; inspect clustering.log')
        if time.monotonic() > deadline:
            raise TimeoutError('Ward did not produce all cuts within 24 hours')
        time.sleep(30)

    env = dict(os.environ, HF_HUB_OFFLINE='1', AICHE_INDEX_DIR=str(INDEX))
    run('preparing_indices', ['05_webapp/prepare_indices.py', '--aggregate', str(AGGREGATE),
        '--clusters-dir', str(CLUSTERS), '--output-dir', str(INDEX)], env)
    manifest = json.loads((JOB / 'input_manifest.json').read_text(encoding='utf-8'))
    (INDEX / 'data_coverage.json').write_text(json.dumps(dict(
        snapshot_date='2026-10-13', aggregate_sha256=fingerprint,
        extraction_records_by_year=manifest['years'], partial_years=[2021],
        note='2021 includes 90 completed extraction files; later outputs are outside this frozen rebuild.'
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
    summary = dict(aggregate_sha256=fingerprint, keywords=173438, added_keywords=58971,
                   mentions=313858, years=sorted(manifest['years']), themes_by_height=themes,
                   institutions=institution_meta, partial_years=[2021],
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
