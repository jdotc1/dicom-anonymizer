# Bulk metadata engine

Use Python 3.10+ with pydicom 3.0.2. From the repository root:

```sh
python engine/engine.py --source .synthetic/input --scan
python engine/engine.py --source .synthetic/input --destination .synthetic/output
```

Input folders are numeric patient pseudonyms. The engine performs bulk metadata pseudonymization, remaps references, audits staged output and publishes a new batch atomically. Read `docs/DATA-HANDLING.md` and the root README for exact retention and limits. No Python runtime or patient data is bundled in this source repository.

JSON-line event names are scan, progress, complete and error. Errors use fixed text to avoid exposing source identity. Library diagnostic messages are suppressed. Policy version: 2.0-build5. Runtime acceptance of this source review snapshot remains pending.
