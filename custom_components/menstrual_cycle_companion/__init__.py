"""Menstrual Cycle Companion integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify

from .const import (
    ATTR_CURRENT_PHASE,
    ATTR_HISTORY,
    ATTR_PERIOD_DURATION_DAYS,
    CONF_FRIENDLY_NAME,
    CONF_ICON,
    CONF_PROFILE,
    DEFAULT_NAME,
    DEFAULT_PERIOD_DURATION_DAYS,
    DOMAIN,
    SERVICE_ADD_CYCLE_START,
    SERVICE_ERASE_ALL_HISTORY,
    SERVICE_EXPORT_HISTORY,
    SERVICE_REFRESH_CYCLE_MODEL,
    SERVICE_FIELD_DATE,
    SERVICE_FIELD_END_DATE,
    SERVICE_FIELD_DATES,
    SERVICE_FIELD_DAYS,
    SERVICE_FIELD_ENTITY_ID,
    SERVICE_FIELD_ENTRY_ID,
    SERVICE_FIELD_ERASE_ALL,
    SERVICE_FIELD_FILENAME,
    SERVICE_FIELD_FORMAT,
    SERVICE_FIELD_PROFILE,
    SERVICE_FIELD_START_DATE,
    SERVICE_REMOVE_CYCLE_START,
    SERVICE_SET_CYCLE_RANGE,
    SERVICE_SET_CYCLE_HISTORY,
    SERVICE_SET_PERIOD_DURATION,
    SIGNAL_HISTORY_UPDATED,
    STORAGE_KEY,
)
from .model import normalize_history
from .storage import MenstrualCycleStorage

PLATFORMS: list[Platform] = [Platform.SENSOR]
EXPORT_DIR_NAME = "menstrual_cycle_companion_exports"
MODEL_REFRESH_INTERVAL = timedelta(hours=2)
ATTRIBUTE_UNIQUE_ID_PREFIX = "_attribute_"

_LOGGER = logging.getLogger(__name__)


def _remove_deprecated_sensor_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove child entities that are no longer part of the public sensor set."""
    entity_registry = er.async_get(hass)
    allowed_keys = {
        "next_predicted_start",
        "avg_cycle_length",
        "fertile_window_start",
        "fertile_window_end",
        "days_until_next_start",
        "menstruation_start",
        "menstruation_end",
        "follicular_phase_start",
        "follicular_phase_end",
        "ovulation_start",
        "ovulation_end",
        "ovulation_date",
        "luteal_phase_start",
        "luteal_phase_end",
        ATTR_CURRENT_PHASE,
    }
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id.startswith(f"{entry.entry_id}{ATTRIBUTE_UNIQUE_ID_PREFIX}"):
            continue
        key = unique_id.removeprefix(f"{entry.entry_id}{ATTRIBUTE_UNIQUE_ID_PREFIX}")
        if key not in allowed_keys:
            entity_registry.async_remove(entity_entry.entity_id)


@dataclass(slots=True)
class MenstrualCycleRuntime:
    """Runtime data for one profile."""

    storage: MenstrualCycleStorage
    profile: str
    friendly_name: str
    icon: str
    history: list[str]
    period_duration_days: int
    unregister_midnight_listener: Callable[[], None] | None = None


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _profile_from_entry(entry: ConfigEntry) -> str:
    profile = slugify(str(entry.data.get(CONF_PROFILE, ""))).strip("_")
    return profile or "default"


def _friendly_name_from_entry(entry: ConfigEntry) -> str:
    return str(entry.data.get(CONF_FRIENDLY_NAME) or DEFAULT_NAME).strip() or DEFAULT_NAME


def _icon_from_entry(entry: ConfigEntry) -> str:
    return str(entry.data.get(CONF_ICON, "")).strip()


