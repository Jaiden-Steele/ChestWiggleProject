// dashboard/public/dashboard.js
// HFOV RTMA Clinical Dashboard
//
// Long-run robustness fixes:
//   - All data stores use fixed-size circular (ring) buffers implemented
//     as typed Float64Arrays + a head pointer.  Array.shift() at 100 Hz
//     allocates O(N) garbage per tick and causes GC pauses — eliminated.
//   - Chart updates are decoupled from WebSocket messages via
//     requestAnimationFrame.  The browser is asked to render at most once
//     per display frame (~60 Hz) regardless of incoming message rate.
//   - Waveform ring buffer holds exactly 200 slots (2 s at 100 Hz).
//     Trend ring buffers hold 300 slots each (enough for a 60-second view
//     while keeping memory flat for the whole experiment).
//   - DC removal uses an exponential moving average (α = 0.005) instead of
//     a fixed-length rolling mean — constant time, constant memory.
//   - No per-message DOM writes; only the RAF callback touches the DOM.
//   - Fault watchdog: if no AccelMsg arrives for 3 s the banner goes red.

"use strict";

// ─── Ring Buffer ────────────────────────────────────────────────────────────
class RingBuffer {
  constructor(capacity) {
    this.capacity = capacity;
    this.data     = new Float64Array(capacity);
    this.times    = new Float64Array(capacity); // wall-clock ms
    this.head     = 0;   // index of the NEXT write position
    this.count    = 0;   // number of valid entries (≤ capacity)
  }

  push(value, timeMs) {
    this.data[this.head]  = value;
    this.times[this.head] = timeMs;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) this.count++;
  }

  /** Fill arrays `vals` and `tMs` with entries in chronological order. */
  read(vals, tMs) {
    const n    = this.count;
    const cap  = this.capacity;
    const start = this.count < cap ? 0 : this.head;
    for (let i = 0; i < n; i++) {
      const idx = (start + i) % cap;
      vals[i] = this.data[idx];
      tMs[i]  = this.times[idx];
    }
    return n;
  }
}

// ─── Data Store ─────────────────────────────────────────────────────────────
const TREND_CAP    = 300;   // ~60 s at 5 Hz
const WAVEFORM_CAP = 200;   // 2 s at 100 Hz

const store = {
  freq:    new RingBuffer(TREND_CAP),
  snr:     new RingBuffer(TREND_CAP),
  accel:   new RingBuffer(TREND_CAP),
  wfTime:  new Float64Array(WAVEFORM_CAP),   // monotonic seconds from Python
  wfMag:   new Float64Array(WAVEFORM_CAP),
  wfZ:     new Float64Array(WAVEFORM_CAP),
  wfHead:  0,
  wfCount: 0,

  currentFreq:  0,
  currentSNR:   -30,
  currentAccel: 0,
  state:        0,    // 0 NORMAL | 1 LOW_SIGNAL | 2 FAULT
  lastAccelMs:  Date.now(),
};

// Exponential moving average for DC removal (α≈0.005 ≈ 200-sample window)
const DC_ALPHA = 0.005;
const dc = { ax: null, ay: null, az: null };

// ─── WebSocket ───────────────────────────────────────────────────────────────
const ws = new WebSocket("ws://localhost:3000");
ws.onopen  = () => setAlert(0, "✓ Connected to RTMA stream");
ws.onerror = () => setAlert(2, "!! FAULT: CONNECTION ERROR !!");
ws.onclose = () => setAlert(2, "!! FAULT: DISCONNECTED !!");

ws.onmessage = ({ data }) => {
  let packet;
  try { packet = JSON.parse(data); } catch { return; }
  const { topic, msg } = packet;
  const now = Date.now();

  if (topic === "AccelMsg") {
    store.lastAccelMs = now;

    // EMA-based DC removal (gravity)
    if (dc.ax === null) { dc.ax = msg.ax; dc.ay = msg.ay; dc.az = msg.az; }
    dc.ax += DC_ALPHA * (msg.ax - dc.ax);
    dc.ay += DC_ALPHA * (msg.ay - dc.ay);
    dc.az += DC_ALPHA * (msg.az - dc.az);

    const ax_ac = msg.ax - dc.ax;
    const ay_ac = msg.ay - dc.ay;
    const az_ac = msg.az - dc.az;
    const mag   = Math.sqrt(ax_ac*ax_ac + ay_ac*ay_ac + az_ac*az_ac);

    const t   = msg.t ?? (now / 1000);
    const idx = store.wfHead;
    store.wfTime[idx] = t;
    store.wfMag[idx]  = mag;
    store.wfZ[idx]    = az_ac;
    store.wfHead  = (store.wfHead  + 1) % WAVEFORM_CAP;
    if (store.wfCount < WAVEFORM_CAP) store.wfCount++;
  }

  if (topic === "FilteredAccelMsg" && msg.value !== undefined) {
    store.currentAccel = msg.value;
    store.accel.push(msg.value, now);
  }

  if (topic === "FrequencyMsg" && msg.f_hz !== undefined) {
    store.currentFreq = msg.f_hz;
    store.freq.push(msg.f_hz, now);
  }

  if (topic === "SNRMsg" && msg.snr_db !== undefined) {
    store.currentSNR = msg.snr_db;
    store.snr.push(msg.snr_db, now);
  }

  if (topic === "StateMsg" && msg.state !== undefined) {
    store.state = msg.state;
  }
};

