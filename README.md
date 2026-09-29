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

A **prayer dashboard card** is registered automatically. It shows the five daily prayers, a live countdown to the next one, Jumua, and sunrise.

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
5. Choose separately whether to create **azan**, **iqama**, and **Jumua** automations.
6. If you enabled any of them, pick a speaker for the azan and any TVs or other media players to pause.

Times use the Home Assistant timezone. You can change the automations and media players later in the integration options.

## Automations

Setup asks three separate questions. Each automation is optional:

| Automation | Default | Fires at | Action |
| --- | --- | --- | --- |
| **Azan** | On | Fajr, Dhuhr, Asr, Maghrib, Isha | Pause/mute chosen TVs and other media, play azan on the chosen speaker, notify |
| **Iqama** | Off | Iqama for those five prayers | Pause/mute chosen media, notify |
| **Jumua** | On | Friday Jumua adhan | Same as azan, at Jumua only |

The azan audio uses the mosque's published adhan when Awqat provides one, otherwise a public fallback. The azan speaker is not paused with the TVs.

Removing the mosque also removes these automations. Existing setups that used the older combined toggle keep azan and Jumua on, and iqama off, until you change them in options.

The mosque device also exposes **Adhan / Iqama / Sunrise** triggers, **next prayer** conditions, and a **Refresh prayer times** action, so you can build extra automations from the device page.

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

## Prayer dashboard

On setup the integration tries to add a sidebar dashboard with the **Awqat Prayer Times** card. You can also add the card yourself:

When adding the card in the visual editor, choose a mosque that has already been set up with the Awqat integration. The editor automatically connects that mosque's prayer sensors.

```yaml
type: custom:awqat-prayer-card
title: Mosquée Badr, Lille
entities:
  fajr: sensor.mosquee_badr_lille_fajr
  dhuhr: sensor.mosquee_badr_lille_dhuhr
  asr: sensor.mosquee_badr_lille_asr
  maghrib: sensor.mosquee_badr_lille_maghrib
  isha: sensor.mosquee_badr_lille_isha
  jumua: sensor.mosquee_badr_lille_jumua
  sunrise: sensor.mosquee_badr_lille_sunrise
  next_prayer: sensor.mosquee_badr_lille_next_prayer
  next_prayer_name: sensor.mosquee_badr_lille_next_prayer_name
```

The card module is served at `/awqat-local/awqat-prayer-card.js` and registered as a Lovelace resource when Home Assistant allows it. If your dashboard is YAML-managed, add that URL as a module resource.

## Development

Run the timetable and API tests (no Home Assistant install required):

```bash
python3 -m unittest discover -s tests -v
```

The client talks to the same widget API used by [awqat.fr](https://awqat.fr/): `https://widget.fawzone.net`.
