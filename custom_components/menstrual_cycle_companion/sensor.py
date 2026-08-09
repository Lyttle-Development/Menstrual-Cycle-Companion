"""Sensor platform for Menstrual Cycle Companion."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AVG_CYCLE_LENGTH,
    ATTR_BLEEDING_BLOCKS,
    ATTR_DAYS_UNTIL_NEXT_START,
    ATTR_FERTILE_WINDOW_END,
    ATTR_FERTILE_WINDOW_START,
    ATTR_FOLLICULAR_PHASE_END,
    ATTR_FOLLICULAR_PHASE_START,
    ATTR_GROUPED_STARTS,
    ATTR_HISTORY,
    ATTR_LUTEAL_PHASE_END,
    ATTR_LUTEAL_PHASE_START,
    ATTR_MENSTRUATION_END,
    ATTR_MENSTRUATION_START,
    ATTR_NEXT_PREDICTED_START,
    ATTR_OVULATION_DATE,
    ATTR_PERIOD_DURATION_DAYS,
    ATTR_PREDICTED_CYCLE_STARTS,
    DOMAIN,
    SIGNAL_HISTORY_UPDATED,
)
from .model import build_cycle_model


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor from config entry."""
    async_add_entities(
        [
            MenstrualCycleGaugeSensor(hass, entry),
            MenstrualCycleDateSensor(hass, entry, "next_menstruation", "Next Menstruation", ATTR_NEXT_PREDICTED_START, ATTR_NEXT_PREDICTED_START),
            MenstrualCycleDateSensor(hass, entry, "follicular_phase", "Follicular Phase", ATTR_FOLLICULAR_PHASE_START, ATTR_FOLLICULAR_PHASE_END),
            MenstrualCycleDateSensor(hass, entry, "ovulation", "Ovulation", ATTR_OVULATION_DATE, ATTR_OVULATION_DATE),
            MenstrualCycleDateSensor(hass, entry, "luteal_phase", "Luteal Phase", ATTR_LUTEAL_PHASE_START, ATTR_LUTEAL_PHASE_END),
        ],
        True,
    )


