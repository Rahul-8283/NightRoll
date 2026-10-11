"""Metrics in Prometheus text format (Phase 12, tasks 6.2 and 6.3).

A small registry kept in this process's memory: counters, gauges and histograms with labels. The API runs as one
process, so there is nothing to merge. Counters start again at zero when it restarts, which is how Prometheus
expects counters to behave.

Labels are always a short, fixed set of words (a route template, a verdict, a reason code), never an ID, so the
number of series stays small and no student can be picked out of the output.
"""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Iterable

LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

Labels = tuple[str, ...]


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(names: Labels, values: Labels, extra: str = "") -> str:
    pairs = [f'{name}="{_escape(value)}"' for name, value in zip(names, values, strict=True)]
    if extra:
        pairs.append(extra)
    return "{" + ",".join(pairs) + "}" if pairs else ""


def _number(value: float) -> str:
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    return repr(float(value)) if value != int(value) else str(int(value))


class Counter:
    kind = "counter"

    def __init__(self, name: str, help_text: str, labels: Labels = ()) -> None:
        self.name, self.help, self.labels = name, help_text, labels
        self.values: dict[Labels, float] = {}

    def inc(self, *label_values: str, amount: float = 1.0) -> None:
        self.values[label_values] = self.values.get(label_values, 0.0) + amount

    def total(self) -> float:
        return sum(self.values.values())

    def samples(self) -> Iterable[str]:
        for label_values, value in sorted(self.values.items()):
            yield f"{self.name}{_format_labels(self.labels, label_values)} {_number(value)}"


class Gauge:
    kind = "gauge"

    def __init__(self, name: str, help_text: str, labels: Labels = ()) -> None:
        self.name, self.help, self.labels = name, help_text, labels
        self.values: dict[Labels, float] = {}

    def set(self, value: float, *label_values: str) -> None:
        self.values[label_values] = value

    def inc(self, *label_values: str, amount: float = 1.0) -> None:
        self.values[label_values] = self.values.get(label_values, 0.0) + amount

    def dec(self, *label_values: str, amount: float = 1.0) -> None:
        self.inc(*label_values, amount=-amount)

    def samples(self) -> Iterable[str]:
        for label_values, value in sorted(self.values.items()):
            yield f"{self.name}{_format_labels(self.labels, label_values)} {_number(value)}"


class Histogram:
    kind = "histogram"

    def __init__(
        self, name: str, help_text: str, labels: Labels = (), buckets: tuple[float, ...] = LATENCY_BUCKETS
    ) -> None:
        self.name, self.help, self.labels, self.buckets = name, help_text, labels, buckets
        # Per label set: the count in each bucket (not cumulative), the sum, and the total count.
        self.series: dict[Labels, tuple[list[int], list[float]]] = {}

    def observe(self, seconds: float, *label_values: str) -> None:
        counts, totals = self.series.setdefault(label_values, ([0] * (len(self.buckets) + 1), [0.0, 0.0]))
        for index, bound in enumerate(self.buckets):
            if seconds <= bound:
                counts[index] += 1
                break
        else:
            counts[-1] += 1
        totals[0] += seconds
        totals[1] += 1

    def merged(self) -> tuple[list[int], float, int]:
        """Counts, sum and number of observations over every label set."""
        counts = [0] * (len(self.buckets) + 1)
        total_sum, total_count = 0.0, 0
        for series_counts, (series_sum, series_count) in self.series.values():
            counts = [a + b for a, b in zip(counts, series_counts, strict=True)]
            total_sum += series_sum
            total_count += int(series_count)
        return counts, total_sum, total_count

    def quantile(self, q: float) -> float | None:
        """An estimate of the q-th quantile over every label set, by interpolating inside the bucket it falls in."""
        counts, _, total = self.merged()
        if total == 0:
            return None
        target = q * total
        seen = 0
        lower = 0.0
        for index, count in enumerate(counts):
            upper = self.buckets[index] if index < len(self.buckets) else self.buckets[-1]
            if count and seen + count >= target:
                fraction = (target - seen) / count
                return lower + (upper - lower) * fraction
            seen += count
            lower = upper
        return self.buckets[-1]

    def samples(self) -> Iterable[str]:
        for label_values, (counts, (total_sum, total_count)) in sorted(self.series.items()):
            running = 0
            for index, bound in enumerate(self.buckets):
                running += counts[index]
                labels = _format_labels(self.labels, label_values, f'le="{_number(bound)}"')
                yield f"{self.name}_bucket{labels} {running}"
            labels = _format_labels(self.labels, label_values, 'le="+Inf"')
            yield f"{self.name}_bucket{labels} {int(total_count)}"
            yield f"{self.name}_sum{_format_labels(self.labels, label_values)} {_number(total_sum)}"
            yield f"{self.name}_count{_format_labels(self.labels, label_values)} {int(total_count)}"


Metric = Counter | Gauge | Histogram
_registry: list[Metric] = []
_collectors: list[Callable[[], Awaitable[None]]] = []


def register[M: Metric](metric: M) -> M:
    _registry.append(metric)
    return metric


def add_collector(collect: Callable[[], Awaitable[None]]) -> None:
    """An async function run before each scrape to refresh gauges that are read from elsewhere (for example Redis)."""
    _collectors.append(collect)


async def render() -> str:
    for collect in _collectors:
        await collect()
    lines: list[str] = []
    for metric in _registry:
        lines.append(f"# HELP {metric.name} {metric.help}")
        lines.append(f"# TYPE {metric.name} {metric.kind}")
        lines.extend(metric.samples())
    return "\n".join(lines) + "\n"


# The metrics the system reports. Everything else in the code only calls inc/observe/set on these.
http_requests = register(
    Counter(
        "nightroll_http_requests_total", "HTTP requests by route template and status.", ("method", "route", "status")
    )
)
http_latency = register(
    Histogram("nightroll_http_request_duration_seconds", "HTTP request latency by route template.", ("method", "route"))
)
verdicts = register(Counter("nightroll_verdicts_total", "Attendance attempts decided, by verdict.", ("verdict",)))
gate_failures = register(
    Counter("nightroll_gate_failures_total", "Attempts stopped at a gate, by reason code.", ("reason",))
)
stage_latency = register(
    Histogram(
        "nightroll_verify_stage_seconds",
        "Time spent in each stage of a verification: the gates, then face, local, fusion.",
        ("stage",),
    )
)
face_latency = register(
    Histogram("nightroll_face_worker_seconds", "Round trip of one call to the face worker.", ("outcome",))
)
websocket_connections = register(Gauge("nightroll_websocket_connections", "Dashboard live connections currently open."))
scheduler_heartbeat_age = register(
    Gauge(
        "nightroll_scheduler_heartbeat_age_seconds",
        "Seconds since the scheduler last wrote its heartbeat. -1 when it has never been seen.",
    )
)
