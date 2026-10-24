/* ==========================================================================
   Apex Compute - Frontend Logic
   Pure vanilla JS, no dependencies
   ========================================================================== */

(function () {
  "use strict";

  // ---------- Clock ----------
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    const el = document.getElementById("clock");
    if (el) el.textContent = `${h}:${m}:${s}`;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // ---------- Status Pill ----------
  const statusPill = document.querySelector(".status-pill");
  const statuses = ["Operational", "Degraded", "Critical"];
  let statusIdx = 0;
  setInterval(() => {
    statusIdx = (statusIdx + 1) % statuses.length;
    const name = statuses[statusIdx];
    statusPill.textContent = name;
    statusPill.className = "status-pill";
    if (name === "Operational") {
      statusPill.classList.add("status-ok");
    } else if (name === "Degraded") {
      statusPill.style.background = "rgba(255, 214, 10, 0.1)";
      statusPill.style.color = "#ffd60a";
      statusPill.style.borderColor = "rgba(255, 214, 10, 0.2)";
    } else {
      statusPill.style.background = "rgba(255, 75, 85, 0.1)";
      statusPill.style.color = "#ff4b55";
      statusPill.style.borderColor = "rgba(255, 75, 85, 0.2)";
    }
  }, 8000);

  // ---------- Random Helpers ----------
  function rand(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }
  function clamp(v, min, max) {
    return Math.min(Math.max(v, min), max);
  }

  // ---------- Sparkline Generator ----------
  function initSparkline(id, color) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "sparkline");
    svg.setAttribute("viewBox", "0 0 100 40");
    svg.setAttribute("preserveAspectRatio", "none");

    const gradient = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
    gradient.setAttribute("id", `grad-${id}`);
    gradient.setAttribute("x1", "0%");
    gradient.setAttribute("y1", "0%");
    gradient.setAttribute("x2", "0%");
    gradient.setAttribute("y2", "100%");

    const stop1 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    stop1.setAttribute("offset", "0%");
    stop1.setAttribute("stop-color", color);
    stop1.setAttribute("stop-opacity", "0.8");

    const stop2 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    stop2.setAttribute("offset", "100%");
    stop2.setAttribute("stop-color", color);
    stop2.setAttribute("stop-opacity", "0.1");

    gradient.appendChild(stop1);
    gradient.appendChild(stop2);
    svg.appendChild(gradient);

    const grid = document.createElementNS("http://www.w3.org/2000/svg", "line");
    grid.setAttribute("class", "sparkline-grid");
    grid.setAttribute("x1", "0");
    grid.setAttribute("y1", "20");
    grid.setAttribute("x2", "100");
    grid.setAttribute("y2", "20");
    svg.appendChild(grid);

    const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
    area.setAttribute("class", "sparkline-area");
    svg.appendChild(area);

    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute("class", "sparkline-line");
    svg.appendChild(line);

    const container = document.getElementById(id);
    if (!container) return;
    container.innerHTML = "";
    container.appendChild(svg);

    let values = [];
    for (let i = 0; i < 30; i++) values.push(20 + Math.random() * 40);

    function update() {
      values.push(clamp(values[values.length - 1] + (Math.random() - 0.5) * 15, 10, 90));
      values.shift();

      const points = values.map((v, i) => {
        const x = (i / (values.length - 1)) * 100;
        const y = 40 - (v / 100) * 40;
        return `${x},${y}`;
      }).join(" ");

      const areaPoints = `M0,40 ${points} L100,40 Z`;
      line.setAttribute("d", `M${points}`);
      area.setAttribute("d", areaPoints);
    }

    update();
    setInterval(update, 1500);
  }

  // Initialize sparklines
  initSparkline("cpu-sparkline", "#76b900");
  initSparkline("net-sparkline", "#00a2ff");
  initSparkline("power-sparkline", "#ffd60a");

  // ---------- Random Value Updates ----------
  const valueEls = {
    cpu: document.getElementById("cpu-value"),
    gpu: document.getElementById("gpu-value"),
    mem: document.getElementById("mem-value"),
    disk: document.getElementById("disk-value"),
    netIn: document.getElementById("net-in"),
    netOut: document.getElementById("net-out"),
    power: document.getElementById("power-val"),
    eff: document.getElementById("eff-val"),
    storage: document.getElementById("storage-pct"),
    storageRing: document.getElementById("storage-ring"),
  };

  let storageVal = 68;
  let cpuVal = 42;
  let gpuVal = 31;
  let memVal = 54;
  let diskVal = 47;

  function updateMetrics() {
    // CPU
    cpuVal = clamp(cpuVal + (Math.random() - 0.5) * 8, 10, 95);
    if (valueEls.cpu) valueEls.cpu.textContent = `${Math.round(cpuVal)}%`;

    // GPU
    gpuVal = clamp(gpuVal + (Math.random() - 0.5) * 10, 5, 99);
    if (valueEls.gpu) valueEls.gpu.textContent = `${Math.round(gpuVal)}%`;

    // Memory
    memVal = clamp(memVal + (Math.random() - 0.5) * 6, 30, 88);
    if (valueEls.mem) valueEls.mem.textContent = `${Math.round(memVal)}%`;

    // Disk
    diskVal = clamp(diskVal + (Math.random() - 0.5) * 2, 10, 95);
    if (valueEls.disk) valueEls.disk.textContent = `${Math.round(diskVal)}%`;

    // Network
    const netIn = (Math.random() * 45 + 5).toFixed(1);
    const netOut = (Math.random() * 38 + 3).toFixed(1);
    if (valueEls.netIn) valueEls.netIn.textContent = `${netIn} MB/s`;
    if (valueEls.netOut) valueEls.netOut.textContent = `${netOut} MB/s`;

    // Power
    const powerVal = (Math.random() * 8 + 2.1).toFixed(1);
    const effVal = (Math.random() * 12 + 88).toFixed(1);
    if (valueEls.power) valueEls.power.textContent = `${powerVal} kW`;
    if (valueEls.eff) valueEls.eff.textContent = `${effVal}%`;

    // Storage
    storageVal = clamp(storageVal + (Math.random() - 0.5) * 0.5, 10, 99);
    if (valueEls.storage) valueEls.storage.textContent = `${Math.round(storageVal)}%`;
    if (valueEls.storageRing) {
      const circumference = 2 * Math.PI * 42;
      const offset = circumference - (storageVal / 100) * circumference;
      valueEls.storageRing.style.strokeDashoffset = offset;
    }
  }

  setInterval(updateMetrics, 2000);
  updateMetrics();

  // ---------- Node Bar Animation ----------
  const nodeFills = document.querySelectorAll(".node-fill");
  nodeFills.forEach(fill => {
    const target = fill.style.width;
    fill.style.width = "0%";
    setTimeout(() => {
      fill.style.width = target;
    }, 500 + Math.random() * 1000);
  });

  // ---------- Alert Ticker ----------
  const alertMsgs = [
    "Thermal threshold approached on Node-02",
    "Package deployment complete: v3.4.1",
    "All nodes synchronized",
    "Latency spike detected on Link-07",
    "Scheduled maintenance: Node-05 (02:00 UTC)",
    "SSL certificate renewal in 7 days",
    "New firmware available for Node-04",
  ];
  const alertList = document.querySelector(".alert-list");
  if (alertList) {
    setInterval(() => {
      const msg = alertMsgs[Math.floor(Math.random() * alertMsgs.length)];
      const time = `${String(Math.floor(Math.random() * 24)).padStart(2, "0")}:${String(Math.floor(Math.random() * 60)).padStart(2, "0")}`;
      const item = document.createElement("div");
      item.className = "alert-item alert-ok";
      item.innerHTML = `<span class="alert-time">${time}</span><span class="alert-msg">${msg}</span>`;
      alertList.insertBefore(item, alertList.firstChild);
      if (alertList.children.length > 6) alertList.removeChild(alertList.lastChild);
    }, 6000);
  }

  console.log("Apex Compute UI initialized");
})();
