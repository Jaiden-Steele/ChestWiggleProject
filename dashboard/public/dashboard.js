console.log("🔥 Dashboard JS loaded");

// ---------------------------------------------------------------------------
// WebSocket Connection
// ---------------------------------------------------------------------------
const ws = new WebSocket("ws://localhost:3000");

// ---------------------------------------------------------------------------
// Data Store
// ---------------------------------------------------------------------------
const dataStore = {
  frequency:   [],
  snr:         [],
  accel:       [],
  waveform:    { time: [], ax: [], ay: [], az: [] }, // raw axes for DC removal
  currentFreq: 0,
  currentSNR:  -30,
  currentAccel: 0,
  currentState: "normal",   // "normal" | "warning" | "fault"
  maxPoints:   50           // trend history length
};

// Rolling mean accumulators for waveform DC removal (matches reference update_waveform)
const DC_WINDOW = 200;
const dcBuf = { ax: [], ay: [], az: [] };

// ---------------------------------------------------------------------------
// Widget Registry
// ---------------------------------------------------------------------------
const widgets = {};

// ---------------------------------------------------------------------------
// WebSocket Handlers
// ---------------------------------------------------------------------------
ws.onopen = () => {
  console.log("✅ WebSocket connected");
  updateAlert("normal", "✓ Connected to RTMA stream");
};

ws.onmessage = (event) => {
  const packet = JSON.parse(event.data);
  const { topic, msg } = packet;
  const now = Date.now();

  // --- Accelerometer raw data (waveform + DC accumulators) ---
  if (topic === "AccelMsg") {
    // Accumulate for running mean (DC removal, same as reference)
    for (const axis of ["ax", "ay", "az"]) {
      dcBuf[axis].push(msg[axis]);
      if (dcBuf[axis].length > DC_WINDOW) dcBuf[axis].shift();
    }

    const meanAx = mean(dcBuf.ax);
    const meanAy = mean(dcBuf.ay);
    const meanAz = mean(dcBuf.az);

    const ax_ac = msg.ax - meanAx;
    const ay_ac = msg.ay - meanAy;
    const az_ac = msg.az - meanAz;
    const mag   = Math.sqrt(ax_ac**2 + ay_ac**2 + az_ac**2);

    const t = msg.t ?? (now / 1000);
    dataStore.waveform.time.push(t);
    dataStore.waveform.mag  = dataStore.waveform.mag  ?? [];
    dataStore.waveform.mag.push(mag);
    dataStore.waveform.z   = dataStore.waveform.z    ?? [];
    dataStore.waveform.z.push(az_ac);

    if (dataStore.waveform.time.length > DC_WINDOW) {
      dataStore.waveform.time.shift();
      dataStore.waveform.mag.shift();
      dataStore.waveform.z.shift();
    }

    updateWidgets("waveform");
  }

  // --- Filtered acceleration amplitude ---
  if (topic === "FilteredAccelMsg" && msg.value !== undefined) {
    // value is now a scalar amplitude (std of filtered window, in mg)
    dataStore.currentAccel = msg.value;
    dataStore.accel.push({ time: now, value: msg.value });
    if (dataStore.accel.length > dataStore.maxPoints) dataStore.accel.shift();
    updateWidgets("accel");
  }

  // --- Estimated frequency ---
  if (topic === "FrequencyMsg" && msg.f_hz !== undefined) {
    dataStore.currentFreq = msg.f_hz;
    dataStore.frequency.push({ time: now, value: msg.f_hz });
    if (dataStore.frequency.length > dataStore.maxPoints) dataStore.frequency.shift();
    updateWidgets("frequency");
  }

  // --- Reference frequency (also feed the frequency trend) ---
  if (topic === "ReferenceFreqMsg" && msg.f_ref !== undefined) {
    dataStore.frequency.push({ time: now, value: msg.f_ref });
    if (dataStore.frequency.length > dataStore.maxPoints) dataStore.frequency.shift();
    updateWidgets("frequency");
  }

  // --- SNR ---
  if (topic === "SNRMsg" && msg.snr_db !== undefined) {
    dataStore.currentSNR = msg.snr_db;
    dataStore.snr.push({ time: now, value: msg.snr_db });
    if (dataStore.snr.length > dataStore.maxPoints) dataStore.snr.shift();
    updateWidgets("snr");
  }

  // --- State from StateMonitor (authoritative) ---
  if (topic === "StateMsg" && msg.state !== undefined) {
    // 0 = NORMAL, 1 = LOW_SIGNAL, 2 = FAULT  (matches state_monitor.py constants)
    const stateMap = {
      0: { css: "normal",  text: "✓ SYSTEM NORMAL — Monitoring Active" },
      1: { css: "warning", text: "⚠ WARNING: LOW SIGNAL QUALITY" },
      2: { css: "fault",   text: "!! FAULT: NO DATA !!" }
    };
    const s = stateMap[msg.state] ?? stateMap[0];
    dataStore.currentState = s.css;
    updateAlert(s.css, s.text);
  }
};

