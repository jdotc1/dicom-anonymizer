#!/usr/bin/env python3
"""Fail-closed de-identification for MRI JSON sidecars.

The module is intentionally independent of pydicom and of the macOS UI.  It
parses bounded UTF-8 JSON without converting decimal numbers to binary floating
point, retains only a versioned allowlist of acquisition/physical metadata,
writes generated filenames into an unpublished staging directory, and audits
those outputs before the enclosing batch is published.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable, Iterable, Mapping
import unicodedata


class SidecarError(Exception):
    """A safe, user-presentable sidecar processing failure."""


class JSONLimits:
    max_bytes = 2 * 1024 * 1024
    max_values = 20_000
    max_depth = 32
    max_string_bytes = 65_536
    max_key_bytes = 512
    max_number_bytes = 256
    max_exponent = 400


@dataclass(frozen=True)
class BatchLimits:
    max_files: int = 10_000
    max_total_bytes: int = 256 * 1024 * 1024
    max_output_bytes: int = 4 * 1024 * 1024
    max_total_output_bytes: int = 256 * 1024 * 1024


_NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


@dataclass(frozen=True)
class RawNumber:
    """A syntactically valid JSON number with its original token preserved."""

    token: str

    def __post_init__(self) -> None:
        token_bytes = self.token.encode("ascii", errors="strict")
        if not token_bytes or len(token_bytes) > JSONLimits.max_number_bytes:
            raise SidecarError("Number exceeds the supported token length.")
        if _NUMBER_RE.fullmatch(self.token) is None:
            raise SidecarError("Invalid JSON number.")
        exponent_match = re.search(r"[eE]([+-]?)([0-9]+)\Z", self.token)
        if exponent_match:
            magnitude = int(exponent_match.group(2))
            if magnitude > JSONLimits.max_exponent:
                raise SidecarError("Number exponent magnitude exceeds 400.")

    def decimal(self) -> Decimal:
        try:
            return Decimal(self.token)
        except InvalidOperation as exc:  # Defensive: grammar was already checked.
            raise SidecarError("Invalid JSON number.") from exc

    @property
    def is_integral(self) -> bool:
        value = self.decimal()
        return value.is_finite() and value == value.to_integral_value()


JSONScalar = None | bool | str | RawNumber
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class _DuplicateKeyError(ValueError):
    pass


def _object_pairs(pairs: list[tuple[str, JSONValue]]) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {}
    canonical: set[str] = set()
    for key, value in pairs:
        normalized = unicodedata.normalize("NFC", key)
        if normalized in canonical:
            if key in result:
                raise _DuplicateKeyError("Duplicate object member name.")
            raise _DuplicateKeyError("Duplicate or canonically equivalent object member name.")
        canonical.add(normalized)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise SidecarError(f"Invalid JSON number constant: {value}.")


def _validate_tree(value: JSONValue, *, depth: int = 0, counter: list[int] | None = None) -> None:
    if counter is None:
        counter = [0]
    if depth > JSONLimits.max_depth:
        raise SidecarError("JSON nesting exceeds 32 levels.")
    counter[0] += 1
    if counter[0] > JSONLimits.max_values:
        raise SidecarError("JSON exceeds 20,000 values.")

    if isinstance(value, dict):
        for key, child in value.items():
            try:
                key_bytes = key.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise SidecarError("JSON member name contains an unpaired Unicode surrogate.") from exc
            if len(key_bytes) > JSONLimits.max_key_bytes:
                raise SidecarError("JSON member name exceeds its supported byte limit.")
            _validate_tree(child, depth=depth + 1, counter=counter)
    elif isinstance(value, list):
        for child in value:
            _validate_tree(child, depth=depth + 1, counter=counter)
    elif isinstance(value, str):
        try:
            value_bytes = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise SidecarError("JSON string contains an unpaired Unicode surrogate.") from exc
        if len(value_bytes) > JSONLimits.max_string_bytes:
            raise SidecarError("JSON string exceeds its supported byte limit.")


def parse_json_bytes(data: bytes) -> dict[str, JSONValue]:
    """Parse one bounded UTF-8 sidecar, preserving number lexemes exactly."""

    if len(data) > JSONLimits.max_bytes:
        raise SidecarError("JSON exceeds the 2 MiB input limit.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SidecarError("Input is not valid UTF-8 JSON.") from exc
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_int=RawNumber,
            parse_float=RawNumber,
            parse_constant=_reject_constant,
        )
    except _DuplicateKeyError as exc:
        raise SidecarError(str(exc)) from None
    except SidecarError:
        raise
    except RecursionError:
        raise SidecarError("Malformed JSON sidecar: nesting exceeds the parser's safe limit.") from None
    except (json.JSONDecodeError, UnicodeError, ValueError, TypeError) as exc:
        raise SidecarError(f"Malformed JSON sidecar: {exc}.") from None
    if not isinstance(parsed, dict):
        raise SidecarError("A sidecar must have a top-level JSON object.")
    _validate_tree(parsed)
    return parsed


def _quote(value: str) -> str:
    out: list[str] = ['"']
    escapes = {
        '"': '\\"',
        "\\": "\\\\",
        "\b": "\\b",
        "\f": "\\f",
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
    }
    for char in value:
        if char in escapes:
            out.append(escapes[char])
            continue
        codepoint = ord(char)
        if codepoint < 0x20 or 0x2028 <= codepoint <= 0x202E or 0x2066 <= codepoint <= 0x2069:
            if codepoint <= 0xFFFF:
                out.append(f"\\u{codepoint:04X}")
            else:
                codepoint -= 0x10000
                high = 0xD800 + (codepoint >> 10)
                low = 0xDC00 + (codepoint & 0x3FF)
                out.append(f"\\u{high:04X}\\u{low:04X}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def serialize_json(value: JSONValue, *, pretty: bool = True) -> str:
    """Serialize deterministically while emitting RawNumber tokens verbatim."""

    def render(item: JSONValue, depth: int) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, RawNumber):
            return item.token
        if isinstance(item, str):
            return _quote(item)
        if isinstance(item, list):
            if not item:
                return "[]"
            if not pretty:
                return "[" + ",".join(render(child, depth + 1) for child in item) + "]"
            indent = "  " * (depth + 1)
            end = "  " * depth
            return "[\n" + ",\n".join(indent + render(child, depth + 1) for child in item) + "\n" + end + "]"
        if isinstance(item, dict):
            if not item:
                return "{}"
            entries = [(key, item[key]) for key in sorted(item)]
            if not pretty:
                return "{" + ",".join(_quote(key) + ":" + render(child, depth + 1) for key, child in entries) + "}"
            indent = "  " * (depth + 1)
            end = "  " * depth
            return "{\n" + ",\n".join(
                indent + _quote(key) + ": " + render(child, depth + 1) for key, child in entries
            ) + "\n" + end + "}"
        raise TypeError(f"Unsupported JSON value type: {type(item).__name__}")

    return render(value, 0)


Shape = str


@dataclass(frozen=True)
class FieldRule:
    shape: Shape
    category: str
    unit: str | None = None
    allowed_values: frozenset[str] | None = None
    pattern: str | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    min_items: int = 1
    max_items: int | None = None

    def _accepts_string(self, value: str) -> bool:
        if len(value.encode("utf-8")) > 64:
            return False
        if self.allowed_values is not None and value not in self.allowed_values:
            return False
        if self.pattern is not None and re.fullmatch(self.pattern, value) is None:
            return False
        return True

    def _accepts_number(self, value: RawNumber, *, integral: bool = False) -> bool:
        if integral and not value.is_integral:
            return False
        number = value.decimal()
        if self.minimum is not None and number < self.minimum:
            return False
        if self.maximum is not None and number > self.maximum:
            return False
        return True

    def _accepts_array(self, value: JSONValue, *, integral: bool = False) -> bool:
        if not isinstance(value, list):
            return False
        if len(value) < self.min_items:
            return False
        if self.max_items is not None and len(value) > self.max_items:
            return False
        return all(isinstance(item, RawNumber) and self._accepts_number(item, integral=integral) for item in value)

    def accepts(self, value: JSONValue) -> bool:
        is_number = isinstance(value, RawNumber)
        is_string = isinstance(value, str)
        if self.shape == "number":
            return is_number and self._accepts_number(value)  # type: ignore[arg-type]
        if self.shape == "integer":
            return is_number and self._accepts_number(value, integral=True)  # type: ignore[arg-type]
        if self.shape == "number_or_array":
            return (is_number and self._accepts_number(value)) or self._accepts_array(value)  # type: ignore[arg-type]
        if self.shape == "number_array":
            return self._accepts_array(value)
        if self.shape == "integer_or_array":
            return (is_number and self._accepts_number(value, integral=True)) or self._accepts_array(value, integral=True)  # type: ignore[arg-type]
        if self.shape == "string":
            return is_string and self._accepts_string(value)  # type: ignore[arg-type]
        if self.shape == "string_or_array":
            return (is_string and self._accepts_string(value)) or (  # type: ignore[arg-type]
                isinstance(value, list)
                and bool(value)
                and all(isinstance(item, str) and self._accepts_string(item) for item in value)
            )
        if self.shape == "boolean":
            return isinstance(value, bool)
        return False


@dataclass(frozen=True)
class SidecarPolicy:
    policy_id: str
    policy_version: str
    catalog_revision: str
    description: str
    fields: Mapping[str, FieldRule]


_DEF_FIELDS: dict[str, FieldRule] = {}


def _add(
    keys: Iterable[str],
    shape: Shape,
    category: str,
    unit: str | None = None,
    *,
    allowed_values: Iterable[str] | None = None,
    pattern: str | None = None,
    minimum: int | float | str | None = None,
    maximum: int | float | str | None = None,
    min_items: int = 1,
    max_items: int | None = None,
) -> None:
    allowed = frozenset(allowed_values) if allowed_values is not None else None
    lower = Decimal(str(minimum)) if minimum is not None else None
    upper = Decimal(str(maximum)) if maximum is not None else None
    for key in keys:
        _DEF_FIELDS[key] = FieldRule(
            shape=shape, category=category, unit=unit,
            allowed_values=allowed, pattern=pattern,
            minimum=lower, maximum=upper,
            min_items=min_items, max_items=max_items)


_add(
    [
        "RepetitionTime",
        "RepetitionTimeExcitation",
        "InversionTime",
        "DwellTime",
        "EffectiveEchoSpacing",
        "TotalReadoutTime",
        "DelayTime",
        "AcquisitionDuration",
        "EstimatedEffectiveEchoSpacing",
        "EstimatedTotalReadoutTime",
        "DerivedVendorReportedEchoSpacing",
        "RepetitionTimeInversion",
    ],
    "number",
    "timing",
    "s",
    minimum=0,
    maximum=86_400,
)
_add(["EchoTime", "PostLabelingDelay", "RepetitionTimePreparation"], "number_or_array", "timing", "s", minimum=0, maximum=86_400, max_items=1_024)
_add(["SliceTiming", "VolumeTiming"], "number_array", "timing", "s", minimum=0, maximum=86_400, max_items=10_000)
_add(["FlipAngle"], "number_or_array", "acquisition", "deg", minimum=0, maximum=360, max_items=1_024)
_add(["EchoNumber", "EchoTrainLength", "ReconMatrixPE", "AcquisitionMatrixPE"], "integer", "acquisition", minimum=0, maximum=1_000_000)
_add(
    [
        "NumberOfAverages",
        "PartialFourier",
        "ParallelReductionFactorInPlane",
        "MultibandAccelerationFactor",
    ],
    "number",
    "acquisition",
    minimum=0,
    maximum=1_000_000,
)
_add(["MRAcquisitionType"], "string", "acquisition", allowed_values=["2D", "3D"])
_add(["PhaseEncodingDirection", "SliceEncodingDirection"], "string", "encoding", pattern=r"[ijk]-?")
_add(["InPlanePhaseEncodingDirectionDICOM"], "string", "encoding", allowed_values=["ROW", "COL"])
_add(["Modality"], "string", "acquisition", allowed_values=["MR"])
_add(
    ["PatientPosition"], "string", "geometry",
    allowed_values=["HFS", "HFP", "FFS", "FFP", "HFDR", "HFDL", "FFDR", "FFDL"])
_add(
    ["ArterialSpinLabelingType"], "string", "acquisition",
    allowed_values=["PCASL", "CASL", "PASL"])
_add(
    ["ScanningSequence"], "string_or_array", "acquisition",
    allowed_values=["SE", "IR", "GR", "EP", "RM"])
_add(
    ["SequenceVariant"], "string_or_array", "acquisition",
    allowed_values=["SK", "MTC", "SS", "TRSS", "SP", "MP", "OSP", "NONE"])
_add(
    ["ScanOptions"], "string_or_array", "acquisition",
    allowed_values=["PER", "RG", "CG", "PPG", "FC", "PFF", "PFP", "SP", "FS"])
_add(["NonlinearGradientCorrection", "SpoilingState"], "boolean", "acquisition")
# Field-specific bounds that are narrower than the grouped defaults above.
_DEF_FIELDS["PartialFourier"] = replace(_DEF_FIELDS["PartialFourier"], maximum=Decimal("1"))
_DEF_FIELDS["ParallelReductionFactorInPlane"] = replace(
    _DEF_FIELDS["ParallelReductionFactorInPlane"], maximum=Decimal("100"))
_DEF_FIELDS["MultibandAccelerationFactor"] = replace(
    _DEF_FIELDS["MultibandAccelerationFactor"], maximum=Decimal("100"))

_add(["MagneticFieldStrength"], "number", "scanner", "T", minimum=0, maximum=100)
_add(["ImagingFrequency"], "number", "scanner", "MHz", minimum=0, maximum=100_000)
_add(["PixelBandwidth"], "number", "encoding", "Hz", minimum=0, maximum=1_000_000_000)
_add(["SliceThickness", "SpacingBetweenSlices"], "number", "geometry", "mm", minimum=0, maximum=10_000)
_add(["ImageOrientationPatientDICOM"], "number_array", "geometry", minimum=-1, maximum=1, min_items=6, max_items=6)

MRI_PHYSICAL_V1 = SidecarPolicy(
    policy_id="mri-physical-v1",
    policy_version="1.0.0",
    catalog_revision="2026-10-24.1",
    description=(
        "Fail-closed top-level allowlist for MRI acquisition, encoding, geometry, scanner-physics, "
        "and conversion metadata. Patient, institution, device-instance, dates/times, paths, "
        "free text, and unknown fields are omitted."
    ),
    fields=dict(_DEF_FIELDS),
)


@dataclass(frozen=True)
class CleanResult:
    retained_fields: int
    dropped_fields: int


def clean_document(document: Mapping[str, JSONValue], policy: SidecarPolicy) -> tuple[dict[str, JSONValue], CleanResult]:
    cleaned: dict[str, JSONValue] = {}
    dropped = 0
    for key, value in document.items():
        rule = policy.fields.get(key)
        if rule is None:
            dropped += 1
            continue
        if not rule.accepts(value):
            raise SidecarError(f"Known sidecar field '{key}' has an unsupported value shape.")
        cleaned[key] = value
    return cleaned, CleanResult(retained_fields=len(cleaned), dropped_fields=dropped)


Fingerprint = tuple[int, int, int, int]


@dataclass(frozen=True)
class SidecarRecord:
    source: Path
    patient: str
    relative_path: str
    signature: Fingerprint
    size: int
    estimated_output_bytes: int = 0


@dataclass(frozen=True)
class WrittenSidecar:
    output: Path
    patient: str
    ordinal: int
    expected_sha256: str
    expected_size: int
    retained_fields: int
    dropped_fields: int


@dataclass(frozen=True)
class BatchSummary:
    enabled: bool
    files_discovered: int
    files_written: int
    files_audited: int
    source_bytes: int
    output_bytes: int
    retained_fields: int
    dropped_fields: int

    @classmethod
    def disabled(cls) -> "BatchSummary":
        return cls(False, 0, 0, 0, 0, 0, 0, 0)

    @classmethod
    def discovered(cls, records: Iterable[SidecarRecord]) -> "BatchSummary":
        records = list(records)
        return cls(True, len(records), 0, 0, sum(item.size for item in records), 0, 0, 0)

    def with_audit(self, files_audited: int) -> "BatchSummary":
        return replace(self, files_audited=files_audited)


@dataclass(frozen=True)
class AuditSummary:
    files_audited: int


def fingerprint(path: Path) -> Fingerprint:
    info = path.stat(follow_symlinks=False)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _read_regular_nofollow(path: Path, *, maximum: int | None = None) -> tuple[bytes, Fingerprint]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SidecarError("A JSON sidecar could not be opened as a regular local file.") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SidecarError("JSON sidecars must be regular local files.")
        chunks: list[bytes] = []
        remaining = None if maximum is None else maximum + 1
        while remaining is None or remaining > 0:
            chunk = os.read(descriptor, 64 * 1024 if remaining is None else min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            if remaining is not None:
                remaining -= len(chunk)
        after = os.fstat(descriptor)
        first = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        second = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if first != second:
            raise SidecarError("A JSON sidecar changed while it was being read.")
        return b"".join(chunks), first
    finally:
        os.close(descriptor)


def _is_part10_dicom(path: Path) -> bool:
    data, _signature = _read_regular_nofollow(path, maximum=132)
    return len(data) >= 132 and data[128:132] == b"DICM"


def _is_appledouble(path: Path) -> bool:
    if not path.name.startswith("._"):
        return False
    data, _signature = _read_regular_nofollow(path, maximum=4)
    return data[:4] == b"\x00\x05\x16\x07"


def scan_sidecars(source: str | os.PathLike[str], *, limits: BatchLimits = BatchLimits(), cancel_check: CancelCheck | None = None) -> list[SidecarRecord]:
    """Discover regular .json files under numeric patient folders without reading values."""

    root = Path(source).absolute()
    if root.is_symlink() or not root.is_dir():
        raise SidecarError("Select an existing local batch folder, without symbolic links.")
    records: list[SidecarRecord] = []
    total_bytes = 0
    def walk_error(error):
        raise SidecarError("JSON sidecar folders cannot be listed. Check read permissions and retry.") from None
    try:
        patients = sorted(root.iterdir(), key=lambda item: item.name)
        for patient in patients:
            if patient.is_symlink():
                raise SidecarError("Symbolic links are not supported. Use a local copy of the input folders.")
            if not patient.is_dir() or re.fullmatch(r"[0-9]+", patient.name) is None:
                # The DICOM scanner owns root-layout validation. Sidecar discovery only follows valid patient folders.
                continue
            for current, dirs, files in os.walk(patient, followlinks=False, onerror=walk_error):
                dirs.sort()
                files.sort()
                current_path = Path(current)
                for directory in dirs:
                    if (current_path / directory).is_symlink():
                        raise SidecarError("Symbolic links are not supported. Use a local copy of the input folders.")
                if cancel_check is not None:
                    cancel_check()
                for name in files:
                    if cancel_check is not None:
                        cancel_check()
                    path = current_path / name
                    if path.suffix.lower() != ".json":
                        continue
                    if path.is_symlink():
                        raise SidecarError("Symbolic links are not supported. Use a local copy of the input folders.")
                    info = path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise SidecarError("JSON sidecars must be regular local files.")
                    if _is_part10_dicom(path) or _is_appledouble(path):
                        continue
                    if info.st_size > JSONLimits.max_bytes:
                        raise SidecarError("A JSON sidecar exceeds the 2 MiB input limit.")
                    total_bytes += info.st_size
                    if total_bytes > limits.max_total_bytes:
                        raise SidecarError("The aggregate JSON sidecar byte limit was exceeded.")
                    if len(records) >= limits.max_files:
                        raise SidecarError("The number of JSON sidecars exceeds the batch limit.")
                    signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    data, stable_signature = _read_regular_nofollow(path, maximum=JSONLimits.max_bytes)
                    if stable_signature != signature or fingerprint(path) != signature:
                        raise SidecarError("A JSON sidecar changed during batch checking. Keep input files unchanged and retry.")
                    document = parse_json_bytes(data)
                    cleaned, _result = clean_document(document, MRI_PHYSICAL_V1)
                    output_size = len((serialize_json(cleaned, pretty=True) + "\n").encode("utf-8"))
                    if output_size > limits.max_output_bytes:
                        raise SidecarError("The cleaned JSON sidecar output byte limit was exceeded.")
                    records.append(
                        SidecarRecord(
                            source=path,
                            patient=patient.name,
                            relative_path=path.relative_to(patient).as_posix(),
                            signature=signature,
                            size=info.st_size,
                            estimated_output_bytes=output_size,
                        )
                    )
    except SidecarError:
        raise
    except OSError as exc:
        raise SidecarError("JSON sidecar files cannot be read. Check permissions and available local storage.") from exc
    records.sort(key=lambda item: (item.patient, item.relative_path))
    return records


def _read_stable(record: SidecarRecord) -> bytes:
    path = record.source
    if path.is_symlink() or fingerprint(path) != record.signature:
        raise SidecarError("A JSON sidecar changed during processing. Keep input files unchanged and retry.")
    data, signature = _read_regular_nofollow(path, maximum=JSONLimits.max_bytes)
    if len(data) > JSONLimits.max_bytes:
        raise SidecarError("A JSON sidecar exceeds the 2 MiB input limit.")
    if signature != record.signature or path.is_symlink() or fingerprint(path) != record.signature:
        raise SidecarError("A JSON sidecar changed during processing. Keep input files unchanged and retry.")
    return data


def _ensure_owned_directory(root: Path, path: Path) -> None:
    root = root.absolute()
    path = path.absolute()
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise SidecarError("A generated sidecar output directory escaped staging.") from None
    if root.is_symlink() or not root.is_dir():
        raise SidecarError("The staging directory is unavailable or was replaced.")
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
            except FileExistsError:
                info = current.lstat()
            else:
                info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise SidecarError("A generated sidecar output directory is symbolic, replaced, or not a directory.")


def _verify_owned_parent(root: Path, path: Path) -> None:
    _ensure_owned_directory(root, path.parent)


def _exclusive_write(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise SidecarError("A generated JSON sidecar output already exists in staging.") from None
    except OSError as exc:
        raise SidecarError("A cleaned JSON sidecar could not be written to staging.") from exc
    try:
        view = memoryview(data)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError("short write")
            view = view[count:]
        os.fsync(descriptor)
    except OSError as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SidecarError("A cleaned JSON sidecar could not be written to staging.") from exc
    finally:
        os.close(descriptor)


Progress = Callable[..., None]
CancelCheck = Callable[[], None]


def clean_sidecars_to_staging(
    records: Iterable[SidecarRecord],
    staging: str | os.PathLike[str],
    policy: SidecarPolicy = MRI_PHYSICAL_V1,
    *,
    progress: Progress | None = None,
    cancel_check: CancelCheck | None = None,
    limits: BatchLimits = BatchLimits(),
    output_operation: Callable[..., Any] | None = None,
) -> tuple[list[WrittenSidecar], BatchSummary]:
    records = list(records)
    output_operation = output_operation or (lambda operation, *args: operation(*args))
    root = Path(staging).absolute()
    counters: dict[str, int] = {}
    written: list[WrittenSidecar] = []
    output_bytes = retained = dropped = 0
    total = len(records)
    if progress is not None:
        progress("sidecar_progress", processed=0, total_files=total)
    for index, record in enumerate(records, 1):
        if cancel_check is not None:
            cancel_check()
        source = _read_stable(record)
        document = parse_json_bytes(source)
        cleaned, result = clean_document(document, policy)
        encoded = (serialize_json(cleaned, pretty=True) + "\n").encode("utf-8")
        if len(encoded) > limits.max_output_bytes or output_bytes + len(encoded) > limits.max_total_output_bytes:
            raise SidecarError("The cleaned JSON sidecar output byte limit was exceeded.")
        if cancel_check is not None:
            cancel_check()

        counters[record.patient] = counters.get(record.patient, 0) + 1
        ordinal = counters[record.patient]
        folder = root / record.patient / "Sidecars"
        output_operation(_ensure_owned_directory, root, folder)
        output = folder / f"Sidecar_{ordinal:06d}.json"
        output_operation(_exclusive_write, output, encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        written.append(
            WrittenSidecar(
                output=output,
                patient=record.patient,
                ordinal=ordinal,
                expected_sha256=digest,
                expected_size=len(encoded),
                retained_fields=result.retained_fields,
                dropped_fields=result.dropped_fields,
            )
        )
        output_bytes += len(encoded)
        retained += result.retained_fields
        dropped += result.dropped_fields
        if progress is not None and (index % 10 == 0 or index == total):
            progress("sidecar_progress", processed=index, total_files=total)

    summary = BatchSummary(
        enabled=True,
        files_discovered=total,
        files_written=len(written),
        files_audited=0,
        source_bytes=sum(record.size for record in records),
        output_bytes=output_bytes,
        retained_fields=retained,
        dropped_fields=dropped,
    )
    return written, summary


def _audit_document(document: Mapping[str, JSONValue], policy: SidecarPolicy) -> None:
    for key, value in document.items():
        rule = policy.fields.get(key)
        if rule is None:
            raise SidecarError("Cleaned JSON sidecar contains a field not allowed by policy.")
        if not rule.accepts(value):
            raise SidecarError(f"Cleaned JSON sidecar field '{key}' has an invalid value shape.")


def audit_sidecars(
    staging: str | os.PathLike[str],
    written: Iterable[WrittenSidecar],
    policy: SidecarPolicy = MRI_PHYSICAL_V1,
    *,
    progress: Progress | None = None,
    cancel_check: CancelCheck | None = None,
) -> AuditSummary:
    root = Path(staging).absolute()
    entries = list(written)
    total = len(entries)
    if progress is not None:
        progress("sidecar_audit_progress", audited_files=0, total_files=total)
    for index, item in enumerate(entries, 1):
        if cancel_check is not None:
            cancel_check()
        try:
            relative = item.output.absolute().relative_to(root)
        except ValueError:
            raise SidecarError("A cleaned JSON sidecar escaped the staging directory.") from None
        if relative.parts[:2] != (item.patient, "Sidecars"):
            raise SidecarError("A cleaned JSON sidecar is in an unexpected staging location.")
        path = item.output
        _verify_owned_parent(root, path)
        if path.is_symlink():
            raise SidecarError("A cleaned JSON sidecar was replaced before audit.")
        try:
            data, _signature = _read_regular_nofollow(path, maximum=JSONLimits.max_bytes)
        except SidecarError as exc:
            raise SidecarError("A cleaned JSON sidecar could not be re-read safely for audit.") from exc
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != item.expected_size or digest != item.expected_sha256:
            raise SidecarError("A cleaned JSON sidecar changed after cleaning and before publication.")
        document = parse_json_bytes(data)
        _audit_document(document, policy)
        recleaned, result = clean_document(document, policy)
        if result.dropped_fields != 0 or serialize_json(recleaned, pretty=True) + "\n" != data.decode("utf-8"):
            raise SidecarError("A cleaned JSON sidecar does not match the canonical policy output.")
        if progress is not None and (index % 10 == 0 or index == total):
            progress("sidecar_audit_progress", audited_files=index, total_files=total)
    return AuditSummary(files_audited=total)


def seal_staging_inventory(
    staging: str | os.PathLike[str],
    *,
    dicom_paths: Iterable[str | os.PathLike[str]],
    sidecar_paths: Iterable[str | os.PathLike[str]],
    report_path: str | os.PathLike[str] | None,
    sidecar_expectations: Iterable[WrittenSidecar] | None = None,
    cancel_check: CancelCheck | None = None,
) -> None:
    """Reject any file or directory not produced by the current operation."""

    root = Path(staging).absolute()
    if root.is_symlink() or not root.is_dir():
        raise SidecarError("The staging directory is unavailable or was replaced.")
    expected_files = {Path(path).absolute() for path in dicom_paths}
    expected_files.update(Path(path).absolute() for path in sidecar_paths)
    if report_path is not None:
        expected_files.add(Path(report_path).absolute())

    allowed_dirs = {root}
    for path in expected_files:
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise SidecarError("An expected output escaped the staging directory.") from None
        parent = root
        for part in relative.parts[:-1]:
            parent = parent / part
            allowed_dirs.add(parent)

    seen_files: set[Path] = set()
    seen_dirs: set[Path] = {root}
    def walk_error(error):
        raise SidecarError("Staging could not be fully inspected. No output was published.") from None

    for current, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        if cancel_check is not None:
            cancel_check()
        current_path = Path(current).absolute()
        for name in list(dirs):
            path = (current_path / name).absolute()
            if path.is_symlink():
                raise SidecarError("Staging contains an unexpected symbolic-link directory.")
            seen_dirs.add(path)
        for name in files:
            path = (current_path / name).absolute()
            if path.is_symlink():
                raise SidecarError("Staging contains an unexpected symbolic-link file.")
            info = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise SidecarError("Staging contains an unexpected non-regular file.")
            if path not in expected_files:
                raise SidecarError("Staging contains an unexpected file. No output was published.")
            seen_files.add(path)

    unexpected_dirs = seen_dirs - allowed_dirs
    if unexpected_dirs:
        raise SidecarError("Staging contains an unexpected directory. No output was published.")
    if seen_files != expected_files:
        raise SidecarError("Staging is missing an expected output file. No output was published.")

    for item in sidecar_expectations or ():
        if cancel_check is not None:
            cancel_check()
        _verify_owned_parent(root, item.output)
        try:
            data, _signature = _read_regular_nofollow(item.output, maximum=JSONLimits.max_bytes)
        except SidecarError as exc:
            raise SidecarError("A cleaned JSON sidecar could not be sealed safely.") from exc
        if len(data) != item.expected_size or hashlib.sha256(data).hexdigest() != item.expected_sha256:
            raise SidecarError("A cleaned JSON sidecar changed after audit; its digest no longer matches.")


def sidecar_report(summary: BatchSummary, policy: SidecarPolicy = MRI_PHYSICAL_V1) -> dict[str, Any]:
    """Return a value-free report fragment safe to include in the batch report."""

    return {
        "enabled": summary.enabled,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "catalog_revision": policy.catalog_revision,
        "mode": "top-level allowlist; unknown and identifier-bearing fields omitted",
        "files_discovered": summary.files_discovered,
        "files_written": summary.files_written,
        "files_audited": summary.files_audited,
        "source_bytes": summary.source_bytes,
        "output_bytes": summary.output_bytes,
        "retained_field_count": summary.retained_fields,
        "dropped_field_count": summary.dropped_fields,
        "limitations": [
            "This cleans JSON metadata only; it does not inspect NIfTI voxels or other companion formats.",
            "Retained acquisition values may remain linkable when combined with external data.",
            "Review cleaned output and downstream sharing requirements before release.",
        ],
    }


__all__ = [
    "AuditSummary",
    "BatchLimits",
    "BatchSummary",
    "CleanResult",
    "FieldRule",
    "JSONLimits",
    "MRI_PHYSICAL_V1",
    "RawNumber",
    "SidecarError",
    "SidecarPolicy",
    "SidecarRecord",
    "WrittenSidecar",
    "audit_sidecars",
    "clean_document",
    "clean_sidecars_to_staging",
    "fingerprint",
    "parse_json_bytes",
    "scan_sidecars",
    "seal_staging_inventory",
    "serialize_json",
    "sidecar_report",
]
