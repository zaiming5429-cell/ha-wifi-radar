#!/usr/bin/env python3
"""Collect privacy-safe Wi-Fi link metrics and publish radar samples."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import platform
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
DEFAULT_OUTPUT = Path.home() / ".local/state/wifi-radar/wifi_radar.json"
MAX_SAMPLES = 600
STOP_REQUESTED = False


@dataclass(frozen=True)
class WifiReading:
    rssi_dbm: float
    signal_percent: int | None
    receive_mbps: float | None
    transmit_mbps: float | None
    channel: int | None
    radio_type: str | None


def _request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def _decode_windows_output(raw: bytes) -> str:
    """Decode output from Korean or English Windows without locale assumptions."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    candidates: list[tuple[int, str]] = []
    for encoding in ("utf-8", "cp949", "euc-kr", "utf-16-le"):
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        score = decoded.count("\ufffd") + decoded.count("\x00")
        candidates.append((score, decoded))
    if not candidates:
        return raw.decode("utf-8", errors="replace")
    return min(candidates, key=lambda item: item[0])[1]


def _run_netsh(timeout_seconds: float = 4.0) -> str:
    commands = (
        ["netsh.exe", "wlan", "show", "interfaces"],
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
            "netsh wlan show interfaces",
        ],
    )
    errors: list[str] = []
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout_seconds,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{command[0]}: {exc}")
            continue
        text = _decode_windows_output(completed.stdout)
        if completed.returncode == 0 and ":" in text:
            return text
        stderr = _decode_windows_output(completed.stderr).strip()
        errors.append(f"{command[0]} exit={completed.returncode}: {stderr[:160]}")
    raise RuntimeError("; ".join(errors) or "netsh produced no usable output")


def _normalise_key(value: str) -> str:
    return re.sub(r"[\s_.()\-/]", "", value).casefold()


def _parse_number(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_netsh(text: str) -> WifiReading:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        fields[_normalise_key(key)] = value.strip()

    def find(*keys: str) -> str | None:
        for key in keys:
            value = fields.get(_normalise_key(key))
            if value is not None:
                return value
        return None

    state = find("state", "상태")
    if state and not any(word in state.casefold() for word in ("connected", "연결됨")):
        raise RuntimeError(f"Wi-Fi interface is not connected: {state}")

    signal_value = _parse_number(find("signal", "신호") or "")
    if signal_value is None:
        for candidate_text in fields.values():
            candidate = _parse_number(candidate_text) if "%" in candidate_text else None
            if candidate is not None and 0 <= candidate <= 100:
                signal_value = candidate
                break
    signal_percent = (
        max(0, min(100, round(signal_value))) if signal_value is not None else None
    )
    direct_rssi = _parse_number(find("rssi", "수신신호강도") or "")
    if direct_rssi is not None and -120 <= direct_rssi <= 0:
        rssi_dbm = direct_rssi
    elif signal_percent is not None:
        # Common netsh approximation when Windows does not expose the Rssi field.
        rssi_dbm = (signal_percent / 2.0) - 100.0
    else:
        raise RuntimeError("netsh output contains neither Rssi nor Signal/신호")

    receive = _parse_number(
        find("receive rate (Mbps)", "receive rate", "수신 속도(Mbps)", "수신속도") or ""
    )
    transmit = _parse_number(
        find("transmit rate (Mbps)", "transmit rate", "전송 속도(Mbps)", "전송속도") or ""
    )
    channel_number = _parse_number(find("channel", "채널") or "")
    radio_type = find("radio type", "무선 종류", "무선종류")
    return WifiReading(
        rssi_dbm=round(rssi_dbm, 2),
        signal_percent=signal_percent,
        receive_mbps=receive,
        transmit_mbps=transmit,
        channel=round(channel_number) if channel_number is not None else None,
        radio_type=radio_type,
    )


def parse_iw(text: str) -> WifiReading:
    """Parse Linux iw output without retaining SSID or BSSID."""
    signal_match = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", text, re.IGNORECASE)
    if not signal_match:
        raise RuntimeError("iw output contains no signal value")
    return WifiReading(float(signal_match.group(1)), None, None, None, None, None)


def _run_reader_command(command: list[str]) -> str:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=5.0)
    if completed.returncode != 0:
        raise RuntimeError(f"{command[0]} failed with exit code {completed.returncode}")
    return _decode_windows_output(completed.stdout)