def _normalize_date_or_raise(value: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as err:
        raise HomeAssistantError(f"Invalid date '{value}', expected YYYY-MM-DD") from err


def _runtime_by_profile(hass: HomeAssistant, profile: str) -> MenstrualCycleRuntime:
    domain_data: dict[str, MenstrualCycleRuntime] = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise HomeAssistantError("No menstrual_cycle_companion config entry loaded")

    wanted = slugify(str(profile)).strip("_")
    for runtime in domain_data.values():
        if runtime.profile == wanted:
            return runtime
    raise HomeAssistantError(f"Unknown profile '{profile}'.")


def _runtime_for_call(hass: HomeAssistant, call: ServiceCall) -> MenstrualCycleRuntime:
    domain_data: dict[str, MenstrualCycleRuntime] = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise HomeAssistantError("No menstrual_cycle_companion config entry loaded")

    profile = call.data.get(SERVICE_FIELD_PROFILE)
    if profile is not None and str(profile).strip():
        return _runtime_by_profile(hass, str(profile))

    entity_id = call.data.get(SERVICE_FIELD_ENTITY_ID)
    if entity_id is not None and str(entity_id).strip():
        state_obj = hass.states.get(str(entity_id).strip())
        if state_obj is None:
            raise HomeAssistantError(f"Unknown entity_id '{entity_id}'.")
        runtime_entry_id = state_obj.attributes.get("entry_id")
        if runtime_entry_id and runtime_entry_id in domain_data:
            return domain_data[runtime_entry_id]
        raise HomeAssistantError(f"Entity '{entity_id}' is not a menstrual_cycle_companion sensor.")

    entry_id = call.data.get(SERVICE_FIELD_ENTRY_ID)
    if entry_id is not None and str(entry_id).strip():
        runtime = domain_data.get(str(entry_id).strip())
        if runtime is not None:
            return runtime
        raise HomeAssistantError(f"Unknown entry_id '{entry_id}'.")

    if len(domain_data) == 1:
        return next(iter(domain_data.values()))

    known = ", ".join(sorted(runtime.profile for runtime in domain_data.values()))
    raise HomeAssistantError(
        f"Multiple profiles configured. Provide '{SERVICE_FIELD_PROFILE}' in service data. Known: {known}"
    )


async def _async_save_and_notify(hass: HomeAssistant, runtime: MenstrualCycleRuntime) -> None:
    runtime.history = normalize_history(runtime.history)
    runtime.period_duration_days = max(1, min(14, int(runtime.period_duration_days)))
    await runtime.storage.async_save(runtime.history, runtime.period_duration_days)
    await _async_refresh_cycle_model(hass, {_entry_id_for_runtime(hass, runtime)})


def _entry_id_for_runtime(hass: HomeAssistant, runtime: MenstrualCycleRuntime) -> str:
    for entry_id, candidate in hass.data.get(DOMAIN, {}).items():
        if candidate is runtime:
            return entry_id
    raise HomeAssistantError(f"Runtime for profile '{runtime.profile}' is not registered.")


def _target_entry_ids_for_call(hass: HomeAssistant, call: ServiceCall | None = None) -> set[str]:
    domain_data: dict[str, MenstrualCycleRuntime] = hass.data.get(DOMAIN, {})
    if not domain_data:
        return set()

    if call is None or not call.data:
        return set(domain_data)

    runtime = _runtime_for_call(hass, call)
    return {_entry_id_for_runtime(hass, runtime)}


async def _async_refresh_cycle_model(hass: HomeAssistant, entry_ids: set[str] | None = None) -> None:
    """Trigger recalculation for loaded cycle sensors and force entity updates."""
    async_dispatcher_send(hass, SIGNAL_HISTORY_UPDATED)

    entity_registry = er.async_get(hass)
    target_entry_ids = entry_ids or set(hass.data.get(DOMAIN, {}))
    entity_ids: list[str] = []

    for entry_id in target_entry_ids:
        for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
            if entity_entry.domain == Platform.SENSOR:
                entity_ids.append(entity_entry.entity_id)

    if entity_ids:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": entity_ids},
            blocking=True,
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration from YAML (not used, config-entry only)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Menstrual Cycle Companion profile from config entry."""
    hass.data.setdefault(DOMAIN, {})

    profile = _profile_from_entry(entry)
    friendly_name = _friendly_name_from_entry(entry)
    icon = _icon_from_entry(entry)

    storage = MenstrualCycleStorage(
        hass,
        key=f"{STORAGE_KEY}.{profile}",
        legacy_key=STORAGE_KEY if profile == "default" else None,
    )
    stored = await storage.async_load()

    runtime = MenstrualCycleRuntime(
        storage=storage,
        profile=profile,
        friendly_name=friendly_name,
        icon=icon,
        history=stored[ATTR_HISTORY],
        period_duration_days=stored.get(ATTR_PERIOD_DURATION_DAYS, DEFAULT_PERIOD_DURATION_DAYS),
    )

    runtime.unregister_midnight_listener = async_track_time_interval(
        hass,
        lambda now: hass.async_create_task(_async_refresh_cycle_model(hass, {entry.entry_id})),
        MODEL_REFRESH_INTERVAL,
    )

    hass.data[DOMAIN][entry.entry_id] = runtime
    _remove_deprecated_sensor_entities(hass, entry)

    async def async_add(call: ServiceCall) -> None:
        await _async_handle_add(hass, call)

    async def async_remove(call: ServiceCall) -> None:
        await _async_handle_remove(hass, call)

    async def async_set_range(call: ServiceCall) -> None:
        await _async_handle_set_range(hass, call)

    async def async_set_history(call: ServiceCall) -> None:
        await _async_handle_set_history(hass, call)

    async def async_set_period_duration(call: ServiceCall) -> None:
        await _async_handle_set_period_duration(hass, call)

    async def async_erase_all_history(call: ServiceCall) -> None:
        await _async_handle_erase_all_history(hass, call)

    async def async_export_history(call: ServiceCall) -> None:
        await _async_handle_export_history(hass, call)

    async def async_refresh_cycle_model(call: ServiceCall) -> None:
        await _async_handle_refresh_cycle_model(hass, call)

    common_profile_field = {
        vol.Optional(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
        vol.Optional(SERVICE_FIELD_PROFILE): cv.string,
        vol.Optional(SERVICE_FIELD_ENTRY_ID): cv.string,
    }

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_CYCLE_START):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_CYCLE_START,
            async_add,
            schema=vol.Schema({**common_profile_field, vol.Required(SERVICE_FIELD_DATE): cv.string}),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REMOVE_CYCLE_START):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_CYCLE_START,
            async_remove,
            schema=vol.Schema({**common_profile_field, vol.Required(SERVICE_FIELD_DATE): cv.string}),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CYCLE_RANGE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CYCLE_RANGE,
            async_set_range,
            schema=vol.Schema(
                {
                    **common_profile_field,
                    vol.Required(SERVICE_FIELD_START_DATE): cv.string,
                    vol.Required(SERVICE_FIELD_END_DATE): cv.string,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CYCLE_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CYCLE_HISTORY,
            async_set_history,
            schema=vol.Schema({**common_profile_field, vol.Required(SERVICE_FIELD_DATES): [cv.string]}),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_PERIOD_DURATION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_PERIOD_DURATION,
            async_set_period_duration,
            schema=vol.Schema(
                {
                    **common_profile_field,
                    vol.Required(SERVICE_FIELD_DAYS): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_ERASE_ALL_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ERASE_ALL_HISTORY,
            async_erase_all_history,
            schema=vol.Schema(
                {
                    **common_profile_field,
                    vol.Required(SERVICE_FIELD_ENTITY_ID): cv.entity_id,
                    vol.Required(SERVICE_FIELD_ERASE_ALL): vol.Equal(True),
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_EXPORT_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_EXPORT_HISTORY,
            async_export_history,
            schema=vol.Schema(
                {
                    **common_profile_field,
                    vol.Optional(SERVICE_FIELD_FORMAT, default="csv"): vol.In(["csv", "txt"]),
                    vol.Optional(SERVICE_FIELD_FILENAME): cv.string,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_CYCLE_MODEL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_CYCLE_MODEL,
            async_refresh_cycle_model,
            schema=vol.Schema(common_profile_field),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime: MenstrualCycleRuntime | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime and runtime.unregister_midnight_listener:
        runtime.unregister_midnight_listener()

    if not hass.data.get(DOMAIN):
        for service in (
            SERVICE_ADD_CYCLE_START,
            SERVICE_REMOVE_CYCLE_START,
            SERVICE_SET_CYCLE_RANGE,
            SERVICE_SET_CYCLE_HISTORY,
            SERVICE_SET_PERIOD_DURATION,
            SERVICE_ERASE_ALL_HISTORY,
            SERVICE_EXPORT_HISTORY,
            SERVICE_REFRESH_CYCLE_MODEL,
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def _async_handle_add(hass: HomeAssistant, call: ServiceCall) -> None:
    runtime = _runtime_for_call(hass, call)
    date_iso = _normalize_date_or_raise(call.data[SERVICE_FIELD_DATE])
    if date_iso not in runtime.history:
        runtime.history.append(date_iso)
    await _async_save_and_notify(hass, runtime)


async def _async_handle_remove(hass: HomeAssistant, call: ServiceCall) -> None:
    runtime = _runtime_for_call(hass, call)
    date_iso = _normalize_date_or_raise(call.data[SERVICE_FIELD_DATE])
    runtime.history = [item for item in runtime.history if item != date_iso]
    await _async_save_and_notify(hass, runtime)


async def _async_handle_set_range(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add every bleeding day in an inclusive, chronologically ordered range."""
    runtime = _runtime_for_call(hass, call)
    start_iso = _normalize_date_or_raise(call.data[SERVICE_FIELD_START_DATE])
    end_iso = _normalize_date_or_raise(call.data[SERVICE_FIELD_END_DATE])
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if end < start:
        raise HomeAssistantError("End date must be on or after start date.")
    if (end - start).days > 90:
        raise HomeAssistantError("Cycle range cannot be longer than 90 days.")

    runtime.history.extend(
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    )
    await _async_save_and_notify(hass, runtime)


async def _async_handle_set_history(hass: HomeAssistant, call: ServiceCall) -> None:
    runtime = _runtime_for_call(hass, call)
    dates = [_normalize_date_or_raise(raw) for raw in call.data[SERVICE_FIELD_DATES]]
    runtime.history = dates
    await _async_save_and_notify(hass, runtime)


async def _async_handle_set_period_duration(hass: HomeAssistant, call: ServiceCall) -> None:
    runtime = _runtime_for_call(hass, call)
    runtime.period_duration_days = int(call.data[SERVICE_FIELD_DAYS])
    await _async_save_and_notify(hass, runtime)


async def _async_handle_erase_all_history(hass: HomeAssistant, call: ServiceCall) -> None:
    entity_id = str(call.data.get(SERVICE_FIELD_ENTITY_ID, "")).strip()
    if not entity_id:
        raise HomeAssistantError(
            "Refusing to erase history. Provide entity_id explicitly for safety."
        )
    runtime = _runtime_for_call(hass, call)
    erase_all = call.data.get(SERVICE_FIELD_ERASE_ALL)
    if erase_all is not True:
        raise HomeAssistantError(
            "Refusing to erase history. Set erase_all: true to confirm destructive action."
        )
    runtime.history = []
    await _async_save_and_notify(hass, runtime)


def _sanitize_export_filename(raw: str) -> str:
    candidate = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in str(raw))
    return candidate.strip("._") or "menstruation_history"


