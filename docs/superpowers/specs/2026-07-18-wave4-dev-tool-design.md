# Wave4 Dev Tool — Design Spec

Date: 2026-07-18

## Purpose

A standalone Windows GUI tool for browsing and editing the settings exposed by
`configuration-manager-apk` on a Barco Duvel device over ADB, with support for
selecting among multiple connected ADB devices. Internal QA/dev tool only —
not distributed externally, no code-protection requirement.

## Background: how configuration-manager-apk exposes its data

Investigated from `C:\Project\Wave4\configuration-manager-apk` source. The APK
runs an Android `ContentProvider` at authority
`com.barco.clickshare.configurationmanager.provider`, reachable via
`adb shell content query/insert/update/delete/call` — no root required. Three
URI subtrees:

- **`clickshare/*`** — the app's main key-value config store (arbitrary
  string keys, e.g. `clickshare.button.timeout`), backed by
  `DataManager`/`ClickshareRepository`. Full CRUD:
  - List all (or by prefix): `content query --uri content://<authority>/clickshare/<prefix>`
    with projection `key:value` (empty prefix = everything) — subtree query
    path in `DataManager.readClickshareData(key, isSubTreeQuery=true)`.
  - Read one: `content query --uri content://<authority>/clickshare/<key>`
  - Write: `content update` (existing key) or `content insert` (new key) with
    `--bind value:s:<value>`
  - Delete: `content delete --uri content://<authority>/clickshare/<key>`
  - Bulk export: `content call --uri content://<authority>/clickshare --method export_config`
    returns the full config as JSON in the result bundle (`json` key) — this
    is the APK's own `ConfigExportManager`/`ConfigExportSerializer`, not
    something we reconstruct client-side.
  - The provider masks values whose key contains `KeyPassphrase`, or JSON
    values with a `parameters.password` field, in its own logs — but actual
    `query` results return the real value. No client-side handling needed
    beyond passing values through.
- **`system/*`** — a small, fixed set of OS-level settings/properties, hardcoded
  in `SystemManagerImpl.kt`'s `init {}` block as a `logical name -> real key`
  map. No enumeration API exists; the mapping must be hand-copied into this
  tool and kept in sync manually if the APK adds entries. Two prefixes:
  - `Settings.*` (e.g. `Settings.ScreenOffTimeout` → `Settings.System.SCREEN_OFF_TIMEOUT`,
    `Settings.SetupWizardHasRun` → `Settings.System.SETUP_WIZARD_HAS_RUN`) —
    read/write via `content query`/`content update` on `system/<logical name>`.
  - `Properties.*` (e.g. `Properties.SystemBuildVersion` → `ro.barco.build.version`,
    `Properties.ModelName` → `ro.product.model`, etc.) — **read-only**;
    `SystemManagerImpl.set()` explicitly rejects writes for this prefix
    (logs an error and returns false), so the tool must not offer an edit
    control for these.
- **`mdep/*`** — MDEP-specific properties via `MdepManager`. Supports `get`
  and `set` per key, but there is no enumeration/list API — every key must be
  queried individually. No delete support observed.

Full known `system/*` key list at time of writing (must be kept in sync with
`SystemManagerImpl.kt` if the APK changes):