def read_linux(interface: str | None) -> WifiReading:
    if not interface:
        listing = _run_reader_command(["iw", "dev"])
        match = re.search(r"^\s*Interface\s+(\S+)", listing, re.MULTILINE)
        if not match:
            raise RuntimeError("no Wi-Fi interface found; pass --interface")
        interface = match.group(1)
    return parse_iw(_run_reader_command(["iw", "dev", interface, "link"]))


def read_custom(command: str) -> WifiReading:
    if not command.strip():
        raise ValueError("--command is required for custom source")
    payload = json.loads(_run_reader_command(shlex.split(command)))
    rssi = payload.get("rssi_dbm") if isinstance(payload, dict) else None
    if not isinstance(rssi, (int, float)) or isinstance(rssi, bool) or not math.isfinite(float(rssi)) or not -120 <= float(rssi) <= 0:
        raise ValueError("custom command must print JSON with rssi_dbm between -120 and 0")
    percent = payload.get("signal_percent")
    return WifiReading(float(rssi), int(percent) if isinstance(percent, (int, float)) else None, None, None, None, None)


def select_reader(source: str, interface: str | None, command: str | None) -> tuple[str, Callable[[], WifiReading]]:
    if source == "custom":
        return "custom_json_command", lambda: read_custom(command or "")
    if source == "windows":
        return "windows_netsh_wlan", lambda: parse_netsh(_run_netsh())
    if source == "linux":
        return "linux_iw", lambda: read_linux(interface)
    if shutil.which("netsh.exe") or platform.system() == "Windows":
        return "windows_netsh_wlan", lambda: parse_netsh(_run_netsh())
    if shutil.which("iw"):
        return "linux_iw", lambda: read_linux(interface)
    raise RuntimeError("no supported Wi-Fi reader; use --source custom --command")


