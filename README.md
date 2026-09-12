# Awqat Prayer Times for Home Assistant

Custom integration that pulls **mosque prayer times from [awqat.fr](https://awqat.fr/)**. You choose the mosque during setup. Times follow that mosque's Awqat configuration: calculation method (UOIF, ISNA, custom angles, …), published calendar when the mosque uses one, fixed Dhuhr/Jumua clocks, and iqama delays.

## What you get

Sensors on a device named after the mosque:

| Sensor | Meaning |
| --- | --- |
| Fajr, Sunrise, Dhuhr, Jumua, Asr, Maghrib, Isha | Adhan (timestamp) |
| Iqama … | Iqama, using the mosque's delay after adhan |
| Next prayer / Next prayer name | Upcoming salat (Jumua replaces Dhuhr on Friday) |
| Fetch status | `ok`, `retrying`, or `failed` |
| Last successful fetch / Next fetch | When the timetable was pulled, and when the next pull is due |

You can add several mosques; each becomes its own device.

## How updates work

Awqat does not need to be polled all day. After a successful load, the integration pulls again:

1. **Once after Isha** (last prayer of the day), plus a two-minute buffer.
2. **Again after 02:00** local time, so the new civil day is always refreshed.

If a pull fails, it retries three more times (30s, 1 min, 2 min). After that the **Fetch status** sensor is `failed` and the last good times stay in place until the next scheduled pull (after Isha or after 02:00). Home Assistant startup always pulls immediately so the sensors have data.

A manual pull is available as the `awqat.refresh` service.

## Install

### HACS

After this project is in a Git repository:

1. HACS → Integrations → Custom repositories.
2. Add the repository URL as an **Integration**.
3. Install **Awqat Prayer Times**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/awqat` into your Home Assistant `config/custom_components/` directory and restart.

## Configure

1. Settings → Devices & services → Add integration.
2. Search for **Awqat Prayer Times**.
3. Type a mosque or city (for example `Lille` or `Villeparisis`), and/or enable **Search near Home Assistant location**.
4. Pick the mosque.

Times use the Home Assistant timezone.

## Automations

When you add a mosque, the integration creates three automations on that device (this can be turned off in the setup form):

| Automation | Default | Fires at |
| --- | --- | --- |
| **Adhan** | On | Fajr, Dhuhr, Asr, Maghrib, Isha |
| **Iqama** | Off | Iqama for those five prayers |
| **Jumua** | On | Friday Jumua adhan and iqama |

They send a Home Assistant persistent notification. Open the mosque device or **Settings → Automations** to edit the action (for example play an adhan on a speaker, or notify your phone). Removing the mosque also removes these automations.

The same device also exposes **Adhan / Iqama / Sunrise** triggers, **next prayer** conditions, and a **Refresh prayer times** action, so you can build extra automations from the device page.

Timestamp sensors still work with a time trigger if you prefer:

```yaml
automation:
  - alias: Maghrib reminder
    trigger:
      - platform: time
        at: sensor.mosquee_badr_lille_maghrib
    action:
      - service: notify.mobile_app
        data:
          message: "Maghrib at the mosque"
```

## Development

Run the timetable and API tests (no Home Assistant install required):

```bash
python3 -m unittest discover -s tests -v
```

The client talks to the same widget API used by [awqat.fr](https://awqat.fr/): `https://widget.fawzone.net`.
