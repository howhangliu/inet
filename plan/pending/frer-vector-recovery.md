# Add configurable vector sequence recovery

> **Kind:** procedure · **Status:** draft · **Seal:** none · **Owns:** — · **Stands on:** [contribution workflow](../../doc/project/guide/contribute-a-change.md)

## Scope

The change adds a packet-independent recovery helper and a selectable stream merger. It preserves the existing StreamMerger and its defaults. Numbered recovery follows IEEE 802.1CB-2017, 7.4.3.2-.4 and .6, with the forward-window correction published in IEEE 802.1CBdb-2021 (maintenance item 0257). Packet/timer integration includes tagless handling and individual recovery. Latent error detection, management tables and full amendment conformance are not claimed.

## Commit series

### VRA-1 — `redundancy: add: vector sequence recovery state`

Purpose: provide reusable sequence-position history, signed modular classification, reset and batched history advancement. No packet interface changes in this commit. Files: VectorSequenceRecovery.h/.cc, tests/unit/VectorSequenceRecovery_1.test and _2.test, the helper release note and this plan. There is no dependency. The computation API is tested with exhaustive classifications, explicit boundaries, an independent received-number oracle and wraparound. Protocol tests do not apply to this standalone computation; the production packet path is introduced in VRA-2. Build INET in debug/release and run `inet_run_unit_tests -p inet -m debug -f 'VectorSequenceRecovery_.*\.test$' --no-build --no-concurrent`, repeating in release. Native sanitizer checks supplement these tests.

### VRA-2 — `redundancy: add: configurable vector stream merger`

Depends on VRA-1. Files: VectorStreamMerger.h/.cc/.ned, tests/module/VectorStreamMerger_*.test, tests/protocol/frer/VectorRecovery*.test, FrameSource.h, vector-recovery.md and a release note. The old merger's membership list does not implement the required acceptance window or recovery timeout. With H=5 and reference 102, unseen 107 must pass, 108 must be rogue, and an already seen position must not pass again. With reset period 10ms, accepted frame at 1ms and duplicate at 9ms, a new start at 11ms must pass in ordinary recovery. Individual recovery must instead reload on numbered drops. Relevant clauses: 7.4.3.4, 7.5, 10.4.1.7/.9/.10; accepted window correction item 0257.

The packet commit hook updates recovery once, before tag changes. Cumulative signals and NED last-value statistics publish aggregate counters, with no direct recordScalar calls. Explicit frame stimuli enter the production merger gate; the existing protocol observer checks every input stimulus and the exact output sequence, tags, times and cardinality. No recovery algorithm is reproduced in the protocol fixture. Existing tests do not cover this missing module; the two unit and eleven module fixtures are additional evidence. Add eight protocol cases for window decisions, wraparound, ordinary timeout, individual timeout, tagless acceptance/rejection, tick rounding and group isolation. Details, before/after behavior and diagrams belong in tests/protocol/frer/vector-recovery.md, associated with VRA-2. Normal selectors: `inet_run_module_tests -p inet -m debug -f 'VectorStreamMerger_.*\.test$' --no-build --no-concurrent` and `inet_run_protocol_tests -p inet -m debug -w '^tests/protocol/frer$' -f 'VectorRecovery.*\.test$' --no-build --no-concurrent`, repeating in release after fresh matching libraries. Run existing framereplication fingerprints without changing their baselines.

### VRA-3 — `examples: add: vector recovery demonstration and validation`

Depends on VRA-2. Files: user-guide section, vectorrecovery showcase README/ini, test-runner and result-checker scripts, and a concise test coverage index. This commit adds configuration examples and repeatable commands; it introduces no additional protocol behavior, so the VRA-2 protocol document covers the production behavior. Run four showcase configurations in both modes; independently compare scalar/vector run IDs, every delivered source creation time, delay and recovery counters. Run shell syntax/Python syntax checks and the repository documentation/series gates. Keep local logs, build output, IDE state and historical machine paths outside the submitted patch.

## Verification status

This plan defines the review boundaries and the checks; it does not declare future checks passed. Current results and unexecuted checks are recorded outside the submitted tree in the PR preparation report. Source changes require new matching INET builds before runtime tests. No recorded fingerprint baseline is changed.
