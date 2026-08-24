#!/usr/bin/env python3
"""Read-only Wi-Fi radar to authenticated HTTP bridge."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def parse_timestamp(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass
class Passage:
    started_at: str
    ended_at: str | None = None
    peak_score: float = 0.0
    max_delta_db: float = 0.0
    duration_seconds: float = 0.0
    sample_count: int = 0


class RadarState:
    """Bounded, thread-safe projection of the collector JSON."""

    def __init__(self, source: Path, stale_seconds: float, start_score: float = 45.0, end_score: float = 35.0, start_samples: int = 2, end_samples: int = 3) -> None:
        self.source = source
        self.stale_seconds = stale_seconds
        self.start_score = start_score
        self.end_score = end_score
        self.start_samples = start_samples
        self.end_samples = end_samples
        self.lock = threading.Lock()
        self.source_data: dict[str, Any] = {}
        self.source_error: str | None = "not_loaded"
        self.last_loaded_at: float | None = None
        self.last_sample_timestamp: str | None = None
        self.high_streak = 0
        self.low_streak = 0
        self.active_passage: Passage | None = None
        self.last_passage: Passage | None = None
        self.passage_count = 0

    def update(self) -> None:
        try:
            with self.source.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("source root must be an object")
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("samples must be a list")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            with self.lock:
                self.source_error = type(exc).__name__
            return

        with self.lock:
            self.source_data = data
            self.source_error = None
            self.last_loaded_at = time.time()
            for sample in samples[-600:]:
                self._consume(sample, data)

    def _consume(self, sample: object, data: dict[str, Any]) -> None:
        if not isinstance(sample, dict):
            return
        timestamp = sample.get("timestamp")
        if not isinstance(timestamp, str) or timestamp <= (self.last_sample_timestamp or ""):
            return
        self.last_sample_timestamp = timestamp
        score = _number(sample.get("vibration_score"), 0.0)
        rssi = _number(sample.get("rssi_dbm"), 0.0)
        baseline = data.get("baseline")
        baseline_mean = _number(baseline.get("mean_dbm"), rssi) if isinstance(baseline, dict) else rssi

        candidate_value = sample.get("motion_candidate")
        motion_confirmed = candidate_value if isinstance(candidate_value, bool) else True
        self.high_streak = self.high_streak + 1 if score >= self.start_score and motion_confirmed else 0
        self.low_streak = self.low_streak + 1 if score < self.end_score else 0

        if self.active_passage is None and self.high_streak >= self.start_samples:
            self.active_passage = Passage(started_at=timestamp)
            self.passage_count += 1

        passage = self.active_passage
        if passage is None:
            return
        passage.sample_count += 1
        passage.peak_score = max(passage.peak_score, score)
        passage.max_delta_db = max(passage.max_delta_db, abs(rssi - baseline_mean))
        start_epoch = parse_timestamp(passage.started_at)
        current_epoch = parse_timestamp(timestamp)
        if start_epoch is not None and current_epoch is not None:
            passage.duration_seconds = max(0.0, current_epoch - start_epoch)

        if self.low_streak >= self.end_samples:
            passage.ended_at = timestamp
            self.last_passage = passage
            self.active_passage = None
            self.high_streak = 0
            self.low_streak = 0

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = self.source_data
            updated_at = data.get("updated_at")
            updated_epoch = parse_timestamp(updated_at)
            age = None if updated_epoch is None else max(0.0, time.time() - updated_epoch)
            stale = self.source_error is not None or age is None or age > self.stale_seconds
            current = data.get("current") if isinstance(data.get("current"), dict) else {}
            baseline = data.get("baseline") if isinstance(data.get("baseline"), dict) else {}
            return {
                "available": not stale,
                "stale": stale,
                "source_status": data.get("status", "unknown"),
                "source_updated_at": updated_at,
                "source_age_seconds": round(age, 3) if age is not None else None,
                "source_error": self.source_error,
                "current": {
                    "rssi_dbm": current.get("rssi_dbm"),
                    "vibration_score": current.get("vibration_score"),
                    "motion_level": current.get("motion_level"),
                    "motion_candidate": bool(current.get("motion_candidate", False)),
                },
                "baseline": {
                    "mean_dbm": baseline.get("mean_dbm"),
                    "stddev_db": baseline.get("stddev_db"),
                    "sample_count": baseline.get("sample_count"),
                },
                "passage": {
                    "active": self.active_passage is not None,
                    "count_since_start": self.passage_count,
                    "current": asdict(self.active_passage) if self.active_passage else None,
                    "last": asdict(self.last_passage) if self.last_passage else None,
                },
            }


def _number(value: object, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


class RadarServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: RadarState, api_key: str) -> None:
        super().__init__(address, RadarHandler)
        self.state = state
        self.api_key = api_key


class RadarHandler(BaseHTTPRequestHandler):
    server: RadarServer

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"}, authenticate=True)
            return
        path = urlsplit(self.path).path
        if path == "/api/v1/state":
            self._json(HTTPStatus.OK, self.server.state.snapshot())
        elif path == "/health":
            state = self.server.state.snapshot()
            status = HTTPStatus.OK if state["available"] else HTTPStatus.SERVICE_UNAVAILABLE
            self._json(status, {"ok": state["available"], "stale": state["stale"]})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        scheme, separator, token = value.partition(" ")
        return separator == " " and scheme.lower() == "bearer" and hmac.compare_digest(token, self.server.api_key)

    def _json(self, status: HTTPStatus, body: dict[str, Any], authenticate: bool = False) -> None:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if authenticate:
            self.send_header("WWW-Authenticate", 'Bearer realm="wifi-radar"')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        # Request lines and headers are intentionally not logged.
        return


def read_api_key(key_file: str | None) -> str:
    key = os.environ.get("WIFI_RADAR_API_KEY", "")
    if not key and key_file:
        key = Path(key_file).read_text(encoding="utf-8").strip()
    if len(key) < 16:
        raise ValueError("set WIFI_RADAR_API_KEY or --api-key-file with at least 16 characters")
    return key


def poll(state: RadarState, interval: float, stopped: threading.Event) -> None:
    while not stopped.is_set():
        state.update()
        stopped.wait(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Path to collector JSON (required; no implicit private path)")
    parser.add_argument("--api-key-file", help="File containing the Bearer key; env WIFI_RADAR_API_KEY takes priority")
    parser.add_argument("--bind", default="127.0.0.1", help="Listen address; explicitly use 0.0.0.0 for LAN access")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--stale-seconds", type=float, default=10.0)
    parser.add_argument("--start-score", type=float, default=45.0)
    parser.add_argument("--end-score", type=float, default=35.0)
    parser.add_argument("--start-samples", type=int, default=2)
    parser.add_argument("--end-samples", type=int, default=3)
    args = parser.parse_args()
    if args.poll_seconds <= 0 or args.stale_seconds <= 0 or args.start_samples < 1 or args.end_samples < 1 or not 0 <= args.end_score < args.start_score <= 100:
        parser.error("invalid polling, stale, score, or consecutive-sample settings")

    api_key = read_api_key(args.api_key_file)
    state = RadarState(Path(args.source), args.stale_seconds, args.start_score, args.end_score, args.start_samples, args.end_samples)
    state.update()
    stopped = threading.Event()
    worker = threading.Thread(target=poll, args=(state, args.poll_seconds, stopped), daemon=True)
    worker.start()
    server = RadarServer((args.bind, args.port), state, api_key)
    print(f"wifi-radar bridge listening on {args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        server.server_close()


if __name__ == "__main__":
    main()
