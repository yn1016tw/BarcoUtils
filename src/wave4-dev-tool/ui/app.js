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
  document.getElementById("search-input").addEventListener("input", () => render());
  document.getElementById("add-key-btn").addEventListener("click", onAddKey);
  document.getElementById("mdep-query-btn").addEventListener("click", onMdepQuery);
  await loadDomain("clickshare");
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
  if (domain !== "mdep") {
    loadDomain(domain);
  }
}

function showStatus(msg) {
  const el = document.getElementById("status-banner");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideStatus() {
  document.getElementById("status-banner").classList.add("hidden");
}

async function loadDomain(domain) {
  hideStatus();
  const result = await pywebview.api.list_config(domain);
  if (!result.success) {
    showStatus(result.error || "無法連接裝置");
    state.entries = [];
  } else {
    state.entries = result.entries;
  }
  render();
}

function render() {
  if (state.domain === "clickshare") {
    renderTree(state.entries);
  } else if (state.domain === "system") {
    renderFlatTable(state.entries, "system-table");
  }
}

function buildTree(entries) {
  const root = { children: {} };
  entries.forEach((entry) => {
    const parts = entry.key.split(".");
    let node = root;
    parts.forEach((part, i) => {
      if (!node.children) node.children = {};
      if (!node.children[part]) node.children[part] = {};
      node = node.children[part];
      if (i === parts.length - 1) {
        node.entry = entry;
      }
    });
  });
  return root;
}

function renderTree(entries) {
  const container = document.getElementById("clickshare-tree");
  container.innerHTML = "";
  const filter = document.getElementById("search-input").value.trim().toLowerCase();
  const filtered = filter ? entries.filter((e) => e.key.toLowerCase().includes(filter)) : entries;
  const tree = buildTree(filtered);
  container.appendChild(renderNode(tree));
}

function renderNode(node) {
  const ul = document.createElement("ul");
  Object.entries(node.children || {}).forEach(([name, child]) => {
    const li = document.createElement("li");
    if (child.entry) {
      li.appendChild(renderLeafRow(child.entry));
    }
    if (child.children && Object.keys(child.children).length > 0) {
      const label = document.createElement("span");
      label.className = "tree-group";
      label.textContent = `▾ ${name}`;
      li.appendChild(label);
      li.appendChild(renderNode(child));
    }
    ul.appendChild(li);
  });
  return ul;
}

function renderLeafRow(entry) {
  const row = document.createElement("div");
  row.className = "leaf-row";

  const keyLabel = document.createElement("span");
  keyLabel.className = "leaf-key";
  keyLabel.textContent = entry.key.split(".").pop();
  row.appendChild(keyLabel);

  const valueSpan = document.createElement("span");
  valueSpan.className = "leaf-value";
  valueSpan.textContent = entry.value;
  row.appendChild(valueSpan);

  if (entry.editable) {
    const editBtn = document.createElement("button");
    editBtn.textContent = "✎";
    editBtn.addEventListener("click", () => startEdit(row, entry, valueSpan));
    row.appendChild(editBtn);
  }

  if (entry.domain === "clickshare") {
    const delBtn = document.createElement("button");
    delBtn.textContent = "🗑";
    delBtn.addEventListener("click", () => onDelete(entry.key));
    row.appendChild(delBtn);
  }

  return row;
}

function startEdit(row, entry, valueEl) {
  const input = document.createElement("input");
  input.value = entry.value;

  const saveBtn = document.createElement("button");
  saveBtn.textContent = "Save";
  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "Cancel";

  saveBtn.addEventListener("click", async () => {
    const result = await pywebview.api.update_config(entry.domain, entry.key, input.value);
    if (result.success) {
      entry.value = input.value;
      valueEl.textContent = entry.value;
      row.replaceChild(valueEl, input);
      saveBtn.remove();
      cancelBtn.remove();
    } else {
      showRowError(row, result.error);
    }
  });

  cancelBtn.addEventListener("click", () => {
    row.replaceChild(valueEl, input);
    saveBtn.remove();
    cancelBtn.remove();
  });

  row.replaceChild(input, valueEl);
  row.appendChild(saveBtn);
  row.appendChild(cancelBtn);
}

function showRowError(row, message) {
  let errEl = row.querySelector(".row-error");
  if (!errEl) {
    errEl = document.createElement("span");
    errEl.className = "row-error";
    row.appendChild(errEl);
  }
  errEl.textContent = message || "儲存失敗";
}

async function onDelete(key) {
  const result = await pywebview.api.delete_clickshare(key);
  if (result.success) {
    await loadDomain("clickshare");
  } else {
    showStatus(`刪除失敗: ${result.error}`);
  }
}

async function onAddKey() {
  const key = prompt("新 key 名稱:");
  if (!key) return;
  const value = prompt("初始值:") || "";
  const result = await pywebview.api.insert_clickshare(key, value);
  if (result.success) {
    await loadDomain("clickshare");
  } else {
    showStatus(`新增失敗: ${result.error}`);
  }
}

function renderFlatTable(entries, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  let filtered = entries;
  if (tableId === "system-table") {
    const filter = document.getElementById("search-input").value.trim().toLowerCase();
    filtered = filter ? entries.filter((e) => e.key.toLowerCase().includes(filter)) : entries;
  }
  filtered.forEach((entry) => {
    const tr = document.createElement("tr");

    const keyTd = document.createElement("td");
    keyTd.textContent = entry.key;
    tr.appendChild(keyTd);

    const valueTd = document.createElement("td");
    const valueSpan = document.createElement("span");
    valueSpan.textContent = entry.value;
    valueTd.appendChild(valueSpan);
    tr.appendChild(valueTd);

    const actionTd = document.createElement("td");
    if (entry.editable) {
      const editBtn = document.createElement("button");
      editBtn.textContent = "✎";
      editBtn.addEventListener("click", () => startEdit(valueTd, entry, valueSpan));
      actionTd.appendChild(editBtn);
    }
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}

async function onMdepQuery() {
  const key = document.getElementById("mdep-key-input").value.trim();
  if (!key) return;
  const result = await pywebview.api.get_mdep(key);
  const tbody = document.querySelector("#mdep-table tbody");
  tbody.innerHTML = "";
  if (!result.success) {
    showStatus(result.error);
    return;
  }
  hideStatus();
  renderFlatTable([result.entry], "mdep-table");
}