class MenstrualCycleGaugeSensor(SensorEntity):
    """Expose cycle state and computed attributes."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_menstruation"
        runtime = self.hass.data[DOMAIN][self._entry.entry_id]
        self._attr_name = runtime.friendly_name
        self._state: str = "neutral"
        self._attrs: dict[str, StateType] = {}
        self._icon: str | None = runtime.icon or None

    async def async_added_to_hass(self) -> None:
        """Register update signals and daily refresh."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_HISTORY_UPDATED, self._handle_runtime_update)
        )
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_daily_refresh,
                hour=0,
                minute=0,
                second=5,
            )
        )
        # Force one recalculation on add/startup so day-based attributes are never stale.
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update sensor from shared runtime."""
        runtime = self.hass.data[DOMAIN][self._entry.entry_id]
        self._attr_name = runtime.friendly_name
        self._icon = runtime.icon or None
        model = build_cycle_model(
            history=runtime.history,
            period_duration_days=runtime.period_duration_days,
            today=dt_util.now().date(),
        )

        self._state = model.state
        has_history = bool(model.history)
        self._attrs = {
            ATTR_HISTORY: model.history,
            ATTR_GROUPED_STARTS: model.grouped_starts,
            ATTR_BLEEDING_BLOCKS: model.bleeding_blocks,
            ATTR_NEXT_PREDICTED_START: model.next_predicted_start,
            ATTR_PREDICTED_CYCLE_STARTS: model.predicted_cycle_starts,
            ATTR_AVG_CYCLE_LENGTH: model.avg_cycle_length,
            "cycle_length_samples": model.cycle_length_samples,
            "cycle_length_variability_days": model.cycle_length_variability,
            "prediction_confidence": model.prediction_confidence,
            "prediction_method": model.prediction_method,
            ATTR_FERTILE_WINDOW_START: model.fertile_window_start,
            ATTR_FERTILE_WINDOW_END: model.fertile_window_end,
            ATTR_DAYS_UNTIL_NEXT_START: model.days_until_next_start,
            ATTR_PERIOD_DURATION_DAYS: model.period_duration_days if has_history else None,
            "period_duration_default_days": runtime.period_duration_days if has_history else None,
            "period_duration_learned_avg_days": model.learned_period_duration_days if has_history else None,
            ATTR_MENSTRUATION_START: model.menstruation_start if has_history else None,
            ATTR_MENSTRUATION_END: model.menstruation_end if has_history else None,
            ATTR_FOLLICULAR_PHASE_START: model.follicular_phase_start if has_history else None,
            ATTR_FOLLICULAR_PHASE_END: model.follicular_phase_end if has_history else None,
            ATTR_OVULATION_DATE: model.ovulation_date if has_history else None,
            ATTR_LUTEAL_PHASE_START: model.luteal_phase_start if has_history else None,
            ATTR_LUTEAL_PHASE_END: model.luteal_phase_end if has_history else None,
            "profile": runtime.profile,
            "entry_id": self._entry.entry_id,
            "friendly_name": runtime.friendly_name,
        }

    @property
    def state(self) -> StateType:
        """Return current cycle state."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return extra attributes for card rendering."""
        return self._attrs

    @property
    def icon(self) -> str | None:
        """Return icon."""
        return self._icon

    @property
    def suggested_display_precision(self) -> int | None:
        """No numeric precision needed."""
        return None

    @property
    def unit_of_measurement(self) -> str | None:
        """No unit for string states."""
        return None

    @property
    def should_poll(self) -> bool:
        """Updates come via dispatcher; no polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Sensor is available when runtime exists."""
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def force_update(self) -> bool:
        """State changes only when model changes."""
        return False

    @property
    def native_value(self) -> StateType:
        """Return sensor state."""
        return self._state

    @property
    def name(self) -> str | None:
        """Return entity name."""
        return self._attr_name

    @property
    def translation_key(self) -> str | None:
        """Translation key for future localization."""
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable by default."""
        return True

    def _handle_runtime_update(self) -> None:
        self.async_schedule_update_ha_state(True)

    def _handle_daily_refresh(self, _now: datetime) -> None:
        self.async_schedule_update_ha_state(True)


class MenstrualCycleDateSensor(SensorEntity):
    """Expose one predicted cycle phase as a date sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        key: str,
        name: str,
        start_attr: str,
        end_attr: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._start_attr = start_attr
        self._end_attr = end_attr
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._value: date | None = None
        self._attrs: dict[str, StateType] = {}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_HISTORY_UPDATED, self._handle_runtime_update)
        )
        self.async_on_remove(
            async_track_time_change(self.hass, self._handle_daily_refresh, hour=0, minute=0, second=5)
        )
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        runtime = self.hass.data[DOMAIN][self._entry.entry_id]
        model = build_cycle_model(
            history=runtime.history,
            period_duration_days=runtime.period_duration_days,
            today=dt_util.now().date(),
        )
        start = getattr(model, self._start_attr, None)
        end = getattr(model, self._end_attr, None)
        try:
            self._value = date.fromisoformat(start) if start else None
        except ValueError:
            self._value = None
        self._attrs = {
            "phase_start": start,
            "phase_end": end,
            "profile": runtime.profile,
            "entry_id": self._entry.entry_id,
        }

    @property
    def native_value(self) -> date | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict[str, StateType]:
        return self._attrs

    @property
    def available(self) -> bool:
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})

    @property
    def should_poll(self) -> bool:
        return False

    def _handle_runtime_update(self) -> None:
        self.async_schedule_update_ha_state(True)

    def _handle_daily_refresh(self, _now: datetime) -> None:
        self.async_schedule_update_ha_state(True)

