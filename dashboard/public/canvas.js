const canvas = document.getElementById("plot");
const ctx = canvas.getContext("2d");

const freqSpan = document.getElementById("freq");
const snrSpan = document.getElementById("snr");

let data = [];

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (data.length === 0) return;

  ctx.fillStyle = "white";
  ctx.font = "16px monospace";
  ctx.fillText(`f = ${data[data.length - 1].toFixed(2)} Hz`, 10, 20);

  if (data.length < 2) return;

  ctx.beginPath();
  ctx.strokeStyle = "#22c55e";
  ctx.lineWidth = 2;

  data.forEach((v, i) => {
    const x = (i / (data.length - 1)) * canvas.width;
    const y = canvas.height - (v / 20.0) * canvas.height;

    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();
}


const ws = new WebSocket("ws://localhost:3000");

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === "FilteredAccelMsg") {
    data.push(msg.value);
    if (data.length > 400) data.shift();
    draw();
  }

  if (msg.type === "FrequencyMsg") {
    freqSpan.textContent = msg.f_hz.toFixed(2);
  }

  if (msg.type === "SNRMsg") {
    snrSpan.textContent = msg.snr_db.toFixed(1);
  }
};