def _load_samples(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        samples = payload.get("samples", [])
        if isinstance(samples, list):
            return [sample for sample in samples if isinstance(sample, dict)][-MAX_SAMPLES:]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _finite_rssi(samples: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for sample in samples:
        value = sample.get("rssi_dbm")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _score_reading(reading: WifiReading, previous: list[dict[str, Any]]) -> tuple[dict[str, float], float, str, bool]:
    # A slow 120-sample window follows normal RF drift while retaining short motion spikes.
    history = _finite_rssi(previous)[-120:]
    baseline_values = (history + [reading.rssi_dbm])[-120:]
    mean = statistics.fmean(baseline_values)
    stddev = statistics.pstdev(baseline_values) if len(baseline_values) >= 2 else 0.0

    recent = (history + [reading.rssi_dbm])[-12:]
    recent_stddev = statistics.pstdev(recent) if len(recent) >= 2 else 0.0
    prior = history[-1] if history else reading.rssi_dbm
    instant_delta = abs(reading.rssi_dbm - prior)
    baseline_deviation = abs(reading.rssi_dbm - mean)

    # At least 0.65 dB of assumed noise prevents a flat startup baseline from exploding.
    noise = max(stddev, 0.65)
    score = min(
        100.0,
        14.0 * (instant_delta / noise)
        + 12.0 * (baseline_deviation / noise)
        + 10.0 * (recent_stddev / noise),
    )
    score = round(score, 1)
    if score >= 70:
        level = "high"
    elif score >= 45:
        level = "medium"
    elif score >= 25:
        level = "low"
    else:
        level = "quiet"

    motion_window = recent[-8:]
    motion_span = max(motion_window) - min(motion_window) if motion_window else 0.0
    motion_path = sum(abs(current - prior) for prior, current in zip(motion_window, motion_window[1:]))
    structural_motion = motion_span >= 4.0 and motion_path >= 6.0

    previous_score = previous[-1].get("vibration_score") if previous else None
    previous_score_high = (
        isinstance(previous_score, (int, float)) and float(previous_score) >= 45.0
    )
    motion_candidate = (
        len(history) >= 20
        and score >= 45.0
        and previous_score_high
        and structural_motion
    )

    baseline = {
        "mean_dbm": round(mean, 3),
        "stddev_db": round(stddev, 3),
        "sample_count": len(baseline_values),
    }
    return baseline, score, level, motion_candidate


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def collect_once(path: Path, reader: Callable[[], WifiReading] | None = None, source_name: str = "windows_netsh_wlan", interval: float = 1.0) -> dict[str, Any]:
    reading = reader() if reader else parse_netsh(_run_netsh())
    samples = _load_samples(path)
    baseline, score, level, candidate = _score_reading(reading, samples)
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    sample: dict[str, Any] = {
        "timestamp": timestamp,
        "rssi_dbm": reading.rssi_dbm,
        "signal_percent": reading.signal_percent,
        "receive_mbps": reading.receive_mbps,
        "transmit_mbps": reading.transmit_mbps,
        "channel": reading.channel,
        "vibration_score": score,
        "motion_level": level,
        "motion_candidate": candidate,
    }
    samples.append(sample)
    samples = samples[-MAX_SAMPLES:]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "calibrating" if len(samples) < 20 else "online",
        "updated_at": timestamp,
        "source": source_name,
        "privacy": "SSID, BSSID, MAC and IP addresses are intentionally not stored",
        "sample_interval_seconds": interval,
        "max_samples": MAX_SAMPLES,
        "baseline": baseline,
        "current": sample,
        "samples": samples,
    }
    _atomic_json_write(path, payload)
    return payload


def write_error_status(path: Path, message: str, source_name: str, interval: float) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    existing_samples = _load_samples(path)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "error",
        "updated_at": timestamp,
        "source": source_name,
        "error": message[:500],
        "sample_interval_seconds": interval,
        "max_samples": MAX_SAMPLES,
        "samples": existing_samples,
    }
    _atomic_json_write(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--source", choices=("auto", "windows", "linux", "custom"), default="auto")
    parser.add_argument("--interface", help="Linux Wi-Fi interface when auto-detection is ambiguous")
    parser.add_argument("--command", help="custom executable and arguments that print one JSON object")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--doctor", action="store_true", help="test the Wi-Fi source without writing data")
    args = parser.parse_args()
    if args.interval < 0.25:
        parser.error("--interval must be at least 0.25 seconds")

    try:
        source_name, reader = select_reader(args.source, args.interface, args.command)
        if args.doctor:
            reading = reader()
            print(json.dumps({"ok": True, "source": source_name, "rssi_dbm": reading.rssi_dbm, "privacy": "network identifiers omitted"}, separators=(",", ":")))
            return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"source check failed: {exc}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    consecutive_errors = 0
    while not STOP_REQUESTED:
        cycle_started = time.monotonic()
        try:
            payload = collect_once(args.output, reader, source_name, args.interval)
            consecutive_errors = 0
            current = payload["current"]
            print(
                f"{payload['updated_at']} rssi={current['rssi_dbm']:.1f}dBm "
                f"score={current['vibration_score']:.1f} "
                f"motion={current['motion_level']} candidate={current['motion_candidate']}",
                flush=True,
            )
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            consecutive_errors += 1
            message = f"{type(exc).__name__}: {exc}"
            print(message, file=sys.stderr, flush=True)
            try:
                write_error_status(args.output, message, source_name, args.interval)
            except OSError as write_exc:
                print(f"failed to publish error status: {write_exc}", file=sys.stderr)
        if args.once:
            return 0 if consecutive_errors == 0 else 1
        elapsed = time.monotonic() - cycle_started
        # Gradual backoff avoids CPU churn while Windows networking is unavailable.
        delay = max(args.interval - elapsed, 0.05)
        if consecutive_errors:
            delay = max(delay, min(30.0, 2.0 ** min(consecutive_errors, 5)))
        time.sleep(delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
