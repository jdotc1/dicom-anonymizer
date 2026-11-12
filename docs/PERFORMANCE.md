# Performance notes

These are rough, caveated figures from **entirely synthetic** batches. They are
not a service level, not a release gate, and say nothing about real clinical
data, whose size, structure and header content differ. Treat every number as an
order of magnitude on one machine.

## Conditions that apply to every number below

- **Synthetic data only.** Small generated CT, MR and RTSTRUCT files with random
  pixel bytes and random contour coordinates. No scanner export, no clinical data.
- **CPU time, not wall time.** Figures are user plus system CPU time of the engine
  process (`time.process_time()`), because wall time on a shared or busy host was
  inflated by other load (load averages of tens were observed). Wall time is
  reported by the harness for reference only and should not be quoted.
- **One host, one Python.** Apple-silicon macOS, Python 3.13, pydicom 3.0.2, a local
  SSD. Other hosts, storage (network or external volumes), antivirus or Python
  versions will differ.
- **Single run, no repeats.** The harness result below is one run on a loaded host;
  run-to-run spread was not characterized. Small batches are dominated by fixed
  start-up cost.
- **Single-threaded.** The engine processes files one at a time in one process.
- **Not compared against any target.** Nothing here is a pass/fail criterion.

## Measuring it yourself

[`scripts/benchmark.py`](../scripts/benchmark.py) is a manual, bounded harness. It
is **not run by CI or any workflow and is not a gate**.

```sh
python scripts/benchmark.py --scratch-dir /path/to/scratch
python scripts/benchmark.py --scratch-dir /path/to/scratch --preset ds-heavy
```

It generates a synthetic batch inside a fresh `run-*` folder under `--scratch-dir`
(removed afterwards unless `--keep`), runs the engine scan and anonymization in a
child process, and prints JSON with per-phase CPU seconds, files per CPU second and
peak resident memory of that child. It refuses sizes above fixed caps (600 files, 64
MiB estimated payload, and per-parameter limits), checks free space, and consults
`storage-guard` if one is on `PATH`. Shape options: `--patients --slices --rows
--rois --points --seed`.

## Harness result (default preset, measured once)

Default preset: 2 patients, 10 CT and 10 MR slices each (64 x 64 pixels), one
RTSTRUCT per patient with 3 ROIs x 10 contours x 100 points. 42 files, about 0.5 MB.
Python 3.13, load average about 30-40 when measured.

| Quantity (CPU seconds unless noted) | Value |
| --- | --- |
| Engine and pydicom import | 0.18 |
| Scan alone (separate call) | 0.058 |
| Full `run()` (scan, processing, audit, publish) | 0.26 |
| of which audit span | 0.063 |
| Full run, files per CPU second | about 160 |
| Scan alone, files per CPU second | about 730 |
| Child process peak RSS | about 69 MB |

The scan-alone figure is a second, separate scan call; the full run performs its own
scan inside `run()`. With 42 files, import and fixed costs are a large share of the
total, so files per second here understates large-batch throughput and the figures
should not be extrapolated from this one point.

## Earlier exploratory measurements (not re-run for this document)

These came from earlier ad hoc synthetic-batch experiments with a similar
generator and are recorded for orientation only. They were not re-measured with the
harness above, and the original conditions (CPU time, loaded host, single machine,
minimum of several runs) apply.

| Observation | Value | Status |
| --- | --- | --- |
| Phase CPU, 22 / 66 / 198 small mixed files | 0.34 / 0.97 / 2.97 s | measured, exploratory |
| Plain image slices | on the order of 200 files/s | measured, exploratory |
| RTSTRUCT-heavy mixes | on the order of 66 files/s | measured, exploratory |
| Scaling with file count | roughly linear over the 22-198 file range | measured, exploratory; larger counts **extrapolated, not measured** |
| Retained Python heap per file | about 3 KB | measured with a heap probe, exploratory |
| Python heap per decimal-string value | about 457 bytes | measured with a heap probe, exploratory |
| One 6.5 MB RTSTRUCT with about 900,000 decimal-string values | peak RSS about 0.93 GB, versus about 43 MB for a small baseline batch | measured, exploratory, two runs |
| Start-up (import) per launch | 0.2-0.4 s CPU | measured, consistent with the 0.18 s above |

## Design facts relevant to cost

- Each input file is decoded in the scan pass, again when processed, and again
  during the output self-audit (three decodes). The macOS app's preview adds a
  fourth. Time scales with header and decimal-string content more than with pixel
  bytes, which are copied rather than interpreted.
- Memory is dominated by the largest single file held in decoded form plus
  per-file bookkeeping. A file with very many decimal-string values (large
  RTSTRUCT contours) costs far more memory than its on-disk size suggests; the
  exploratory 900,000-value probe above used roughly 20 times the baseline process
  memory. A simple "base plus a small multiple of the largest file" rule is **not**
  supported by that probe for decimal-string-heavy files.
- Generated identifiers are random, so output is not byte-reproducible between runs.

## Not measured

- Real clinical or scanner-exported data of any kind.
- Batches beyond a few hundred files, multi-gigabyte pixel payloads, compressed
  transfer syntaxes, or very deep sequence nesting.
- Network, external or encrypted volumes; antivirus or indexing interference.
- MRI JSON sidecar cleaning cost.
- The macOS app's user interface, worker pipe and preview costs.
- Other hosts, Intel Macs, Python versions other than 3.13 (the harness itself is
  written to run on 3.10 or newer).
- Variance across repeated runs.
