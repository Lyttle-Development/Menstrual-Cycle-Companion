# Menstrual Cycle Companion

A privacy-first Home Assistant custom integration for recording menstrual bleeding days, estimating cycle phases, and exposing the results as sensors.

> This project is for personal tracking and pattern recognition. It is not a medical device, diagnostic tool, contraceptive method, or fertility-planning method. Read [`DISCLAIMER.md`](DISCLAIMER.md) before use.

## What it provides

- One configurable profile and sensor per person.
- Persistent local history in Home Assistant's `.storage` directory.
- Cycle state: `period`, `fertile`, `pms`, or `neutral`.
- Predicted next start, average cycle length, fertile-window dates, and days until the prediction.
- Services for adding, removing, importing, exporting, and clearing history.
- Inclusive cycle start/end date selection from the companion gauge card.
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

Create a profile with a stable profile name such as `anna` and a friendly name such as `Anna`. The resulting sensor is usually similar to `sensor.anna` but the final entity ID is controlled by Home Assistant's entity registry.

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

## Sensor attributes

The sensor state is one of `period`, `fertile`, `pms`, or `neutral`. Useful attributes include:

- `history`
- `grouped_starts`
- `bleeding_blocks`
- `next_predicted_start`
- `avg_cycle_length`
- `fertile_window_start` and `fertile_window_end`
- `days_until_next_start`
- `period_duration_days`
- `period_duration_default_days`
- `period_duration_learned_avg_days`

Predictions are intentionally simple estimates from recent confirmed starts. Record enough history to make the estimates useful, and treat them as approximate.

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

## Daily refresh automation

The integration updates on startup and around midnight. The optional example in [`examples/daily_recalculate_days_until_next_start.yaml`](examples/daily_recalculate_days_until_next_start.yaml) can be imported as an automation if you want an explicit daily refresh.

## Cards

Cards are intentionally distributed separately so the integration remains a standard HACS integration and the frontend package can be updated independently. Install [`menstrual-cycle-companion-cards`](https://github.com/Lyttle-Development/menstrual-cycle-companion-cards) for:

- `custom:menstrual-cycle-gauge-card`
- `custom:menstrual-cycle-heatmap-card`

The cards require this integration and a configured sensor.

The gauge card's calendar editor uses range selection by default: click the
first bleeding day, then click the last bleeding day. The selected interval is
shown immediately, and the completed range is written as confirmed bleeding
days. Set `calendar_selection_mode: toggle` in the card configuration to retain
single-day add/remove behavior.

## Privacy and responsible use

Cycle history is sensitive health information. Keep Home Assistant access restricted, protect backups, and only create or share profiles with informed consent. See [`DISCLAIMER.md`](DISCLAIMER.md) for the full health, privacy, and liability notice.

## Development

The repository includes HACS and Hassfest workflows. Python tests and Home Assistant test fixtures should be added before publishing a stable release. Validate JSON and YAML files and run JavaScript syntax checks in CI.

Before publishing to HACS, set a non-empty description and valid topics in the GitHub repository's **About** settings (at minimum `home-assistant` and `hacs`). The CI workflow currently skips only those two API-managed checks because repository settings cannot be stored in this repository.

## License

MIT. See [`LICENSE`](LICENSE).