async def _async_handle_export_history(hass: HomeAssistant, call: ServiceCall) -> None:
    runtime = _runtime_for_call(hass, call)
    export_format = str(call.data.get(SERVICE_FIELD_FORMAT, "csv")).lower()
    if export_format not in {"csv", "txt"}:
        raise HomeAssistantError("Invalid format. Use 'csv' or 'txt'.")

    stem = call.data.get(SERVICE_FIELD_FILENAME)
    if stem:
        stem = _sanitize_export_filename(str(stem))
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"menstruation_history_{runtime.profile}_{stamp}"

    extension = ".csv" if export_format == "csv" else ".txt"
    target_dir = Path(hass.config.path(EXPORT_DIR_NAME))
    target_path = target_dir / f"{stem}{extension}"

    history = normalize_history(runtime.history)
    if export_format == "csv":
        content = "date\n" + "\n".join(history) + ("\n" if history else "")
    else:
        content = "\n".join(history) + ("\n" if history else "")

    def _write_file() -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

    await hass.async_add_executor_job(_write_file)
    _LOGGER.info("Exported menstruation history for profile '%s' to %s", runtime.profile, target_path)


async def _async_handle_refresh_cycle_model(hass: HomeAssistant, call: ServiceCall) -> None:
    await _async_refresh_cycle_model(hass, _target_entry_ids_for_call(hass, call))

