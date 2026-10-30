# Agent notes — Wireless Pressure Holding (DPS meter setup)

Handoff written 2026-10-30 at the end of the session that built this folder. Everything
below was verified live against a real meter on this PC unless marked **unverified**.

## Workspace

| Path | Role |
|------|------|
| `C:\Projects\Active\Wireless_Pressure_Holding\` | **Code** (this folder) |
| `C:\Users\Syed.h.Shah\OneDrive - Delta Electronics, Inc\Projects_Onedrive\Wireless_Pressure_Holding\` | Project docs: system deck `Wireless_Pressure_Holding.pptx`, settings deck `DPS_Settings_Guide.pptx`, vendor PDFs, BOM, photos |
| same OneDrive folder → `scan_syed.h.shah_2026-10-30-08-33-15.pdf` | **The Modbus register map** (scan of the sheet from the box). Not available online anywhere. |

## System

DPS-2.5SPD3 pressure switch (RE-ATLANTIS, Taiwan) → RS-485 → **DX-CP24** RS-485↔Bluetooth bridge
→ Bluetooth → **DX-CP11** USB dongle → PC **COM5**.

- **CP11 = WCH CH340** (`USB\VID_1A86&PID_7523`). Windows 11 has no driver for it (problem code 28 / no COM
  port) until **CH341SER.EXE** from wch-ic.com is installed. Every PC that runs the tool needs it.
- The Bluetooth link is transparent (no AT replies while paired). CP24 link LED solid = connected.
- Meter RS-485 wiring: brown V+ 14–28 V, blue COM, black D+, white D−. RS-485 units have no alarm wires,
  so P-1/P-2 effectively just drive the red/green display.
- The meter's RANGE register reports **−1~50 bar** (≈725 PSI FS, ±1.8–3.6 PSI accuracy). The system deck
  says 0–2.5 kPa. Mismatch is unresolved; the user hasn't confirmed which test pressures they need.

## Modbus facts (verified)

- **19200 baud, N-8-2, slave address 0.** The meter answers on address 0 even though 0 is the Modbus
  broadcast id (many off-the-shelf tools refuse to poll 0).
- The PC-side baud must be 19200; the CP24's RS-485 side is fixed at what it was configured to (the CP24's
  datasheet default is 9600, so it was presumably set to 19200). You cannot scan for a meter at another baud
  through this link — a meter at another baud must be changed from its front panel.
- **Read: FC03 only.** FC04 → exception 1. Readable registers: 0x00–0x17 and 0x1C–0x1D only.
- **No serial number / identity.** FC11 and FC2B/0E get no reply; nothing outside the map responds.
- **Writes: FC06 on 16-bit registers works.** FC16 gets no reply at all. FC06 to the low word of a 32-bit
  register → exception 3. FC06 to the high word is **stored without range checking** (this corrupted P-2
  to 131,074,000 once during testing; fixed by writing 0 to 0x16). So the 32-bit registers
  (ANLO, ANHI, CODE, P-1, P-2) are **front-panel only**. Do not experiment with 32-bit writes again.
- 32-bit values are signed, high word first. "Counts" = display value × 10^DP.

| Reg | Name | Reference meter | Notes |
|-----|------|-----------------|-------|
| 0x00 | RANGE | 2 (−1~50 bar) | read-only |
| 0x01 | UNIT | 5 (PSI) | 0 bar,1 kg/cm²,2 kPa,3 MPa,4 mmHg,5 PSI,6 inHg |
| 0x02 | DP | 2 | decimal places 0–4 |
| 0x03 | OUT_T | 2 (D) | 0 H hysteresis, 1 C window, 2 D dual |
| 0x04 | ADDR | 0 | 0–255 |
| 0x05 | BAUD | 0 (19200) | 0 19200,1 9600,2 4800,3 2400 — must match CP24 |
| 0x06 | PARI | 0 (N-8-2) | 0 N82,1 N81,2 E81,3 O81 — must match CP24 |
| 0x07 | LOCK | 0 | panel key lock |
| 0x08 | LCUT | 20 (0.20 PSI) | display low cut, counts |
| 0x09 | IDC_T | 50 (5.0 s) | display/update time ×0.1 s |
| 0x0A | HYS | 0 | counts |
| 0x0B/0x0C | AZERO/ASPAN | 1000/45000 | analog trim — never write |
| 0x0D | CJC | ~330 | internal temp ×0.1 °C, live — never write |
| 0x0E | ANLO | 0 | 32-bit, panel only |
| 0x10 | ANHI | 10000 | 32-bit, panel only |
| 0x12 | CODE | 0 | 32-bit panel pass code, panel only |
| 0x14 | P-1 | 1000 (10.00 PSI) | 32-bit, panel only |
| 0x16 | P-2 | 2000 (20.00 PSI) | 32-bit, panel only |
| 0x1C | DISPLAY | live pressure | 32-bit signed, ÷10^DP |

Factory defaults per the sheet: ADDR 0, BAUD 19200, PARI n82, UNIT bar, DP 2, LCUT 0, IDC_T 0.5 s,
OUT_T H, LOCK no, CODE 0, ANLO 0, ANHI 10000, HYS 0. **Unverified:** the user believes out-of-box meters
ship with different comm settings than the sheet says; no new meter has been tested yet.

## Files

| File | What |
|------|------|
| `dps_setup.py` | Core + CLI (pyserial, hand-rolled Modbus RTU — pymodbus avoided because it treats id 0 as broadcast). `DESIRED` block at top = the defaults (copied from the user's already-configured reference meter; user confirmed those are the defaults). Never writes RANGE/AZERO/ASPAN/CJC/BAUD/PARI; ADDR only via `--new-address`; 32-bit settings are checked and reported as "set from the front panel". `Meter.write_setting` refuses anything not in `LIMITS` (ranges from the register sheet). `INFO` = per-setting help text used by the GUI. `apply_custom()` writes an arbitrary subset of settings. Appends every successful apply to `dps_meters.csv` (next to the script, or next to the exe when frozen). |
| `dps_gui.py` | PyQt6 front end: port picker (auto-selects CH340), address, serial/tag, then two tabs. **Defaults**: "Change address to", Read, Set Defaults. **Settings**: one row per setting (meter value / editor / default / ? info button); editable = UNIT, DP, LCUT, IDC_T, OUT_T, HYS, LOCK, the rest shown read-only; changed rows highlighted, Load defaults / Revert / Write N change(s) with a confirm dialog. Changing DP rescales LCUT/HYS to keep their pressure. Shared log below. Serial work runs in a QThread. Settings-tab writes were tested against a fake meter only, not hardware yet. |
| `build_exe.py` | PyInstaller build via a generated spec that strips unused Qt/SSL files. Default = folder build → `dist\DPS_Setup\DPS_Setup.exe` + `dist\DPS_Setup.zip` (the zip is what gets shared). `--onefile` exists but see gotchas. |
| `dps_meters.csv` | Commissioning log. First row = the reference meter, tag `REFERENCE`. |
| `docs/DPS_Settings_Guide.pptx` | 10-slide guide: what the meter can do, what every setting means, tuning advice, register map. Copy of the one in OneDrive. |
| `docs/DPS-2.5SPD3_Modbus_Register_Sheet.pdf` | Copy of the scanned register-map sheet from the box (the only source for the map). |
| `docs/build_deck.js` | pptxgenjs generator for `DPS_Settings_Guide.pptx` (needs `pptxgenjs react react-dom react-icons sharp` in a local node_modules and the pptx skill's `apply_theme.js`; run with `NODE_PATH` pointing at that node_modules). |

## Commands (run Python from the Bash tool)

```
python dps_setup.py                               # compare meter vs DESIRED, no writes
python dps_setup.py --apply --tag <label serial>  # write differences, verify, log
python dps_setup.py --apply --new-address 3       # also move meter to address 3 (untested on hardware)
python dps_setup.py --address 3 --watch           # live pressure
python dps_gui.py                                 # GUI from source
python build_exe.py                               # rebuild dist\DPS_Setup + zip
```

Python 3.12 at `C:\Users\Syed.h.Shah\AppData\Local\Programs\Python\Python312`; pyserial, PyQt6 6.12,
PyInstaller 6.21 installed.

## Gotchas learned the hard way

- **Trend Micro Apex One** (Defender is passive) quarantines the PyInstaller one-file exe ~15 s after it
  is built, and the one-file exe took ~58 s to open (re-unpacks + AV scan every launch). The folder build
  opens in ~3 s and is left alone. Keep the folder build as the default.
- Build in `%TEMP%\dps_setup_build`, not inside OneDrive — OneDrive sync locks files and rebuilds fail
  with access denied. PyInstaller also cleans dist output by spec name, so two builds sharing a name
  delete each other's output.
- The PowerShell tool hung twice running `python`/`Get-Command python`; the Bash tool works fine.
- Writes go to EEPROM (~100k cycles): the tool only writes settings that differ.

## Open items

1. **New out-of-box meter** — not yet tested. Procedure given to the user: wire to CP24 → Read → if no
   reply, set ADDR 0 / BAUD 19200 / PARI n82 on the front panel (hold ENT 3 s, code 0) → Set Defaults →
   set P-1 10.00 / P-2 20.00 on the panel (hold ▼/A-ADJ 5 s) → Read shows 0 differences.
2. **Serial number in the meter** — not possible via a register. Offered option (not decided): store the
   last 5 digits in CODE from the front panel (readable over RS-485, but it then gates the panel menu).
   If chosen, set `DESIRED['CODE'] = None` and show CODE as the meter ID in the GUI.
3. `--new-address` / "Change address to" has not been exercised on hardware (does the reply come from the
   old or new address?). Needed once several meters share one CP24 (up to 32).
4. Tuning suggestions in the settings deck, not applied: IDC_T 5.0 s → ~1.0 s, LOCK = YES after setup,
   pick a sensor range closer to the hold pressure. User still deciding target values.
5. Possible GUI addition: an address scan ("Find meter") at 19200 for meters not at address 0.
6. Git repo: https://github.com/Hassaan-ECE/DPS_Meter_Setup (public, by the user's choice; includes the
   register sheet PDF and settings deck in `docs/`). `dist/` is git-ignored — share the zip via a Release.
7. Team share: `S:\Engineering\Public\Syed_Hassaan_Shah\DPS_Meter_Setup\` = `DPS_Setup.zip` + `README.md`
   (install steps) + `drivers\CH340\CH341SER.EXE`. After a rebuild, copy the new `dist\DPS_Setup.zip`
   there and bump the date in that README.
