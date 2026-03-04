console.log("🔥 Dashboard JS loaded");

// --- WebSocket Connection ---
const ws = new WebSocket("ws://localhost:3000");

// --- Data Storage ---
const dataStore = {
  frequency: [],
  snr: [],
  accel: [],
  waveform: { time: [], mag: [], z: [] },
  currentFreq: 0,
  currentSNR: 0,
  currentAccel: 0,
  maxPoints: 50 // Keep last 50 points for trends
};

// --- Widget Management ---
const widgets = {};

// --- WebSocket Handlers ---
ws.onopen = () => {
  console.log("✅ WebSocket connected");
  updateAlert("normal", "Connected to RTMA stream");
};

ws.onmessage = (event) => {
  const packet = JSON.parse(event.data);
  const { topic, msg } = packet;

  const now = Date.now();

  if (topic === "SNRMsg" && msg.snr_db !== undefined) {
    dataStore.currentSNR = msg.snr_db;
    dataStore.snr.push({ time: now, value: msg.snr_db });
    if (dataStore.snr.length > dataStore.maxPoints) dataStore.snr.shift();
    updateWidgets("snr");
  }

  if (topic === "ReferenceFreqMsg" && msg.f_ref !== undefined) {
    dataStore.currentFreq = msg.f_ref;
    dataStore.frequency.push({ time: now, value: msg.f_ref });
    if (dataStore.frequency.length > dataStore.maxPoints) dataStore.frequency.shift();
    updateWidgets("frequency");
  }

  if (topic === "FrequencyMsg" && msg.f_hz !== undefined) {
    dataStore.currentFreq = msg.f_hz;
    dataStore.frequency.push({ time: now, value: msg.f_hz });
    if (dataStore.frequency.length > dataStore.maxPoints) dataStore.frequency.shift();
    updateWidgets("frequency");
  }

  if (topic === "FilteredAccelMsg" && msg.value !== undefined) {
    dataStore.currentAccel = msg.value;
    dataStore.accel.push({ time: now, value: msg.value });
    if (dataStore.accel.length > dataStore.maxPoints) dataStore.accel.shift();
    updateWidgets("accel");
  }

  if (topic === "AccelMsg") {
    const t = msg.t || now / 1000;
    const mag = Math.sqrt(msg.ax**2 + msg.ay**2 + msg.az**2);
    
    dataStore.waveform.time.push(t);
    dataStore.waveform.mag.push(mag);
    dataStore.waveform.z.push(msg.az);
    
    if (dataStore.waveform.time.length > 200) {
      dataStore.waveform.time.shift();
      dataStore.waveform.mag.shift();
      dataStore.waveform.z.shift();
    }
    
    updateWidgets("waveform");
  }

  // Check signal quality for alerts
  if (dataStore.currentSNR < 8.0 && dataStore.currentSNR > -20) {
    updateAlert("warning", "⚠ WARNING: LOW SIGNAL QUALITY");
  } else if (dataStore.currentSNR >= 8.0) {
    updateAlert("normal", "✓ SYSTEM NORMAL - Monitoring Active");
  }
};

ws.onerror = (error) => {
  console.error("❌ WebSocket error:", error);
  updateAlert("fault", "!! FAULT: CONNECTION ERROR !!");
};

ws.onclose = () => {
  console.log("🔌 WebSocket closed");
  updateAlert("fault", "!! FAULT: NO DATA !!");
};

// --- Alert Banner ---
function updateAlert(state, message) {
  const banner = document.getElementById("alertBanner");
  banner.textContent = message;
  banner.className = `alert-banner alert-${state}`;
}

// --- Widget Update Logic ---
function updateWidgets(dataType) {
  Object.values(widgets).forEach(widget => {
    if (widget.dataType === dataType) {
      widget.update();
    }
  });
}

// --- Drag and Drop ---
const canvas = document.getElementById("canvas");
const tools = document.querySelectorAll(".tool");

tools.forEach(tool => {
  tool.addEventListener("dragstart", e => {
    e.dataTransfer.setData("widgetType", tool.dataset.widget);
  });
});

canvas.addEventListener("dragover", e => e.preventDefault());

canvas.addEventListener("drop", e => {
  e.preventDefault();
  const type = e.dataTransfer.getData("widgetType");
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  createWidget(type, x, y);
});

// --- Widget Factory ---
function createWidget(type, x, y) {
  const id = crypto.randomUUID();
  const div = document.createElement("div");
  div.className = "widget";
  div.id = id;
  div.style.left = x + "px";
  div.style.top = y + "px";

  let widget;

  switch(type) {
    case "frequency-value":
      widget = new ValueWidget(div, "Frequency", "frequency", " Hz", "#60a5fa");
      break;
    case "snr-value":
      widget = new ValueWidget(div, "SNR", "snr", " dB", "#10b981");
      break;
    case "accel-value":
      widget = new ValueWidget(div, "Filtered Accel", "accel", "", "#f59e0b");
      break;
    case "frequency-trend":
      widget = new TrendWidget(div, "Frequency Trend (10s)", "frequency", "Hz", "#60a5fa");
      break;
    case "snr-trend":
      widget = new TrendWidget(div, "SNR Trend (10s)", "snr", "dB", "#10b981");
      break;
    case "waveform":
      widget = new WaveformWidget(div);
      break;
    default:
      return;
  }

  widgets[id] = widget;
  makeDraggable(div);
  canvas.appendChild(div);
  widget.update();
}

