#!/usr/bin/env python3
"""Check VRA network scalar accounting and payload creation-time delivery."""
import argparse
from collections import Counter
from decimal import Decimal
import json
import math
from pathlib import Path
import shlex

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("configuration", choices=["VectorRecovery", "MinimumHistory", "RepeatedFailures", "Wraparound"])
parser.add_argument("result_directory", type=Path)
parser.add_argument("--require-signal-statistics", action="store_true",
                    help="Require the current module's NED last-value counter statistics")
args = parser.parse_args()
files = list(args.result_directory.glob(args.configuration + "-*.sca"))
if len(files) != 1:
    parser.error("Expected one scalar result for configuration " + args.configuration)
sca = files[0]
vec = sca.with_suffix(".vec")
scalars = {}
histograms = {}
current = None
run_id = None
for line in sca.open():
    if line.startswith("run "):
        run_id = line.split()[1]
    elif line.startswith("scalar "):
        _, module, name, value = shlex.split(line)
        scalars[(module, name)] = float(value)
        current = None
    elif line.startswith("statistic "):
        _, module, name = shlex.split(line)
        current = (module, name)
        histograms[current] = {}
    elif line.startswith("field ") and current is not None:
        _, name, value = line.split()
        histograms[current][name] = float(value)

root = "ManualConfigurationShowcase"
def scalar(module, name):
    key = (root + "." + module, name)
    # Accept old direct scalars when inspecting historical result files.
    return scalars[key] if key in scalars else scalars[(key[0], name + ":last")]
def check(condition, message):
    if not condition:
        raise RuntimeError(message)

expected = 70000 if args.configuration == "Wraparound" else 100
period = Decimal("0.0001") if args.configuration == "Wraparound" else Decimal("0.001")
duplicates = {"VectorRecovery": 40, "MinimumHistory": 40, "RepeatedFailures": 60, "Wraparound": 69400}[args.configuration]
failed_branch_losses = {"VectorRecovery": 38, "MinimumHistory": 2, "RepeatedFailures": 57, "Wraparound": 62}[args.configuration]
steady_losses = 1 if args.configuration == "MinimumHistory" else 31
failed_branch_resets = 3 if args.configuration == "RepeatedFailures" else 2
generated = int(scalar("source.app[0].source", "packets:count"))
delivered = int(scalar("destination.app[0].sink", "packets:count"))
check(generated in (expected, expected + 1), "Unexpected source production count")
check(delivered == expected, "Application frame loss or duplicate delivery")
for node, passed, discarded, lost, resets in [
    ("destination", expected, duplicates, steady_losses, 1),
    ("s2b", expected, duplicates, steady_losses, 1),
    ("s2a", duplicates, duplicates, failed_branch_losses, failed_branch_resets),
]:
    module = node + ".bridging.streamRelay.merger"
    for suffix, value in [("PassedPackets", passed), ("DiscardedPackets", discarded),
                          ("RoguePackets", 0), ("OutOfOrderPackets", 0),
                          ("TaglessPackets", 0), ("LostPackets", lost), ("Resets", resets)]:
        if args.require_signal_statistics:
            check((root + "." + module, "recovery" + suffix + ":last") in scalars,
                  "Missing declared last-value statistic for " + module + " recovery" + suffix)
        observed = scalar(module, "recovery" + suffix)
        check(observed == value, f"{node} recovery{suffix}: expected {value}, got {observed}")

life = histograms[(root + ".destination.app[0].sink", "packetLifeTime:histogram")]
check(life["count"] == expected, "Missing finite application lifetime measurements")
check(math.isfinite(life["min"]) and life["min"] > 0, "Invalid application delay")
check(abs(life["max"] - life["min"]) <= 1e-12, "Unexpected delay variation in equal-path network")

source_id = None
destination_id = None
produced = []
creation_times = []
vector_run = None
for line in vec.open():
    if line.startswith("run "):
        vector_run = line.split()[1]
    elif line.startswith("vector "):
        parts = shlex.split(line)
        if parts[2:] == [root + ".source.app[0].source", "packetLengths:vector", "ETV"]:
            source_id = parts[1]
        elif parts[2:] == [root + ".destination.app[0].sink", "packetLifeTime:vector", "ETV"]:
            destination_id = parts[1]
    elif line[:1].isdigit():
        index, event, timestamp, value = line.split()
        if index == source_id:
            produced.append(Decimal(timestamp))
        elif index == destination_id:
            creation_times.append(Decimal(timestamp) - Decimal(value))
check(vector_run == run_id, "Scalar and vector run identifiers differ")
check(len(produced) == generated, "Missing source production vector")
check(len(creation_times) == expected, "Missing application creation-time evidence")
actual = Counter(creation_times)
check(all(count == 1 for count in actual.values()), "Duplicate payload creation times delivered")
required = {period * i for i in range(expected)}
check(set(actual) == required, "One or more expected source frames are missing")
check(required.issubset(set(produced)), "Delivered payloads do not match source production")
print(json.dumps({"configuration": args.configuration, "run": run_id,
                  "generated": generated, "delivered_once": len(actual),
                  "destination_duplicates_eliminated": duplicates,
                  "delay_microseconds": life["mean"] * 1e6,
                  "sequence_wrap_exercised": expected > 65536, "result": "PASS"}, indent=2))
