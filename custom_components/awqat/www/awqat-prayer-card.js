class AwqatPrayerCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:awqat-prayer-card",
      entities: {
        fajr: "sensor.fajr",
        dhuhr: "sensor.dhuhr",
        asr: "sensor.asr",
        maghrib: "sensor.maghrib",
        isha: "sensor.isha",
        jumua: "sensor.jumua",
        sunrise: "sensor.sunrise",
        next_prayer: "sensor.next_prayer",
        next_prayer_name: "sensor.next_prayer_name",
      },
    };
  }

  setConfig(config) {
    if (!config || !config.entities) {
      throw new Error("Set entities for fajr, dhuhr, asr, maghrib, isha, jumua, sunrise, next_prayer");
    }
    this._config = config;
    this._tick = this._tick.bind(this);
  }

  connectedCallback() {
    if (!this._timer) {
      this._timer = window.setInterval(this._tick, 1000);
    }
  }

  disconnectedCallback() {
    if (this._timer) {
      window.clearInterval(this._timer);
      this._timer = null;
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _tick() {
    if (this._hass) {
      this._render();
    }
  }

  _state(key) {
    const entityId = this._config.entities[key];
    if (!entityId || !this._hass) {
      return null;
    }
    return this._hass.states[entityId] || null;
  }

  _clock(key) {
    const state = this._state(key);
    if (!state || !state.state || state.state === "unknown" || state.state === "unavailable") {
      return "--:--";
    }
    const date = new Date(state.state);
    if (Number.isNaN(date.getTime())) {
      return "--:--";
    }
    return date.toLocaleTimeString(this._hass.locale?.language || undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _nextWhen() {
    const state = this._state("next_prayer");
    if (!state || !state.state) {
      return null;
    }
    const date = new Date(state.state);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  _countdown(target) {
    if (!target) {
      return "--";
    }
    let seconds = Math.max(0, Math.floor((target.getTime() - Date.now()) / 1000));
    const hours = Math.floor(seconds / 3600);
    seconds -= hours * 3600;
    const minutes = Math.floor(seconds / 60);
    seconds -= minutes * 60;
    const pad = (value) => String(value).padStart(2, "0");
    return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`;
  }

  _nextName() {
    const named = this._state("next_prayer_name");
    if (named && named.state && named.state !== "unknown") {
      return named.state;
    }
    const next = this._state("next_prayer");
    return next && next.attributes && next.attributes.prayer_name
      ? next.attributes.prayer_name
      : "Next prayer";
  }

  _mosque() {
    const next = this._state("next_prayer");
    return (next && next.attributes && next.attributes.mosque) || this._config.title || "Prayer times";
  }

  _render() {
    if (!this._config) {
      return;
    }
    const nextWhen = this._nextWhen();
    const nextKey = (this._state("next_prayer") && this._state("next_prayer").attributes.prayer) || "";
    const prayers = [
      ["fajr", "Fajr"],
      ["dhuhr", "Dhuhr"],
      ["asr", "Asr"],
      ["maghrib", "Maghrib"],
      ["isha", "Isha"],
    ];
    if (!this._root) {
      this._root = document.createElement("ha-card");
      this.appendChild(this._root);
    }
    this._root.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          overflow: hidden;
          background:
            radial-gradient(1200px 280px at 10% -10%, color-mix(in srgb, var(--primary-color) 28%, transparent), transparent),
            var(--card-background-color, var(--ha-card-background, #122017));
          color: var(--primary-text-color);
          padding: 18px 18px 14px;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 12px;
          margin-bottom: 16px;
        }
        .mosque {
          font-size: 1.05rem;
          font-weight: 650;
          letter-spacing: 0.01em;
        }
        .label {
          opacity: 0.7;
          font-size: 0.78rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
        }
        .hero {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 12px;
          align-items: end;
          padding: 16px 16px 14px;
          border-radius: 16px;
          background: color-mix(in srgb, var(--primary-color) 14%, var(--card-background-color, #163022));
          margin-bottom: 16px;
        }
        .next-name {
          font-size: 1.8rem;
          font-weight: 720;
          line-height: 1.1;
        }
        .countdown {
          font-variant-numeric: tabular-nums;
          font-size: 1.7rem;
          font-weight: 700;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 8px;
        }
        .salat {
          text-align: center;
          padding: 12px 6px;
          border-radius: 14px;
          background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
        }
        .salat.next {
          background: color-mix(in srgb, var(--primary-color) 22%, transparent);
          box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--primary-color) 55%, transparent);
        }
        .salat .name {
          font-size: 0.75rem;
          opacity: 0.75;
          margin-bottom: 6px;
        }
        .salat .time {
          font-size: 1.02rem;
          font-weight: 650;
          font-variant-numeric: tabular-nums;
        }
        .extras {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          margin-top: 10px;
        }
        .extra {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 14px;
          border-radius: 14px;
          background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
        }
        .extra .name { opacity: 0.75; font-size: 0.85rem; }
        .extra .time { font-weight: 650; font-variant-numeric: tabular-nums; }
        @media (max-width: 640px) {
          .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .hero, .countdown, .next-name { text-align: left; }
          .countdown { font-size: 1.35rem; }
        }
      </style>
      <div class="header">
        <div>
          <div class="label">Awqat</div>
          <div class="mosque">${this._mosque()}</div>
        </div>
      </div>
      <div class="hero">
        <div>
          <div class="label">Next prayer</div>
          <div class="next-name">${this._nextName()}</div>
        </div>
        <div class="countdown">${this._countdown(nextWhen)}</div>
      </div>
      <div class="grid">
        ${prayers
          .map(
            ([key, name]) => `
          <div class="salat${nextKey === key ? " next" : ""}">
            <div class="name">${name}</div>
            <div class="time">${this._clock(key)}</div>
          </div>`
          )
          .join("")}
      </div>
      <div class="extras">
        <div class="extra">
          <span class="name">Sunrise</span>
          <span class="time">${this._clock("sunrise")}</span>
        </div>
        <div class="extra">
          <span class="name">Jumua</span>
          <span class="time">${this._clock("jumua")}</span>
        </div>
      </div>
    `;
  }
}

customElements.define("awqat-prayer-card", AwqatPrayerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "awqat-prayer-card",
  name: "Awqat Prayer Times",
  description: "Five daily prayers, countdown to the next one, Jumua and sunrise.",
  preview: true,
});