// --- Widget Classes ---
class ValueWidget {
  constructor(element, title, dataType, unit, color) {
    this.element = element;
    this.dataType = dataType;
    this.unit = unit;
    this.color = color;
    
    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">${title}</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-value" style="color: ${color}">--</div>
    `;
    
    this.valueEl = element.querySelector(".widget-value");
  }
  
  update() {
    let value;
    if (this.dataType === "frequency") value = dataStore.currentFreq;
    else if (this.dataType === "snr") value = dataStore.currentSNR;
    else if (this.dataType === "accel") value = dataStore.currentAccel;
    
    this.valueEl.textContent = value.toFixed(2) + this.unit;
  }
}

class TrendWidget {
  constructor(element, title, dataType, yLabel, color) {
    this.element = element;
    this.dataType = dataType;
    
    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">${title}</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-chart">
        <canvas></canvas>
      </div>
    `;
    
    const ctx = element.querySelector("canvas").getContext("2d");
    
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [{
          label: yLabel,
          data: [],
          borderColor: color,
          backgroundColor: color + "33",
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 2,
          pointBackgroundColor: color
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { 
              color: "#94a3b8",
              maxTicksLimit: 6,
              callback: function(value, index) {
                return index % 10 === 0 ? this.getLabelForValue(value) : '';
              }
            },
            grid: { color: "#1e293b" }
          },
          y: {
            ticks: { color: "#94a3b8" },
            grid: { color: "#1e293b" }
          }
        },
        plugins: {
          legend: { display: false }
        },
        animation: false
      }
    });
  }
  
  update() {
    let data;
    if (this.dataType === "frequency") data = dataStore.frequency;
    else if (this.dataType === "snr") data = dataStore.snr;
    else if (this.dataType === "accel") data = dataStore.accel;
    
    if (!data || data.length === 0) return;
    
    // Calculate time labels (seconds ago)
    const now = Date.now();
    const labels = [];
    const values = [];
    
    data.forEach(point => {
      const secondsAgo = ((now - point.time) / 1000).toFixed(1);
      labels.push(`-${secondsAgo}s`);
      values.push(point.value);
    });
    
    this.chart.data.labels = labels;
    this.chart.data.datasets[0].data = values;
    this.chart.update("none");
  }
}

class WaveformWidget {
  constructor(element) {
    this.element = element;
    this.dataType = "waveform";
    
    element.innerHTML = `
      <div class="widget-header">
        <span class="widget-title">Real-Time Waveform (2s)</span>
        <span class="widget-close" onclick="removeWidget('${element.id}')">×</span>
      </div>
      <div class="widget-chart" style="height: 300px;">
        <canvas></canvas>
      </div>
    `;
    
    const ctx = element.querySelector("canvas").getContext("2d");
    
    this.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Magnitude",
            data: [],
            borderColor: "#2196F3",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.1
          },
          {
            label: "Z-axis",
            data: [],
            borderColor: "#4CAF50",
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            ticks: { 
              color: "#94a3b8", 
              maxTicksLimit: 5,
              callback: function(value, index) {
                return index % 20 === 0 ? this.getLabelForValue(value) : '';
              }
            },
            grid: { color: "#1e293b" }
          },
          y: {
            ticks: { color: "#94a3b8" },
            grid: { color: "#1e293b" }
          }
        },
        plugins: {
          legend: {
            labels: { color: "#94a3b8" }
          }
        },
        animation: false
      }
    });
  }
  
  update() {
    const wf = dataStore.waveform;
    if (wf.time.length === 0) return;
    
    // Show last 2 seconds
    const lastTime = wf.time[wf.time.length - 1];
    const startTime = lastTime - 2;
    
    const labels = [];
    const magData = [];
    const zData = [];
    
    for (let i = 0; i < wf.time.length; i++) {
      if (wf.time[i] >= startTime) {
        labels.push((wf.time[i] - startTime).toFixed(2));
        magData.push(wf.mag[i]);
        zData.push(wf.z[i]);
      }
    }
    
    this.chart.data.labels = labels;
    this.chart.data.datasets[0].data = magData;
    this.chart.data.datasets[1].data = zData;
    this.chart.update("none");
  }
}

// --- Widget Removal ---
function removeWidget(id) {
  const widget = widgets[id];
  if (widget && widget.chart) {
    widget.chart.destroy();
  }
  delete widgets[id];
  document.getElementById(id).remove();
}

// --- Draggable Logic ---
function makeDraggable(div) {
  let offsetX, offsetY;
  let isDragging = false;

  const header = div.querySelector(".widget-header");
  
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
      div.style.top = (ev.clientY - rect.top - offsetY) + "px";
    };

    document.onmouseup = () => {
      isDragging = false;
      div.style.cursor = "move";
      document.onmousemove = null;
      document.onmouseup = null;
    };
  };
}

// Make removeWidget globally accessible
window.removeWidget = removeWidget;