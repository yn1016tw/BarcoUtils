const state = {
  serial: null,
  domain: "clickshare",
  entries: [],
};

window.addEventListener("pywebviewready", init);

async function init() {
  await refreshDevices();
  document.getElementById("rescan-btn").addEventListener("click", refreshDevices);
  document.getElementById("connect-ip-btn").addEventListener("click", onConnectIp);
  document.getElementById("device-select").addEventListener("change", onDeviceChange);
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.domain));
  });
}

async function refreshDevices() {
  const devices = await pywebview.api.list_devices();
  const select = document.getElementById("device-select");
  select.innerHTML = "";
  devices.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.serial;
    opt.textContent = `${d.serial} (${d.model})`;
    select.appendChild(opt);
  });
  if (devices.length > 0) {
    state.serial = devices[0].serial;
    await pywebview.api.select_device(state.serial);
  }
}

async function onConnectIp() {
  const ip = document.getElementById("connect-ip-input").value.trim();
  if (!ip) return;
  const result = await pywebview.api.connect_ip(ip);
  if (result.success) {
    await refreshDevices();
  } else {
    showStatus(`連線失敗: ${result.message}`);
  }
}

async function onDeviceChange(e) {
  state.serial = e.target.value;
  await pywebview.api.select_device(state.serial);
}

function switchTab(domain) {
  state.domain = domain;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.domain === domain));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  document.getElementById(`${domain}-panel`).classList.add("active");
  document.getElementById("export-btn").style.display = domain === "clickshare" ? "" : "none";
}

function showStatus(msg) {
  const el = document.getElementById("status-banner");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideStatus() {
  document.getElementById("status-banner").classList.add("hidden");
}