| Logical key | Backing key | Type | Editable |
|---|---|---|---|
| `Settings.ScreenOffTimeout` | `Settings.System.SCREEN_OFF_TIMEOUT` | system setting | yes |
| `Settings.SetupWizardHasRun` | `Settings.System.SETUP_WIZARD_HAS_RUN` | system setting | yes |
| `Properties.SystemBuildDate` | `ro.system.build.date` | prop | no |
| `Properties.SystemBuildVersion` | `ro.barco.build.version` | prop | no |
| `Properties.SystemBuildMinimalVersion` | `ro.barco.build.minimal_version` | prop | no |
| `Properties.ProductName` | `ro.product.name` | prop | no |
| `Properties.ModelName` | `ro.product.model` | prop | no |
| `Properties.DeviceName` | `ro.product.device` | prop | no |
| `Properties.Brand` | `ro.product.brand` | prop | no |
| `Properties.Manufacturer` | `ro.product.manufacturer` | prop | no |
| `Properties.SN` | `ro.serialno` | prop | no |
| `Properties.BarcoDefaultSN` | `ro.barco.serial_number.default` | prop | no |
| `Properties.BarcoPlatformName` | `ro.barco.platform` | prop | no |
| `Properties.BarcoProductName` | `ro.barco.product` | prop | no |
| `Properties.BarcoArticleNumber` | `persist.barco.article_number` | prop | no |
| `Properties.BarcoFirstBoot` | `persist.barco.firstboot` | prop | no |
| `Properties.BarcoCountryCode` | `persist.barco.country_code` | prop | no |
| `Properties.BarcoPlatform` | `persist.barco.platform` | prop | no |
| `Properties.SysWlan0Mac` | `persist.sys.wlan0.mac` | prop | no |
| `Properties.MdepBuildId` | `ro.mdep.build.id` | prop | no |

## Non-goals

- Not a general ADB file browser / shell.
- Not modifying `mdep/*` list enumeration (no API exists for it).
- No code obfuscation/protection (internal tool).
- No auto-backup or undo history of edited values (per user decision — plain
  Save/Cancel, no confirmation dialog, no local change log).

## Technology choices