ws.onerror = () => {
  updateAlert("fault", "!! FAULT: CONNECTION ERROR !!");
};

ws.onclose = () => {
  updateAlert("fault", "!! FAULT: NO DATA !!");
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function mean(arr) {
  return arr.length === 0 ? 0 : arr.reduce((a, b) => a + b, 0) / arr.length;
}

// ---------------------------------------------------------------------------
// Alert Banner
// ---------------------------------------------------------------------------
function updateAlert(state, message) {
  const banner = document.getElementById("alertBanner");
  banner.textContent = message;
  banner.className = `alert-banner alert-${state}`;
}

// ---------------------------------------------------------------------------
// Widget Update Dispatch
// ---------------------------------------------------------------------------
function updateWidgets(dataType) {
  Object.values(widgets).forEach(w => {
    if (w.dataType === dataType) w.update();
  });
}

// ---------------------------------------------------------------------------
// Drag-and-Drop onto Canvas
// ---------------------------------------------------------------------------
const canvas = document.getElementById("canvas");

document.querySelectorAll(".tool").forEach(tool => {
  tool.addEventListener("dragstart", e => {
    e.dataTransfer.setData("widgetType", tool.dataset.widget);
  });
});

canvas.addEventListener("dragover", e => e.preventDefault());

canvas.addEventListener("drop", e => {
  e.preventDefault();
  const type = e.dataTransfer.getData("widgetType");
  const rect  = canvas.getBoundingClientRect();
  createWidget(type, e.clientX - rect.left, e.clientY - rect.top);
});

// ---------------------------------------------------------------------------
// Widget Factory
// ---------------------------------------------------------------------------
function createWidget(type, x, y) {
  const id  = crypto.randomUUID();
  const div = document.createElement("div");
  div.className = "widget";
  div.id        = id;
  div.style.left = x + "px";
  div.style.top  = y + "px";

  let widget;
  switch (type) {
    case "frequency-value":
      widget = new ValueWidget(div, "Frequency",       "frequency", " Hz", "#60a5fa"); break;
    case "snr-value":
      widget = new ValueWidget(div, "SNR",             "snr",       " dB", "#10b981"); break;
    case "accel-value":
      widget = new ValueWidget(div, "Filtered Accel",  "accel",     " mg", "#f59e0b"); break;
    case "frequency-trend":
      widget = new TrendWidget(div, "Frequency (10s)", "frequency", "Hz",  "#60a5fa"); break;
    case "snr-trend":
      widget = new TrendWidget(div, "SNR (10s)",       "snr",       "dB",  "#10b981"); break;
    case "waveform":
      widget = new WaveformWidget(div); break;
    default: return;
  }

  widgets[id] = widget;
  makeDraggable(div);
  canvas.appendChild(div);
  widget.update();
}

// ---------------------------------------------------------------------------
// Widget Classes
// ---------------------------------------------------------------------------
class ValueWidget {
  constructor(element, title, dataType, unit, color) {
    this.element  = element;
    this.dataType = dataType;
    this.unit     = unit;

    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">${title}</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-value" style="color:${color}">--</div>`;

    this.valueEl = element.querySelector(".widget-value");
  }

  update() {
    const v =
      this.dataType === "frequency" ? dataStore.currentFreq  :
      this.dataType === "snr"       ? dataStore.currentSNR   :
                                      dataStore.currentAccel;
    this.valueEl.textContent = (typeof v === "number" ? v.toFixed(2) : "--") + this.unit;
  }
}

// ---------------------------------------------------------------------------
class TrendWidget {
  constructor(element, title, dataType, yLabel, color) {
    this.element  = element;
    this.dataType = dataType;

    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">${title}</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-chart"><canvas></canvas></div>`;

    const ctx = element.querySelector("canvas").getContext("2d");
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: yLabel, data: [],
          borderColor: color, backgroundColor: color + "33",
          borderWidth: 2, tension: 0.4, fill: true,
          pointRadius: 2, pointBackgroundColor: color
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { ticks: { color: "#94a3b8", maxTicksLimit: 6 }, grid: { color: "#1e293b" } },
          y: { ticks: { color: "#94a3b8" },                   grid: { color: "#1e293b" } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  update() {
    const data =
      this.dataType === "frequency" ? dataStore.frequency :
      this.dataType === "snr"       ? dataStore.snr       :
                                      dataStore.accel;
    if (!data || data.length === 0) return;

    const now = Date.now();
    this.chart.data.labels              = data.map(p => `-${((now - p.time) / 1000).toFixed(1)}s`);
    this.chart.data.datasets[0].data    = data.map(p => p.value);
    this.chart.update("none");
  }
}

// ---------------------------------------------------------------------------
class WaveformWidget {
  constructor(element) {
    this.element  = element;
    this.dataType = "waveform";

    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">Real-Time Waveform (2 s)</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-chart" style="height:300px"><canvas></canvas></div>`;

    const ctx = element.querySelector("canvas").getContext("2d");
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          { label: "Magnitude", data: [], borderColor: "#2196F3", borderWidth: 2, pointRadius: 0, tension: 0.1 },
          { label: "Z-axis",    data: [], borderColor: "#4CAF50", borderWidth: 2, pointRadius: 0, tension: 0.1 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          x: { ticks: { color: "#94a3b8", maxTicksLimit: 5 }, grid: { color: "#1e293b" } },
          y: { ticks: { color: "#94a3b8" },                   grid: { color: "#1e293b" } }
        },
        plugins: { legend: { labels: { color: "#94a3b8" } } }
      }
    });
  }

  update() {
    const wf = dataStore.waveform;
    if (!wf.time || wf.time.length === 0) return;

    const lastTime  = wf.time[wf.time.length - 1];
    const startTime = lastTime - 2.0;   // show last 2 seconds

    const labels = [], magData = [], zData = [];
    for (let i = 0; i < wf.time.length; i++) {
      if (wf.time[i] >= startTime) {
        labels.push((wf.time[i] - startTime).toFixed(2));
        magData.push(wf.mag[i]);
        zData.push(wf.z[i]);
      }
    }

    this.chart.data.labels           = labels;
    this.chart.data.datasets[0].data = magData;
    this.chart.data.datasets[1].data = zData;
    this.chart.update("none");
  }
}

// ---------------------------------------------------------------------------
// Widget Removal
// ---------------------------------------------------------------------------
function removeWidget(id) {
  const w = widgets[id];
  if (w?.chart) w.chart.destroy();
  delete widgets[id];
  document.getElementById(id)?.remove();
}
window.removeWidget = removeWidget;

// ---------------------------------------------------------------------------
// Drag-within-canvas
// ---------------------------------------------------------------------------
function makeDraggable(div) {
  const header = div.querySelector(".widget-header");
  let offsetX, offsetY, isDragging = false;

  header.onmousedown = (e) => {
    if (e.target.classList.contains("widget-close")) return;
    isDragging = true;
    offsetX = e.offsetX;
    offsetY = e.offsetY;
    div.style.cursor = "grabbing";

    document.onmousemove = (ev) => {
      if (!isDragging) return;
      const rect = canvas.getBoundingClientRect();
      div.style.left = (ev.clientX - rect.left - offsetX) + "px";
      div.style.top  = (ev.clientY - rect.top  - offsetY) + "px";
    };
    document.onmouseup = () => {
      isDragging = false;
      div.style.cursor = "move";
      document.onmousemove = null;
      document.onmouseup  = null;
    };
  };
}