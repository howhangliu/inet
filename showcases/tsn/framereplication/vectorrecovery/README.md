# Vector recovery for FRER

This configuration reuses the manual FRER topology and its switch failure/recovery
scenario, selecting `VectorStreamMerger` at merge points. Run it from this directory
after building INET and sourcing the OMNeT++ and INET environments:

```sh
inet_dbg -u Cmdenv -n ../../../../src:../../.. -c VectorRecovery
```

In the OMNeT++ IDE, build INET in debug mode, open this
directory's `omnetpp.ini`, and choose **Run As > OMNeT++ Simulation** with the
**VectorRecovery** configuration. Select **Qtenv** for an interactive run or
**Cmdenv** for a console run. The source sends a frame every millisecond; switch
`s2a` fails at 20ms and restarts at 80ms. Recovery scalar counters are recorded
on each merger and can be inspected in the result files after the run.

The same INI file includes additional configurations:

| Configuration | Check |
| --- | --- |
| `MinimumHistory` | The minimum supported two-bit history, including switch failure |
| `RepeatedFailures` | Two outages (20..35 ms and 50..75 ms) with recovery resets |
| `Wraparound` | 70000 small frames over 7 seconds, crossing the 16-bit sequence wrap |

The wraparound run records only source production and destination packet-lifetime
vectors to limit result-file size. The focused test runner executes each configuration
in debug and release modes and checks accounting and unique payload creation
times automatically. It writes to separate test result directories, preserving
results from interactive IDE runs.

For another network, keep its existing stream mappings and select the module:

```ini
*.*.hasStreamRedundancy = true
*.*.bridging.streamRelay.merger.typename = "VectorStreamMerger"
*.*.bridging.streamRelay.merger.historyLength = 32
*.*.bridging.streamRelay.merger.resetTimeout = 100ms
```

Inputs sharing a recovery instance must share a sequence generator. By default,
the output stream name identifies that instance. For independently numbered flows
whose final output names are all empty (tag removal), set `recoveryMapping` to
assign separate instance names, for example `{a1: "flow1", b1: "flow1", a2:
"flow2", b2: "flow2"}`. Set history length
to cover path-delay differences and expected sequence gaps; arrivals at a signed
difference `delta > historyLength` or `delta <= -historyLength` are rejected. Accepted frames are
forwarded immediately and may be out of order. Configure the reset timeout for
the stream's silence and restart behavior; reset permits a delayed duplicate to
be accepted as the next initial frame.

`VectorSequenceRecovery` is the reusable C++ state class. It provides a pure
`classify()` query, a `process()` operation returning the decision and loss count,
and `reset()`. Its caller owns timers and packet handling. The module supplies
these, tagless handling, individual-recovery mode, and aggregate scalar counters.

The scope is the IEEE 802.1CB-2017 VRA functions (7.4.3.2-7.4.3.4 and
7.4.3.6), with the IEEE 802.1CBdb-2021 forward-boundary correction (item 0257).
The 2017 initialization-related loss counting is retained. Other amendment requirements, latent error detection, MRA and full management tables are not
implemented. Full FRER conformance is not claimed.

Recovery counters are cumulative signals with NED `last` statistics. Scalar
result names have a `:last` suffix; vector recording can be enabled with normal
OMNeT++ result-recording configuration.

Focused validation is available in `tests/unit/VectorSequenceRecovery_*.test` and
`tests/module/VectorStreamMerger_*.test`. Run `tests/run-vector-recovery-tests.sh`
from a configured OMNeT++ environment to build both modes and run the normal
unit/module/protocol runners, four network scenarios and existing FRER fingerprint
regressions. See `tests/VectorRecoveryValidation.md` for selection and scope.
The simulator-free core tests can also run natively with
`python3 tests/run-vector-recovery-core-tests.py --sanitize`.
