# Vector recovery test coverage

The implementation supports IEEE 802.1CB-2017 base vector recovery with the IEEE 802.1CBdb-2021 forward-window correction (maintenance item 0257). Full FRER conformance is not claimed. The [protocol reviewer document](protocol/frer/vector-recovery.md) explains the requirements, fixtures, expected traces and limits; the [commit plan](../plan/pending/frer-vector-recovery.md) defines the submission boundaries.

| Layer | Files | Claim |
| --- | --- | --- |
| Unit | unit/VectorSequenceRecovery_1.test and _2.test | Sequence arithmetic, boundaries, reset, loss increments, independent set oracle, multiple wraps |
| Module | module/VectorStreamMerger_1.test through _11.test | Production push/pull path, timers, counters, tagless handling, mapping changes, streaming rejection and invalid configurations |
| Protocol | protocol/frer/VectorRecovery*.test | Exact production input/output traces for decisions, wraparound, timers, tagless policy, rounding and isolation |
| Network | ../showcases/tsn/framereplication/vectorrecovery/omnetpp.ini | Exactly-once delivery during outages and sequence-number wraparound |
| Regression | fingerprint/showcases.csv, existing framereplication entries | Existing non-graphical fingerprint baselines remain unchanged |

## Run the focused checks

Use an OMNeT++ 6.4 or newer environment with the INET Python requirements installed, source this checkout's setenv, then run from its root:

```sh
bash tests/run-vector-recovery-tests.sh
```

The script builds fresh INET and category support libraries, invokes INET's normal category runners, and validates four scenarios in debug and release. It selects exactly 2 unit, 11 module and 8 protocol fixtures per mode. It also runs the five existing FRER fingerprint scenarios, excluding graphical ingredients as advised by the repository's fingerprint wrapper. No recorded baseline is regenerated into the submitted source.

If an older environment lacks the current Python dependencies, create a virtual environment outside the checkout while the OMNeT++ environment is active:

```sh
python3 -m venv --system-site-packages "$HOME/.venvs/inet-vra"
source "$HOME/.venvs/inet-vra/bin/activate"
python3 -m pip install -r python/requirements.txt
```

The system-site-packages option preserves the OMNeT++ packages already supplied by that environment. Do not replace the toolchain or fake OPP_ENV_VERSION to bypass its setup checks.

Logs and result artifacts go to tests/vector-recovery-results. The source manifest identifies the revision and SHA-256 of the tested VRA inputs, including uncommitted changes. A source change during the run invalidates its final summary. Review exact selections, all nonpassing/skipped outcomes and the recorded source manifest before reporting success. User IDE runs are additional evidence, not a replacement for the selected suite.

Optional native core validation, using an available C++ compiler and OMNeT++ headers:

```sh
python3 tests/run-vector-recovery-core-tests.py --sanitize --omnetpp-root /path/to/omnetpp
```

This compiles the production helper with the same unit-test activities and ASan/UBSan. It supplies no module or network runtime evidence. Historical local logs and machine-specific notes are not part of the submitted patch.
