const ws = new WebSocket("ws://localhost:3000");

const canvas = document.getElementById("canvas");
const tools = document.querySelectorAll(".tool");

let widgets = {};

tools.forEach(tool => {
  tool.addEventListener("dragstart", e => {
    e.dataTransfer.setData("widget", tool.dataset.widget);
  });
});

canvas.addEventListener("dragover", e => e.preventDefault());

canvas.addEventListener("drop", e => {
  const type = e.dataTransfer.getData("widget");
  addWidget(type);
});

function addWidget(type) {
  const id = crypto.randomUUID();

  const div = document.createElement("div");
  div.className = "widget";
  div.id = id;

  if (type === "frequency") {
    div.innerHTML = `<h3>Frequency</h3><span>-- Hz</span>`;
    widgets[id] = { type, element: div.querySelector("span") };
  }

  if (type === "snr") {
    div.innerHTML = `<h3>SNR</h3><span>-- dB</span>`;
    widgets[id] = { type, element: div.querySelector("span") };
  }

  if (type === "error") {
    div.innerHTML = `<h3>Frequency Error</h3><span>-- Hz</span>`;
    widgets[id] = { type, element: div.querySelector("span") };
  }

  canvas.appendChild(div);
}

ws.onmessage = (event) => {
  const { topic, msg } = JSON.parse(event.data);

  Object.values(widgets).forEach(widget => {
    if (topic === "FrequencyMsg" && widget.type === "frequency") {
      widget.element.textContent = msg.frequency_hz.toFixed(2) + " Hz";
    }

    if (topic === "SNRMsg" && widget.type === "snr") {
      widget.element.textContent = msg.snr_db.toFixed(1) + " dB";
      widget.element.style.color = msg.snr_db >= 15 ? "green" : "red";
    }

    if (topic === "FrequencyErrorMsg" && widget.type === "error") {
      widget.element.textContent = msg.error_hz.toFixed(2) + " Hz";
      widget.element.style.color = msg.error_hz <= 0.5 ? "green" : "red";
    }
  });
};