// ─── Fault watchdog (3 s, runs independently of WS) ─────────────────────────
setInterval(() => {
  if (Date.now() - store.lastAccelMs > 3000) {
    setAlert(2, "!! FAULT: NO DATA !!");
  }
}, 1000);

// ─── Alert Banner ────────────────────────────────────────────────────────────
const ALERT_CFG = [
  { css: "alert-normal",  text: "✓ SYSTEM NORMAL — Monitoring Active" },
  { css: "alert-warning", text: "⚠ WARNING: LOW SIGNAL QUALITY" },
  { css: "alert-fault",   text: "!! FAULT: NO DATA !!" },
];
let _lastAlertState = -1;
let _customAlert    = null;

function setAlert(state, customText) {
  _customAlert = customText ?? null;
  if (state !== _lastAlertState || customText) {
    const banner = document.getElementById("alertBanner");
    const cfg    = ALERT_CFG[state] ?? ALERT_CFG[0];
    banner.className   = `alert-banner ${cfg.css}`;
    banner.textContent = customText ?? cfg.text;
    _lastAlertState = state;
  }
}

// ─── Widget Registry ─────────────────────────────────────────────────────────
const widgets = {};

// ─── requestAnimationFrame render loop ───────────────────────────────────────
let _rafPending = false;
function scheduleRender() {
  if (_rafPending) return;
  _rafPending = true;
  requestAnimationFrame(() => {
    _rafPending = false;
    // Sync alert banner with authoritative state
    if (_customAlert === null) setAlert(store.state);
    // Update all widgets
    Object.values(widgets).forEach(w => { try { w.render(); } catch {} });
  });
}

// Kick the render loop at ~30 Hz independent of data arrival
setInterval(scheduleRender, 33);

// ─── Drag-and-drop canvas ────────────────────────────────────────────────────
const canvasEl = document.getElementById("canvas");

document.querySelectorAll(".tool").forEach(tool => {
  tool.addEventListener("dragstart", e => {
    e.dataTransfer.setData("widgetType", tool.dataset.widget);
  });
});
canvasEl.addEventListener("dragover", e => e.preventDefault());
canvasEl.addEventListener("drop", e => {
  e.preventDefault();
  const type = e.dataTransfer.getData("widgetType");
  const rect = canvasEl.getBoundingClientRect();
  createWidget(type, e.clientX - rect.left, e.clientY - rect.top);
});

// ─── Widget Factory ───────────────────────────────────────────────────────────
function createWidget(type, x, y) {
  const id  = crypto.randomUUID();
  const div = document.createElement("div");
  div.className  = "widget";
  div.id         = id;
  div.style.left = `${Math.max(0, x)}px`;
  div.style.top  = `${Math.max(0, y)}px`;

  let w;
  switch (type) {
    case "frequency-value":  w = new ValueWidget(div, "Frequency",      "freq",  " Hz", "#60a5fa"); break;
    case "snr-value":        w = new ValueWidget(div, "SNR",            "snr",   " dB", "#10b981"); break;
    case "accel-value":      w = new ValueWidget(div, "Amplitude",      "accel", " mg", "#f59e0b"); break;
    case "frequency-trend":  w = new TrendWidget(div, "Frequency (60s)","freq",  "Hz",  "#60a5fa"); break;
    case "snr-trend":        w = new TrendWidget(div, "SNR (60s)",      "snr",   "dB",  "#10b981"); break;
    case "waveform":         w = new WaveformWidget(div); break;
    default: return;
  }

  widgets[id] = w;
  makeDraggable(div);
  canvasEl.appendChild(div);
}

// ─── Widget Base ─────────────────────────────────────────────────────────────
function widgetHeader(id, title) {
  return `<div class="widget-header">
    <span class="widget-title">${title}</span>
    <span class="widget-close" onclick="removeWidget('${id}')">×</span>
  </div>`;
}

// ─── ValueWidget ─────────────────────────────────────────────────────────────
class ValueWidget {
  constructor(el, title, storeKey, unit, color) {
    this.el       = el;
    this.storeKey = storeKey;
    this.unit     = unit;
    el.innerHTML  = `${widgetHeader(el.id, title)}
      <div class="value-display" style="color:${color}">--</div>`;
    this.display = el.querySelector(".value-display");
  }
  render() {
    const v = store[`current${this.storeKey.charAt(0).toUpperCase() + this.storeKey.slice(1)}`];
    this.display.textContent = typeof v === "number"
      ? v.toFixed(2) + this.unit
      : "--";
  }
}

