"""Cycle calculation model for Menstrual Cycle Companion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from .const import STATE_FERTILE, STATE_NEUTRAL, STATE_PERIOD, STATE_PMS


@dataclass(slots=True)
class CycleModel:
    """Computed cycle values for the sensor attributes."""

    history: list[str]
    grouped_starts: list[str]
    bleeding_blocks: list[dict[str, str | int]]
    next_predicted_start: str | None
    avg_cycle_length: int | None
    cycle_length_samples: list[int]
    cycle_length_variability: int | None
    prediction_confidence: str
    prediction_method: str
    fertile_window_start: str | None
    fertile_window_end: str | None
    days_until_next_start: int | None
    period_duration_days: int
    learned_period_duration_days: int | None
    menstruation_start: str | None
    menstruation_end: str | None
    follicular_phase_start: str | None
    follicular_phase_end: str | None
    ovulation_date: str | None
    luteal_phase_start: str | None
    luteal_phase_end: str | None
    state: str


def normalize_history(history: list[str]) -> list[str]:
    """Normalize and sort history values."""
    normalized: set[str] = set()
    for raw in history:
        try:
            normalized.add(date.fromisoformat(str(raw)).isoformat())
        except ValueError:
            continue
    return sorted(normalized)


def grouped_cycle_starts(days: list[str]) -> list[str]:
    """Group contiguous bleeding entries and return starts."""
    if not days:
        return []

    starts: list[str] = []
    for idx, current in enumerate(days):
        if idx == 0:
            starts.append(current)
            continue

        prev = days[idx - 1]
        diff = (date.fromisoformat(current) - date.fromisoformat(prev)).days
        if diff > 2:
            starts.append(current)

    return starts


def bleeding_blocks(days: list[str]) -> list[list[str]]:
    """Group bleeding days into blocks (contiguous / near-contiguous entries)."""
    if not days:
        return []

    blocks: list[list[str]] = []
    current: list[str] = [days[0]]

    for idx in range(1, len(days)):
        prev = date.fromisoformat(days[idx - 1])
        current_day = date.fromisoformat(days[idx])
        diff = (current_day - prev).days
        if diff <= 2:
            current.append(days[idx])
        else:
            blocks.append(current)
            current = [days[idx]]

    blocks.append(current)
    return blocks


def learned_period_duration(default_days: int, blocks: list[list[str]]) -> tuple[int, int | None]:
    """Learn period duration from recent historical block lengths."""
    default_norm = max(1, min(14, int(default_days)))
    if len(blocks) < 2:
        return default_norm, None

    recent = blocks[-6:]
    lengths = [len(block) for block in recent if block]
    if not lengths:
        return default_norm, None

    learned = round(median(lengths))
    return max(1, min(14, learned)), round(sum(lengths) / len(lengths))


def _valid_cycle_lengths(grouped_starts: list[str]) -> list[int]:
    """Return physiologically plausible intervals between recorded starts."""
    lengths: list[int] = []
    for idx in range(1, len(grouped_starts)):
        diff = (
            date.fromisoformat(grouped_starts[idx])
            - date.fromisoformat(grouped_starts[idx - 1])
        ).days
        if 10 < diff < 80:
            lengths.append(diff)
    return lengths


def _robust_cycle_lengths(lengths: list[int]) -> list[int]:
    """Remove isolated recording errors without discarding normal variation."""
    if len(lengths) < 4:
        return lengths
    center = median(lengths)
    deviations = [abs(value - center) for value in lengths]
    mad = median(deviations)
    tolerance = max(6, 2.5 * mad)
    filtered = [value for value in lengths if abs(value - center) <= tolerance]
    return filtered or lengths


def predict_next_start(
    grouped_starts: list[str],
) -> tuple[str | None, int | None, list[int], int | None, str, str]:
    """Predict the next start from a robust, recent, person-specific baseline."""
    if not grouped_starts:
        return None, None, [], None, "none", "no_history"

    raw_lengths = _valid_cycle_lengths(grouped_starts)
    if not raw_lengths:
        last = date.fromisoformat(grouped_starts[0])
        return (last + timedelta(days=28)).isoformat(), 28, [], None, "default", "low"

    lengths = _robust_cycle_lengths(raw_lengths[-8:])
    # Weight recent cycles more heavily while retaining the person's established baseline.
    weights = list(range(1, len(lengths) + 1))
    predicted_length = round(sum(value * weight for value, weight in zip(lengths, weights)) / sum(weights))
    variability = round(median([abs(value - median(lengths)) for value in lengths])) if len(lengths) > 1 else 0
    confidence = "medium" if len(lengths) < 4 else "high"
    if variability >= 7:
        confidence = "variable"

    next_start = date.fromisoformat(grouped_starts[-1]) + timedelta(days=predicted_length)
    return next_start.isoformat(), predicted_length, lengths, variability, "weighted_recent", confidence


def build_cycle_model(history: list[str], period_duration_days: int, today: date | None = None) -> CycleModel:
    """Build complete cycle model for sensor state + attributes."""
    now = today or date.today()
    normalized = normalize_history(history)

    # Keep model based on confirmed values up to today, but keep full history as attribute.
    base_history = [item for item in normalized if item <= now.isoformat()] or normalized

    blocks = bleeding_blocks(base_history)
    blocks_payload = [
        {
            "start": block[0],
            "end": block[-1],
            "length": len(block),
        }
        for block in blocks
        if block
    ]
    starts = grouped_cycle_starts(base_history)
    (
        next_start,
        avg_cycle,
        cycle_length_samples,
        cycle_length_variability,
        prediction_method,
        prediction_confidence,
    ) = predict_next_start(starts)
    effective_duration, learned_avg_duration = learned_period_duration(period_duration_days, blocks)

    menstruation_start = starts[-1] if starts else None
    menstruation_end: str | None = None
    follicular_start: str | None = None
    follicular_end: str | None = None
    ovulation_date: str | None = None
    luteal_start: str | None = None
    luteal_end: str | None = None
    if menstruation_start and next_start:
        cycle_start = date.fromisoformat(menstruation_start)
        cycle_end = date.fromisoformat(next_start) - timedelta(days=1)
        menstruation_end_date = min(cycle_start + timedelta(days=effective_duration - 1), cycle_end)
        menstruation_end = menstruation_end_date.isoformat()
        follicular_start_date = menstruation_end_date + timedelta(days=1)
        ovulation_candidate = date.fromisoformat(next_start) - timedelta(days=14)
        ovulation_date_value = (
            cycle_end
            if follicular_start_date > cycle_end
            else max(follicular_start_date, min(ovulation_candidate, cycle_end))
        )
        ovulation_date = ovulation_date_value.isoformat()
        follicular_start = follicular_start_date.isoformat()
        follicular_end = (ovulation_date_value - timedelta(days=1)).isoformat()
        luteal_start = min(ovulation_date_value + timedelta(days=1), cycle_end).isoformat()
        luteal_end = cycle_end.isoformat()

    fertile_start: str | None = None
    fertile_end: str | None = None
    days_until: int | None = None

    if next_start:
        next_date = date.fromisoformat(next_start)
        ovulation_day = next_date - timedelta(days=14)
        fertile_start = (ovulation_day - timedelta(days=4)).isoformat()
        fertile_end = (ovulation_day + timedelta(days=1)).isoformat()
        days_until = (next_date - now).days

    state = STATE_NEUTRAL
    if now.isoformat() in set(normalized):
        state = STATE_PERIOD
    elif fertile_start and fertile_end and fertile_start <= now.isoformat() <= fertile_end:
        state = STATE_FERTILE
    elif next_start and abs((date.fromisoformat(next_start) - now).days) <= 1:
        state = STATE_PMS

    return CycleModel(
        history=normalized,
        grouped_starts=starts,
        bleeding_blocks=blocks_payload,
        next_predicted_start=next_start,
        avg_cycle_length=avg_cycle,
        cycle_length_samples=cycle_length_samples,
        cycle_length_variability=cycle_length_variability,
        prediction_confidence=prediction_confidence,
        prediction_method=prediction_method,
        fertile_window_start=fertile_start,
        fertile_window_end=fertile_end,
        days_until_next_start=days_until,
        period_duration_days=effective_duration,
        learned_period_duration_days=learned_avg_duration,
        menstruation_start=menstruation_start,
        menstruation_end=menstruation_end,
        follicular_phase_start=follicular_start,
        follicular_phase_end=follicular_end,
        ovulation_date=ovulation_date,
        luteal_phase_start=luteal_start,
        luteal_phase_end=luteal_end,
        state=state,
    )
