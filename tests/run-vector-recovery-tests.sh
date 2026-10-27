#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-3.0-or-later
set -euo pipefail

task_inet_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$task_inet_root"
for task_tool in opp_makemake opp_test python3; do
    command -v "$task_tool" >/dev/null || { echo "Source an OMNeT++ 6.4 or newer environment first." >&2; exit 1; }
done
set +u
source ./setenv -q
set -u
task_jobs=${VRA_BUILD_JOBS:-4}
task_logs="$task_inet_root/tests/vector-recovery-results"
mkdir -p "$task_logs"

# Current INET's standard runners use the dependencies declared in this checkout.
if ! python3 -c 'import requests, dask, distributed, IPython, optimparallel, sewar, py4j' \
        2> "$task_logs/python-dependencies.log"; then
    cat "$task_logs/python-dependencies.log" >&2
    echo 'Install python/requirements.txt in a virtual environment created with --system-site-packages.' >&2
    echo 'Keep the existing OMNeT++ environment active when creating and using that environment.' >&2
    exit 2
fi

# Record the tested source content even while the contribution is uncommitted.
python3 - <<'PY' > "$task_logs/source-manifest.json"
import hashlib, json, subprocess
from pathlib import Path
paths = sorted(set(Path('src/inet/protocolelement/redundancy').glob('Vector*')) |
               set(Path('tests/unit').glob('VectorSequenceRecovery_*.test')) |
               set(Path('tests/module').glob('VectorStreamMerger_*.test')) |
               set(Path('tests/protocol/frer').glob('*')) |
               {Path('tests/run-vector-recovery-tests.sh'), Path('tests/check-vector-recovery-network.py'),
                Path('showcases/tsn/framereplication/vectorrecovery/omnetpp.ini')})
print(json.dumps({'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and not p.name.startswith('._')}}, indent=2))
PY

# Use the normal category selectors, and reject an empty or incomplete selection.
python3 - <<'PY' | tee "$task_logs/selection.log"
from inet.project.inet import inet_project
from inet.test.all import get_unit_test_tasks, get_module_test_tasks, get_protocol_test_tasks

def leaves(tasks):
    if hasattr(tasks, 'tasks'):
        return [leaf for child in tasks.tasks for leaf in leaves(child)]
    return [tasks]

for getter, selector, expected in [
    (get_unit_test_tasks, dict(filter=r'VectorSequenceRecovery_.*\.test$'), 2),
    (get_module_test_tasks, dict(filter=r'VectorStreamMerger_.*\.test$'), 11),
    (get_protocol_test_tasks, dict(working_directory_filter=r'^tests/protocol/frer$', filter=r'VectorRecovery.*\.test$'), 8),
]:
    selected = leaves(getter(simulation_project=inet_project, mode='debug', build=False, concurrent=False, **selector))
    assert len(selected) == expected, (getter.__name__, len(selected), expected)
    print(getter.__name__, len(selected))
    for test in selected:
        print(' ', test.test_file_name)
PY

for task_mode in debug release; do
    make -j"$task_jobs" MODE="$task_mode" 2>&1 | tee "$task_logs/build-$task_mode.log"
    # --no-build below skips category support-library builds too, so build them explicitly.
    for task_library in tests/unit/lib tests/module/lib tests/protocol/lib; do
        task_library_name=${task_library#tests/}
        task_library_name=${task_library_name%/lib}
        make -C "$task_library" -j"$task_jobs" MODE="$task_mode" 2>&1 | tee "$task_logs/build-$task_library_name-support-$task_mode.log"
    done
    inet_run_unit_tests -p inet -m "$task_mode" --no-build --no-concurrent \
        -f 'VectorSequenceRecovery_.*\.test$' 2>&1 | tee "$task_logs/unit-$task_mode.log"
    inet_run_module_tests -p inet -m "$task_mode" --no-build --no-concurrent \
        -f 'VectorStreamMerger_.*\.test$' 2>&1 | tee "$task_logs/module-$task_mode.log"
    inet_run_protocol_tests -p inet -m "$task_mode" --no-build --no-concurrent \
        -w '^tests/protocol/frer$' -f 'VectorRecovery.*\.test$' 2>&1 | tee "$task_logs/protocol-$task_mode.log"

    for task_config in VectorRecovery MinimumHistory RepeatedFailures Wraparound; do
        task_result_dir="$task_logs/network-$task_config-$task_mode"
        (
            cd "$task_inet_root/showcases/tsn/framereplication/vectorrecovery"
            MODE="$task_mode" inet -u Cmdenv -n ../../../../src:../../.. -c "$task_config" --result-dir="$task_result_dir"
        ) 2>&1 | tee "$task_logs/network-$task_config-$task_mode.log"
        python3 tests/check-vector-recovery-network.py "$task_config" "$task_result_dir" --require-signal-statistics \
            2>&1 | tee "$task_logs/check-$task_config-$task_mode.log"
    done

    # Existing baselines remain untouched. Exclude graphical fingerprints as advised by
    # the existing fingerprinttest wrapper; check all other ingredients for five FRER runs.
    (
        cd "$task_inet_root/tests/fingerprint"
        MODE="$task_mode" inet_fingerprinttest showcases.csv --directory "$task_inet_root" \
            --executable "$task_inet_root/bin/inet" --match '/showcases/tsn/framereplication/' \
            --excludefpfilter tyf --threads "$task_jobs" --logfile "$task_logs/fingerprint-details-$task_mode.log"
    ) 2>&1 | tee "$task_logs/fingerprint-$task_mode.log"
done

# A successful CLI exit is not enough if cases were skipped or sources changed mid-run.
python3 - <<'PY'
import hashlib, json, re
from pathlib import Path
logs = Path('tests/vector-recovery-results')
manifest = json.loads((logs / 'source-manifest.json').read_text())
for path, expected in manifest['sha256'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, 'Source changed during run: ' + path
for mode in ('debug', 'release'):
    for suite in ('unit', 'module', 'protocol'):
        text = re.sub(r'\x1b\[[0-9;]*m', '', (logs / f'{suite}-{mode}.log').read_text())
        assert not re.search(r'\b[1-9][0-9]* (SKIP|CANCEL|FAIL|ERROR)\b', text), suite + ' has nonpassing results'
        assert re.search(r'\b[1-9][0-9]* PASS\b', text), suite + ' has no PASS evidence'
print('Source manifest matches the completed run; normal category runners report passing cases.')
PY
echo "VRA debug/release builds, 42 focused tests, eight network runs and existing FRER fingerprint regressions passed. Logs: $task_logs"
