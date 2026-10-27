#!/usr/bin/env python3
"""Run the actual recovery class and its simulator-free test activities natively."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--sanitize", action="store_true", help="Enable AddressSanitizer and UndefinedBehaviorSanitizer")
parser.add_argument("--omnetpp-root", type=Path, help="OMNeT++ installation containing include/omnetpp.h")
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
omnet = args.omnetpp_root
if omnet is None and os.environ.get("OMNETPP_ROOT"):
    omnet = Path(os.environ["OMNETPP_ROOT"])
if omnet is None:
    candidates = sorted(root.parent.glob("omnetpp-*/include/omnetpp.h"))
    if len(candidates) == 1:
        omnet = candidates[0].parent.parent
if omnet is None or not (omnet / "include/omnetpp.h").is_file():
    parser.error("Supply --omnetpp-root or source the OMNeT++ environment")
compiler = shlex.split(os.environ.get("CXX", shutil.which("clang++") or shutil.which("g++") or ""))
if not compiler:
    parser.error("No C++ compiler available")
output = root / "tests/vector-recovery-results"
output.mkdir(parents=True, exist_ok=True)
log = output / ("core-sanitized.log" if args.sanitize else "core-native.log")

def sections(path):
    result = {}
    current = None
    for line in path.read_text().splitlines(keepends=True):
        if line.startswith("%"):
            current = line.split(":", 1)[0][1:]
            result.setdefault(current, "")
        elif current is not None:
            result[current] += line
    return result

with log.open("w") as handle, tempfile.TemporaryDirectory(prefix="inet-vra-core-") as directory:
    for test in sorted((root / "tests/unit").glob("VectorSequenceRecovery_*.test")):
        bodies = sections(test)
        source = Path(directory) / (test.stem + ".cc")
        executable = Path(directory) / test.stem
        source.write_text(bodies["includes"] + "\n" + bodies.get("global", "") +
                          "\nint main() {\n" + bodies["activity"] + "\n}\n")
        command = compiler + ["-std=c++17", "-O1", "-g", "-D_XOPEN_SOURCE=700",
                              "-I" + str(root / "src"), "-I" + str(omnet / "include"),
                              str(source), str(root / "src/inet/protocolelement/redundancy/VectorSequenceRecovery.cc"),
                              "-o", str(executable)]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        handle.write("COMMAND: " + shlex.join(command) + "\n")
        handle.flush()
        build = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
        handle.write(build.stdout)
        if build.returncode:
            print(build.stdout, file=sys.stderr)
            sys.exit(build.returncode)
        run_env = os.environ.copy()
        if args.sanitize:
            run_env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
            run_env["ASAN_OPTIONS"] = "halt_on_error=1"
        run = subprocess.run([str(executable)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=180, env=run_env)
        handle.write(run.stdout)
        handle.flush()
        print(test.name + ":\n" + run.stdout, end="", flush=True)
        if run.returncode:
            sys.exit(run.returncode)
        expected = bodies.get("contains", "").strip()
        if expected and expected not in run.stdout:
            raise RuntimeError("Expected test output was missing: " + test.name)
    handle.write("All native core tests passed.\n")
print("All native core tests passed. Log: " + str(log))
