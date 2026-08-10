# Menstrual Cycle Companion

A privacy-first Home Assistant custom integration for recording menstrual bleeding days, estimating cycle phases, and exposing the results as sensors.

> This project is for personal tracking and pattern recognition. It is not a medical device, diagnostic tool, contraceptive method, or fertility-planning method. Read [`DISCLAIMER.md`](DISCLAIMER.md) before use.

## What it provides

- One configurable profile and one `Menstrual Cycle` device per person.
- A master sensor on that device retains the complete cycle model as attributes.
- Every master-sensor attribute is also exposed as an entity on the same device.
- Persistent local history in Home Assistant's `.storage` directory.
- Cycle state: `period`, `fertile`, `pms`, or `neutral`.
- Predicted next start, average cycle length, fertile-window dates, and days until the prediction.
- Services for adding, removing, importing, exporting, and clearing history.
- Inclusive cycle start/end date selection from the companion gauge card.
- Daily symptom and bleeding-strength logging, product usage statistics, and timer state.
- Optional pregnancy, pre-menarche, menopause, NFP analysis, household inventory, and doctor-report workflows.
- Automatic serving and registration of the expanded companion card set and localized translations.
- A separate companion card repository: [`menstrual-cycle-companion-cards`](https://github.com/Lyttle-Development/menstrual-cycle-companion-cards).

## Install with HACS

1. Open **HACS → Integrations**.
2. Search for **Menstrual Cycle Companion**.
3. Install it and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Menstrual Cycle Companion** and create one profile per person.
6. Install the optional cards from the [cards repository](https://github.com/Lyttle-Development/menstrual-cycle-companion-cards), then add its JavaScript resources as described there.

For an unpublished repository, add each GitHub repository through **HACS → Custom repositories** using category **Integration** for this repository and **Dashboard** for the cards repository.

## Manual installation

Copy `custom_components/menstrual_cycle_companion` into `/config/custom_components/`, restart Home Assistant, and add the integration through the UI. Do not configure it through YAML.

## First setup

Create a profile with a stable profile name such as `anna` and a friendly name such as `Anna`. Home Assistant creates one device using that friendly name. The device contains a master sensor plus entities such as `Next Predicted Start`, `Avg Cycle Length`, and `History`; final entity IDs are controlled by Home Assistant's entity registry. The master sensor is the recommended entity for service calls and retains the complete attribute payload for existing cards.

Add confirmed bleeding days from a card or with a service:

```yaml
action: menstrual_cycle_companion.add_cycle_start
data:
  entity_id: sensor.anna
  date: "2026-08-01"
```

Import history in one operation:

```yaml
action: menstrual_cycle_companion.set_cycle_history
data:
  entity_id: sensor.anna
  dates:
    - "2026-05-03"
    - "2026-05-04"
    - "2026-06-01"
    - "2026-06-02"
    - "2026-07-01"
```

Set a complete cycle range in one operation (both dates are included):

```yaml
action: menstrual_cycle_companion.set_cycle_range
data:
  entity_id: sensor.anna
  start_date: "2026-08-01"
  end_date: "2026-08-05"
```

## Master sensor attributes and entities

The master sensor state is one of `period`, `fertile`, `pms`, or `neutral`. Every attribute below remains available on the master sensor and is also represented by a child entity on the same device:

- `history`
- `grouped_starts`
- `bleeding_blocks`
- `next_predicted_start`
- `predicted_cycle_starts` — configurable future predicted cycle starts
- `avg_cycle_length`
- `cycle_length_samples`
- `cycle_length_variability_days`
- `prediction_confidence` and `prediction_method`
- `fertile_window_start` and `fertile_window_end`
- `days_until_next_start`
- `period_duration_days`
- `period_duration_default_days`
- `period_duration_learned_avg_days`
- `menstruation_start` and `menstruation_end`
- `follicular_phase_start` and `follicular_phase_end`
- `ovulation_date`
- `luteal_phase_start` and `luteal_phase_end`

Date attributes are date sensors. Numeric and text attributes expose their value
directly. Collection attributes (`history`, `grouped_starts`, `bleeding_blocks`,
`predicted_cycle_starts`, and `cycle_length_samples`) expose their item count as
the entity state and retain the complete collection in the entity's `value`
attribute. This is necessary because Home Assistant entity states cannot be
lists or dictionaries.

Predictions are personalized from the person's confirmed start history. The
model uses up to the eight most recent valid cycle intervals, gives newer
cycles more weight, and filters isolated recording outliers. Period duration is
learned from recent bleeding blocks once at least two blocks are available.
The `predicted_cycle_starts` attribute projects the current predicted cycle
length forward for 12 future starts and is recalculated when history changes.
With no interval history, the model uses a clearly marked 28-day fallback;
this is replaced automatically as more entries are recorded. The prediction
metadata attributes expose the sample count, typical variation, method, and
confidence. All phase dates remain estimates, not medical guidance.

## Services

All services accept `entity_id`, `profile`, or `entry_id` when more than one profile exists. Using `entity_id` is recommended.

- `menstrual_cycle_companion.add_cycle_start`
- `menstrual_cycle_companion.remove_cycle_start`
- `menstrual_cycle_companion.set_cycle_range`
- `menstrual_cycle_companion.set_cycle_history`
- `menstrual_cycle_companion.set_period_duration`
- `menstrual_cycle_companion.refresh_cycle_model`
- `menstrual_cycle_companion.export_history`
- `menstrual_cycle_companion.erase_all_history`
- `menstrual_cycle_companion.add_symptom` / `remove_symptom` / `get_symptom`
- `menstrual_cycle_companion.log_product_usage`
- `menstrual_cycle_companion.manage_household_inventory`
- `menstrual_cycle_companion.set_pregnancy_mode` / `set_menarche_mode` / `set_menopause_mode`
- `menstrual_cycle_companion.export_doctor_report`

Deletion requires both an explicit sensor `entity_id` and `erase_all: true`:

```yaml
action: menstrual_cycle_companion.erase_all_history
data:
  entity_id: sensor.anna
  erase_all: true
```

Export a local backup:

```yaml
action: menstrual_cycle_companion.export_history
data:
  entity_id: sensor.anna
  format: csv
  filename: anna_cycle_backup
```

Exports are written to `<config>/menstrual_cycle_companion_exports/`.

## Automatic refresh

The integration recalculates the cycle model when history or period-duration
data changes, on startup, and automatically every two hours. The gauge card
also provides a **Refresh** button for an on-demand recalculation. No separate
Home Assistant automation is required.

## Cards

Cards are intentionally distributed separately so the integration remains a standard HACS integration and the frontend package can be updated independently. Install [`menstrual-cycle-companion-cards`](https://github.com/Lyttle-Development/menstrual-cycle-companion-cards) for:

- `custom:menstrual-cycle-gauge-card` and `custom:menstrual-cycle-heatmap-card`
- Calendar, countdown, compact status, history-row, product-inventory, and statistics cards from the companion cards repository

The cards require this integration and a configured sensor.

The gauge's outer ring uses these calculated boundaries to show the proposed
menstruation, follicular, ovulation, and luteal phases. They are estimates based
on the predicted next start and should not be treated as medical guidance.

The gauge card's calendar editor uses range selection by default: click the
first bleeding day, then click the last bleeding day. The selected interval is
shown immediately, and the completed range is written as confirmed bleeding
days. Set `calendar_selection_mode: toggle` in the card configuration to retain
single-day add/remove behavior.

## Privacy and responsible use

Cycle history is sensitive health information. Keep Home Assistant access restricted, protect backups, and only create or share profiles with informed consent. See [`DISCLAIMER.md`](DISCLAIMER.md) for the full health, privacy, and liability notice.

## Development

The repository includes HACS and Hassfest workflows. Python tests and Home Assistant test fixtures should be added before publishing a stable release. Validate JSON and YAML files and run JavaScript syntax checks in CI.

To publish a HACS-detectable release, update `version.json` (`major`, `minor`, or
`patch`) and push the change to `main`. The publishing workflow synchronizes the
integration manifest, creates a matching `v<major>.<minor>.<patch>` GitHub release,
and HACS can then detect that version.

Before publishing to HACS, set a non-empty description and valid topics in the GitHub repository's **About** settings (at minimum `home-assistant` and `hacs`). The CI workflow currently skips only those two API-managed checks because repository settings cannot be stored in this repository.

## License

MIT. See [`LICENSE`](LICENSE).