- **Packaging**: Python + [pywebview](https://pywebview.flowrl.com/) (UI in
  HTML/CSS/JS, rendered via the OS's built-in WebView2 on Windows) +
  PyInstaller `--onefile`. Produces a single `.exe` with no separate Python
  install or browser runtime needed on the target machine. Rejected
  alternatives: native C++ (matches `src/hid-test` pattern but slower to
  develop, no reuse of Python ADB helpers), C#/.NET self-contained publish
  (clean single-exe story but throws away all existing Python ADB code),
  Electron (bundles a full Chromium+Node runtime — far heavier than needed).
- **Code protection**: none required; PyInstaller bytecode is trivially
  recoverable with tools like `pyinstxtractor` + `decompyle3`, but that's
  acceptable for an internal tool.

## Architecture

```
wave4-dev-tool/
├── app.py                  — pywebview entry point; creates the window,
│                              exposes a Python API object to JS
├── backend/
│   ├── adb_devices.py      — `adb devices -l` parsing, device list/connect
│   ├── config_provider.py  — wraps `adb shell content query/insert/update/
│   │                          delete/call` for the three domains
│   └── models.py           — ConfigEntry(domain, key, value, editable)
├── ui/
│   ├── index.html          — device selector + 3 tabs (ClickShare/System/MDEP)
│   ├── app.js               — calls the exposed Python API, renders table/tree,
│   │                          search filter, Save/Cancel/Delete/Add handlers
│   └── style.css
└── build.bat                — `pyinstaller --onefile --add-data ui;ui app.py`
```

`app.py` registers a Python object via `webview.create_window(..., js_api=Api())`;
JS calls it as `pywebview.api.<method>(...)`. No embedded HTTP server needed.

Backend and UI are the only two layers that know about ADB/`content` command
syntax vs. rendering — `models.ConfigEntry` is the shared contract passed
across the JS bridge as plain JSON.

## Multi-device support

- On launch (and on demand via a "重新掃描" button), `adb_devices.py` runs
  `adb devices -l`, parses serial/model/transport_id for each attached
  device, and populates a dropdown showing `serial (model)`.
- The selected serial is threaded through as `-s <serial>` on every
  subsequent `adb shell content ...` call.
- A manual `IP:port` input triggers `adb connect <ip:port>` before adding
  that target to the dropdown, for TCP/IP-connected units — consistent with
  the `--ip` support pattern already used by `testcases/*.py` in this repo.

## UI layout

```
┌──────────────────────────────────────────────────────┐
│ 裝置: [1882000501 (Hub Pro) ▼]  [重新掃描]            │
├──────────────────────────────────────────────────────┤
│ [ ClickShare ] [ System ] [ MDEP ]        [匯出 JSON] │
├──────────────────────────────────────────────────────┤
│ 搜尋: [___________]                                   │
├──────────────────────────────────────────────────────┤
│ (ClickShare tab: tree, grouped by '.' prefix)         │
│ ▾ clickshare                                          │
│   ▾ button                                            │
│       timeout          30              ✎ 🗑           │
│   ▾ hdmi                                              │
│       autoswitch       true            ✎ 🗑           │
│                                                        │
│ (System/MDEP tabs: flat list, no tree grouping)       │
├──────────────────────────────────────────────────────┤
│ [+ 新增 key]   (ClickShare tab only)                  │
└──────────────────────────────────────────────────────┘
```

- **ClickShare tab**: keys are grouped into a collapsible tree by splitting
  on `.` (client-side only — the backend always returns a flat
  `[{key, value, editable}]` list; `app.js` builds the tree). Only leaf nodes
  (actual keys) show a value and ✎/🗑 controls; intermediate group nodes are
  purely expand/collapse, not editable.
- **System / MDEP tabs**: flat list, no tree grouping (key namespaces there
  are shallow — `Settings.*` / `Properties.*` — a tree would add UI
  complexity for no benefit). System tab auto-loads all keys from the
  hardcoded table above on tab open. MDEP tab has no list API — it's a
  "type a key, query it" form instead of an auto-populated list.
- **Search box**: filters by key name, client-side, live as you type. On the
  ClickShare tree, a match keeps its full ancestor chain expanded and visible;
  non-matching branches collapse/hide.
- **Editing**: click ✎ → that row's value cell becomes an inline text input
  with Save/Cancel buttons. No confirmation dialog, no automatic backup of
  the previous value (per explicit user decision).
- **Delete** (🗑, ClickShare tab only — `content delete` has no equivalent on
  system/mdep): immediate, no confirmation dialog.
- **Add key** (ClickShare tab only): "+ 新增 key" opens a blank row (key +
  value inputs) → Save calls `content insert`.
- `Properties.*` rows on the System tab render without ✎ (grayed out,
  read-only) since the APK itself rejects writes to that prefix.
- **匯出 JSON** button: calls `content call ... --method export_config`,
  writes the returned JSON to a file via a native "Save As" dialog.

## Data flow & error handling

- **List/read**: switching tabs (or explicit refresh) triggers
  `pywebview.api.list_config(domain)` → backend runs the matching
  `content query` → returns `[{key, value, editable}]` → frontend builds the
  tree (ClickShare) or renders the flat table (System/MDEP).
- **Write**: Save calls `pywebview.api.update_config(domain, key, value)` →
  backend runs `content update`; for ClickShare, if the key doesn't exist yet
  it falls back to `content insert`. Returns `{success, error}`; frontend
  updates the row in place or shows an inline error string on that row (no
  modal dialogs).
- **Delete**: `pywebview.api.delete_config(domain, key)` → `content delete`
  (ClickShare only).
- **Device unreachable / adb timeout**: every backend ADB call uses a 5s
  timeout. On failure, the whole table area shows a "無法連接裝置" banner
  instead of rendering an empty table, so a connection failure is never
  mistaken for "no keys configured".
- **MDEP query**: single-key lookup only (`pywebview.api.get_mdep(key)`);
  results can be edited/saved but not deleted (no delete method exists on
  `MdepManager`).

## Testing / verification plan

- Manual verification against a real Duvel device (no automated test harness
  exists in this repo for GUI tools per `CLAUDE.md`).
- Smoke test each domain: list ClickShare tree, edit + save a value, add a
  new key, delete a key, export JSON and diff a couple of values against the
  live query; list System tab and confirm `Properties.*` rows are read-only
  while `Settings.*` rows are editable; MDEP single-key lookup round-trip.
- Multi-device: verify dropdown lists all attached devices correctly and that
  switching the selection changes which device subsequent calls target.