// ─── TrendWidget ──────────────────────────────────────────────────────────────
// Pre-allocated scratch arrays to avoid per-render allocations
const _tScratch = new Float64Array(TREND_CAP);
const _vScratch = new Float64Array(TREND_CAP);

class TrendWidget {
  constructor(el, title, storeKey, yLabel, color) {
    this.storeKey = storeKey;
    el.innerHTML  = `${widgetHeader(el.id, title)}
      <div class="widget-chart"><canvas></canvas></div>`;

    const ctx = el.querySelector("canvas").getContext("2d");
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: yLabel, data: [],
          borderColor: color, backgroundColor: color + "22",
          borderWidth: 2, tension: 0.3, fill: true,
          pointRadius: 0,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { ticks: { color: "#64748b", maxTicksLimit: 5, font: { size: 10 } },
               grid:  { color: "#1e293b" } },
          y: { ticks: { color: "#94a3b8", font: { size: 11 } },
               grid:  { color: "#1e293b" } }
        },
        plugins: { legend: { display: false } },
        elements: { line: { borderCapStyle: "round" } }
      }
    });
  }

  render() {
    const ring = store[this.storeKey];
    const n    = ring.read(_vScratch, _tScratch);
    if (n === 0) return;

    const now    = Date.now();
    const labels = new Array(n);
    const vals   = new Array(n);
    for (let i = 0; i < n; i++) {
      labels[i] = `-${((now - _tScratch[i]) / 1000).toFixed(0)}s`;
      vals[i]   = _vScratch[i];
    }

    this.chart.data.labels           = labels;
    this.chart.data.datasets[0].data = vals;
    this.chart.update("none");
  }
}

// ─── WaveformWidget ───────────────────────────────────────────────────────────
// Pre-allocated scratch arrays
const _wfT   = new Float64Array(WAVEFORM_CAP);
const _wfMag = new Float64Array(WAVEFORM_CAP);
const _wfZ   = new Float64Array(WAVEFORM_CAP);

class WaveformWidget {
  constructor(el) {
    this.dataType = "waveform";
    el.innerHTML  = `${widgetHeader(el.id, "Real-Time Waveform (2 s)")}
      <div class="widget-chart" style="height:260px"><canvas></canvas></div>`;

    const ctx = el.querySelector("canvas").getContext("2d");
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          { label: "Magnitude", data: [], borderColor: "#3b82f6",
            borderWidth: 2, pointRadius: 0, tension: 0.1 },
          { label: "Z-axis",    data: [], borderColor: "#22c55e",
            borderWidth: 1.5, pointRadius: 0, tension: 0.1, borderDash: [4,2] }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { ticks: { color: "#64748b", maxTicksLimit: 5, font: { size: 10 } },
               grid:  { color: "#1e293b" } },
          y: { ticks: { color: "#94a3b8", font: { size: 11 } },
               grid:  { color: "#1e293b" } }
        },
        plugins: {
          legend: { labels: { color: "#94a3b8", boxWidth: 12, font: { size: 11 } } }
        }
      }
    });
  }

  render() {
    const n = store.wfCount;
    if (n === 0) return;

    // Read ring buffer in chronological order into scratch arrays
    const cap   = WAVEFORM_CAP;
    const start = n < cap ? 0 : store.wfHead;
    for (let i = 0; i < n; i++) {
      const idx  = (start + i) % cap;
      _wfT[i]   = store.wfTime[idx];
      _wfMag[i] = store.wfMag[idx];
      _wfZ[i]   = store.wfZ[idx];
    }

    const tEnd   = _wfT[n - 1];
    const tStart = tEnd - 2.0;

    const labels = [], mag = [], z = [];
    for (let i = 0; i < n; i++) {
      if (_wfT[i] >= tStart) {
        labels.push((_wfT[i] - tStart).toFixed(2));
        mag.push(_wfMag[i]);
        z.push(_wfZ[i]);
      }
    }

    this.chart.data.labels           = labels;
    this.chart.data.datasets[0].data = mag;
    this.chart.data.datasets[1].data = z;
    this.chart.update("none");
  }
}

// ─── Widget Removal ───────────────────────────────────────────────────────────
function removeWidget(id) {
  const w = widgets[id];
  if (w?.chart) w.chart.destroy();
  delete widgets[id];
  document.getElementById(id)?.remove();
}
window.removeWidget = removeWidget;

// ─── Drag inside canvas ───────────────────────────────────────────────────────
function makeDraggable(div) {
  const header = div.querySelector(".widget-header");
  let ox = 0, oy = 0, dragging = false;

  header.addEventListener("mousedown", (e) => {
    if (e.target.classList.contains("widget-close")) return;
    dragging = true;
    ox = e.clientX - div.offsetLeft;
    oy = e.clientY - div.offsetTop;
    div.style.cursor = "grabbing";
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    div.style.left = `${e.clientX - ox}px`;
    div.style.top  = `${e.clientY - oy}px`;
  });

  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    div.style.cursor = "move";
  });
}