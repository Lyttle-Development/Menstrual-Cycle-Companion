"""Constants for the Menstrual Cycle Companion integration."""

from __future__ import annotations

DOMAIN = "menstrual_cycle_companion"
PLATFORMS = ["sensor"]

STORAGE_VERSION = 1
STORAGE_KEY = "menstrual_cycle_companion.history"

CONF_NAME = "name"
CONF_PROFILE = "profile"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_ICON = "icon"
CONF_PERIOD_DURATION_DAYS = "period_duration_days"

DEFAULT_NAME = "Menstrual Cycle"
DEFAULT_PERIOD_DURATION_DAYS = 5

ATTR_HISTORY = "history"
ATTR_GROUPED_STARTS = "grouped_starts"
ATTR_BLEEDING_BLOCKS = "bleeding_blocks"
ATTR_NEXT_PREDICTED_START = "next_predicted_start"
ATTR_PREDICTED_CYCLE_STARTS = "predicted_cycle_starts"
ATTR_AVG_CYCLE_LENGTH = "avg_cycle_length"
ATTR_FERTILE_WINDOW_START = "fertile_window_start"
ATTR_FERTILE_WINDOW_END = "fertile_window_end"
ATTR_DAYS_UNTIL_NEXT_START = "days_until_next_start"
ATTR_PERIOD_DURATION_DAYS = "period_duration_days"
ATTR_MENSTRUATION_START = "menstruation_start"
ATTR_MENSTRUATION_END = "menstruation_end"
ATTR_FOLLICULAR_PHASE_START = "follicular_phase_start"
ATTR_FOLLICULAR_PHASE_END = "follicular_phase_end"
ATTR_OVULATION_DATE = "ovulation_date"
ATTR_OVULATION_START = "ovulation_start"
ATTR_OVULATION_END = "ovulation_end"
ATTR_LUTEAL_PHASE_START = "luteal_phase_start"
ATTR_LUTEAL_PHASE_END = "luteal_phase_end"
ATTR_CURRENT_PHASE = "current_phase"

SERVICE_ADD_CYCLE_START = "add_cycle_start"
SERVICE_REMOVE_CYCLE_START = "remove_cycle_start"
SERVICE_SET_CYCLE_RANGE = "set_cycle_range"
SERVICE_SET_CYCLE_HISTORY = "set_cycle_history"
SERVICE_SET_PERIOD_DURATION = "set_period_duration"
SERVICE_ERASE_ALL_HISTORY = "erase_all_history"
SERVICE_EXPORT_HISTORY = "export_history"
SERVICE_REFRESH_CYCLE_MODEL = "refresh_cycle_model"

SERVICE_FIELD_DATE = "date"
SERVICE_FIELD_START_DATE = "start_date"
SERVICE_FIELD_END_DATE = "end_date"
SERVICE_FIELD_DATES = "dates"
SERVICE_FIELD_DAYS = "days"
SERVICE_FIELD_ERASE_ALL = "erase_all"
SERVICE_FIELD_FORMAT = "format"
SERVICE_FIELD_FILENAME = "filename"
SERVICE_FIELD_PROFILE = "profile"
SERVICE_FIELD_ENTRY_ID = "entry_id"
SERVICE_FIELD_ENTITY_ID = "entity_id"

SIGNAL_HISTORY_UPDATED = "menstrual_cycle_companion_history_updated"

STATE_PERIOD = "period"
STATE_FERTILE = "fertile"
STATE_PMS = "pms"
STATE_NEUTRAL = "neutral"
