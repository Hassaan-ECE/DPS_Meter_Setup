const pptxgen = require('pptxgenjs');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const fa = require('react-icons/fa');
const { applyTheme } = require('C:/Users/Syed.h.Shah/.claude/skills/synced/a5f81319-1b73-48f3-9ecf-737ed16788b5_808fc2ce-bc57-405b-a599-c15ec6603679/pptx/scripts/apply_theme.js');

const OUT = process.argv[2] || 'DPS_Settings_Guide.pptx';

const THEME = {
  name: 'DPS Gauge',
  headFontFace: 'Arial',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1F2A30', lt1: 'FFFFFF', dk2: '263238', lt2: 'EEF2F3',
    accent1: '19C37D', accent2: 'E53935', accent3: 'F2A900',
    accent4: '546E7A', accent5: '9FB3BC', accent6: '10191E',
    hlink: '19C37D', folHlink: '546E7A',
  },
};
const H = THEME.colors;
const LED = 'Courier New';

async function icon(Comp, color) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: '#' + color, size: 256 }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toBuffer();
  return 'image/png;base64,' + buf.toString('base64');
}

(async () => {
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5
  pres.title = 'DPS-2.5SPD3 Settings Guide';
  pres.author = 'Syed Hassaan Shah';
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: 'TITLE',
    background: { color: H.dk2 },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.8, y: 1.9, w: 7.4, h: 2.0, fontSize: 44, bold: true, color: C.background1, valign: 'bottom', align: 'left', margin: 0 }, text: '' } },
      { placeholder: { options: { name: 'body', type: 'body', x: 0.8, y: 4.15, w: 7.4, h: 1.3, fontSize: 20, color: C.accent5, valign: 'top', margin: 0 }, text: '' } },
    ],
  });

  pres.defineSlideMaster({
    title: 'CONTENT',
    background: { color: H.lt1 },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 0.35, w: 12.1, h: 0.75, fontSize: 36, bold: true, color: C.text1, valign: 'middle', align: 'left', margin: 0 }, text: '' } },
      { placeholder: { options: { name: 'body', type: 'body', x: 0.6, y: 1.12, w: 12.1, h: 0.5, fontSize: 16, color: C.accent4, valign: 'top', margin: 0 }, text: '' } },
      { text: { text: 'DPS-2.5SPD3 Settings Guide', options: { x: 0.6, y: 6.98, w: 6, h: 0.3, fontSize: 10, color: C.accent4, margin: 0 } } },
    ],
    slideNumber: { x: 12.2, y: 6.98, w: 0.5, h: 0.3, fontSize: 10, color: H.accent4, align: 'right' },
  });

  // Motif: a black LED readout like the meter's own display.
  function led(slide, name, x, y, w, h, value, unit, fs, color) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.accent6 }, line: { type: 'none' }, objectName: name });
    const runs = [{ text: value, options: { fontFace: LED, bold: true, fontSize: fs, color: color || C.accent1 } }];
    if (unit) runs.push({ text: ' ' + unit, options: { fontFace: LED, bold: true, fontSize: Math.max(12, Math.round(fs * 0.5)), color: C.accent5 } });
    slide.addText(runs, { x, y, w, h, align: 'center', valign: 'middle', margin: 0, isTextBox: true, objectName: name + ' value' });
  }

  function iconCircle(slide, name, data, x, y, d) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent6 }, line: { type: 'none' }, objectName: name });
    const pad = d * 0.25;
    slide.addImage({ data, x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, altText: name });
  }

  function card(slide, name, x, y, w, h, dark) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: dark ? C.accent6 : C.background2 }, line: { type: 'none' }, objectName: name });
  }

  const content = (section, title, sub) => {
    const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
    s.addText(title, { placeholder: 'title' });
    s.addText(sub, { placeholder: 'body', bullet: false });
    return s;
  };

  const green = H.accent1;
  const I = {
    gauge: await icon(fa.FaTachometerAlt, green),
    ruler: await icon(fa.FaRulerHorizontal, green),
    light: await icon(fa.FaTrafficLight, green),
    bell: await icon(fa.FaBell, green),
    wave: await icon(fa.FaWaveSquare, green),
    net: await icon(fa.FaNetworkWired, green),
    tower: await icon(fa.FaBroadcastTower, green),
    usb: await icon(fa.FaUsb, green),
    laptop: await icon(fa.FaLaptop, green),
  };

  // 1. Title ---------------------------------------------------------------
  pres.addSection({ title: 'Overview' });
  let s = pres.addSlide({ masterName: 'TITLE', sectionTitle: 'Overview' });
  s.addText('DPS-2.5SPD3 Settings Guide', { placeholder: 'title' });
  s.addText('Wireless Pressure Holding: what the meter can do, what each setting means, and what to tune', { placeholder: 'body', bullet: false });
  led(s, 'Live reading', 8.9, 2.5, 3.6, 1.5, '0.00', 'PSI', 48);
  s.addText('Read over RS-485 / Bluetooth, Oct 30 2026', { x: 8.9, y: 4.15, w: 3.6, h: 0.4, fontSize: 12, color: C.accent5, align: 'center', margin: 0, isTextBox: true });

  // 2. Capabilities ----------------------------------------------------------
  s = content('Overview', 'What the meter can do', 'A pressure switch with a display, two alarms and optional outputs; RS-485 is how we use it');
  const caps = [
    [I.gauge, 'Measures pressure', 'Our unit: −1 to 50 bar (≈ −14.5 to 725 PSI), accuracy 0.25–0.5% of full scale.'],
    [I.ruler, 'Seven display units', 'bar, kg/cm², kPa, MPa, mmHg, PSI, inHg. Our meters are set to PSI.'],
    [I.light, 'Red / green display', 'The digits change color when the alarm state changes: a built-in pass/fail light.'],
    [I.bell, 'Two alarm set points', 'P-1 and P-2 with hysteresis, window or dual modes. Relay/NPN/PNP outputs are an order option.'],
    [I.wave, 'Analog output (option)', '4–20 mA or 1–5 V. Separate order option; our RS-485 units only have power + D+/D− wires.'],
    [I.net, 'RS-485 Modbus RTU', 'How we read pressure and push settings. Up to 32 meters on one CP24 bridge.'],
  ];
  caps.forEach(([img, head, body], i) => {
    const cw = 3.83, ch = 2.3, x = 0.6 + (i % 3) * (cw + 0.3), y = 1.85 + Math.floor(i / 3) * (ch + 0.25);
    card(s, head + ' card', x, y, cw, ch);
    iconCircle(s, head + ' icon', img, x + 0.3, y + 0.3, 0.75);
    s.addText(head, { x: x + 1.25, y: y + 0.3, w: cw - 1.5, h: 0.75, fontSize: 18, bold: true, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
    s.addText(body, { x: x + 0.3, y: y + 1.2, w: cw - 0.6, h: 0.95, fontSize: 14, color: C.text1, valign: 'top', margin: 0, isTextBox: true });
  });

  // 3. Communication chain -----------------------------------------------------
  s = content('Overview', 'How the PC talks to the meter', 'Four hops, one serial port: the Bluetooth link is transparent, so the PC speaks Modbus straight to the meter');
  const nodes = [
    [I.gauge, 'DPS-2.5SPD3', 'Pressure switch'],
    [I.tower, 'DX-CP24', 'RS-485 ↔ Bluetooth bridge'],
    [I.usb, 'DX-CP11', 'USB dongle (CH340 driver)'],
    [I.laptop, 'PC', 'DPS_Setup.exe on COM5'],
  ];
  const links = ['RS-485 wires', 'Bluetooth', 'USB'];
  nodes.forEach(([img, name, sub], i) => {
    const cx = 1.9 + i * 3.17;
    iconCircle(s, name + ' icon', img, cx - 0.65, 1.85, 1.3);
    s.addText(name, { x: cx - 1.4, y: 3.3, w: 2.8, h: 0.4, fontSize: 18, bold: true, color: C.text1, align: 'center', margin: 0, isTextBox: true });
    s.addText(sub, { x: cx - 1.4, y: 3.7, w: 2.8, h: 0.4, fontSize: 14, color: C.accent4, align: 'center', margin: 0, isTextBox: true });
    if (i < links.length) {
      s.addShape(pres.shapes.LINE, { x: cx + 0.85, y: 2.5, w: 3.17 - 1.7, h: 0, line: { color: C.accent4, width: 2, endArrowType: 'triangle' }, objectName: links[i] + ' arrow' });
      s.addText(links[i], { x: cx + 0.75, y: 2.05, w: 3.17 - 1.5, h: 0.35, fontSize: 12, italic: true, color: C.accent4, align: 'center', margin: 0, isTextBox: true });
    }
  });
  s.addText('Link settings (must match the CP24)', { x: 0.6, y: 4.6, w: 5.6, h: 0.4, fontSize: 16, bold: true, color: C.text1, margin: 0, isTextBox: true });
  [['19200', 'baud'], ['N-8-2', ''], ['ADDR 0', '']].forEach(([v, u], i) => led(s, 'Link ' + v, 0.6 + i * 1.95, 5.15, 1.75, 0.9, v, u, 20));
  card(s, 'Protocol card', 6.6, 4.6, 6.1, 2.1);
  s.addText([
    { text: 'Read pressure: ', options: { bold: true } }, { text: 'function 03, register 0x1C (32-bit, ÷ 100)', options: { breakLine: true } },
    { text: 'Change settings: ', options: { bold: true } }, { text: 'function 06, 16-bit settings only', options: { breakLine: true } },
    { text: 'Meter wiring: ', options: { bold: true } }, { text: 'brown V+ 14–28 V · blue COM · black D+ · white D−' },
  ], { x: 6.9, y: 4.75, w: 5.6, h: 1.8, fontSize: 14, color: C.text1, valign: 'middle', paraSpaceAfter: 6, margin: 0, isTextBox: true });

  // 4. Display settings ---------------------------------------------------------
  pres.addSection({ title: 'Settings' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Settings' });
  s.addText('Display settings', { placeholder: 'title' });
  s.addText('What you see on the meter and over RS-485, and how often it updates', { placeholder: 'body', bullet: false });
  const disp = [
    ['UNIT', 'Display unit', 'PSI', '', 'Unit shown on the display and returned over RS-485.', 'Keep PSI so readings match the test spec.'],
    ['DP', 'Decimal point', '0.01', '', 'Decimal places. Raw values scale with it: 1000 = 10.00.', '2 is plenty: sensor accuracy is ±1.8–3.6 PSI.'],
    ['LCUT', 'Display low cut', '0.20', 'PSI', 'Anything below 0.20 PSI reads as 0.', 'Harmless for holds well above zero; set 0 to see small leftovers.'],
    ['IDC_T', 'Display time', '5.0', 's', 'Refreshes every 5.0 s (range 0.1–9.9 s).', 'Try 0.5–1.0 s for a smoother pressure-decay log.'],
  ];
  disp.forEach(([name, full, v, u, does, consider], i) => {
    const cw = 2.8, x = 0.6 + i * (cw + 0.3), y = 1.85;
    card(s, name + ' card', x, y, cw, 4.85);
    s.addText([{ text: name, options: { fontSize: 20, bold: true, breakLine: true } }, { text: full, options: { fontSize: 14, color: C.accent4 } }],
      { x: x + 0.25, y: y + 0.2, w: cw - 0.5, h: 0.8, color: C.text1, valign: 'top', margin: 0, isTextBox: true });
    led(s, name + ' value', x + 0.25, y + 1.1, cw - 0.5, 0.85, v, u, 26);
    s.addText(does, { x: x + 0.25, y: y + 2.15, w: cw - 0.5, h: 1.2, fontSize: 14, color: C.text1, valign: 'top', margin: 0, isTextBox: true });
    s.addText([{ text: 'Consider: ', options: { bold: true } }, { text: consider }],
      { x: x + 0.25, y: y + 3.1, w: cw - 0.5, h: 1.3, fontSize: 14, color: C.text1, valign: 'top', margin: 0, isTextBox: true });
  });

  // 5. Alarm set points -------------------------------------------------------
  s = content('Settings', 'Alarm set points', 'P-1 and P-2 decide when the display flips between red and green');
  [['P-1', '10.00', 'PSI'], ['P-2', '20.00', 'PSI'], ['HYS', '0.00', 'PSI'], ['OUT-T', 'D', 'dual']].forEach(([n, v, u], i) => {
    const y = 1.9 + i * 0.85;
    s.addText(n, { x: 0.6, y, w: 1.2, h: 0.7, fontSize: 18, bold: true, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
    led(s, n + ' value', 1.8, y, 2.9, 0.7, v, u, 22);
  });
  const modes = [
    ['H', 'Hysteresis', 'OUT1 turns on above P-2 and off below P-1; OUT2 does the opposite.'],
    ['C', 'Window', 'OUT1 is on while pressure is between P-1 and P-2; OUT2 does the opposite.'],
    ['D', 'Dual (current setting)', 'OUT1 switches at P-1 and OUT2 at P-2, each with the HYS deadband.'],
  ];
  modes.forEach(([letter, name, desc], i) => {
    const y = 1.9 + i * 1.12;
    card(s, name + ' card', 5.3, y, 7.4, 0.97);
    s.addShape(pres.shapes.OVAL, { x: 5.5, y: y + 0.16, w: 0.65, h: 0.65, fill: { color: C.accent6 }, line: { type: 'none' }, objectName: letter + ' badge' });
    s.addText(letter, { x: 5.5, y: y + 0.16, w: 0.65, h: 0.65, fontFace: LED, bold: true, fontSize: 22, color: C.accent1, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
    s.addText([{ text: name, options: { bold: true, fontSize: 16, breakLine: true } }, { text: desc, options: { fontSize: 14 } }],
      { x: 6.4, y: y + 0.08, w: 6.1, h: 0.81, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
  });
  card(s, 'Alarm note', 0.6, 5.45, 12.1, 1.25);
  s.addText([
    { text: 'On our RS-485 units ', options: { bold: true } },
    { text: 'the wiring is power + D+/D− only, so the set points mainly drive the red/green display.', options: { breakLine: true } },
    { text: 'P-1 and P-2 are set on the front panel ', options: { bold: true } },
    { text: '(hold ▼/A-ADJ for 5 s). The meter rejects 32-bit writes over RS-485.' },
  ], { x: 0.9, y: 5.55, w: 11.5, h: 1.05, fontSize: 14, color: C.text1, valign: 'middle', paraSpaceAfter: 4, margin: 0, isTextBox: true });

  // 6. Communication and access -------------------------------------------------
  s = content('Settings', 'Communication and access', 'Settings that keep the link working and stop accidental changes');
  const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.accent4 } } });
  const ledCell = (t) => ({ text: t, options: { fontFace: LED, bold: true, color: C.accent1, fill: { color: C.accent6 }, align: 'center' } });
  const rows = [
    ['ADDR', '0', 'Modbus address (0–255)', 'Give each meter a unique 1–255 if several share one CP24. Many tools won\'t poll 0.'],
    ['BAUD', '19200', 'RS-485 speed', 'Must match the CP24. Change both or neither.'],
    ['PARI', 'N-8-2', 'Parity and stop bits', 'Must match the CP24. Leave as is.'],
    ['LOCK', 'NO', 'Front-panel key lock', 'Set YES after setup so operators can\'t change settings.'],
    ['CODE', '0', 'Menu pass code (0 = none)', 'Front panel only. Optional extra protection.'],
  ];
  s.addTable([
    [hdr('Setting'), hdr('Now'), hdr('What it is'), hdr('Guidance')],
    ...rows.map(([n, v, what, how], i) => {
      const fill = { color: i % 2 ? C.background2 : C.background1 };
      return [{ text: n, options: { bold: true, fill } }, ledCell(v), { text: what, options: { fill } }, { text: how, options: { fill } }];
    }),
  ], { x: 0.6, y: 1.85, w: 12.1, colW: [1.4, 1.6, 3.4, 5.7], rowH: 0.75, fontSize: 14, color: C.text1, valign: 'middle', margin: [0, 0.12, 0, 0.12], border: { type: 'none' } });

  // 7. Calibration -----------------------------------------------------------------
  s = content('Settings', 'Calibration values: leave these alone', 'Factory trims and read-only values; change them only when re-calibrating against a reference');
  const cal = [
    ['RANGE', '−1~50', 'bar', 'Sensor range, fixed by the hardware. Read-only.'],
    ['AZERO / ASPAN', '1000/45000', '', 'Factory trim for the analog output. Only matters with the 4–20 mA option.'],
    ['ANLO / ANHI', '0/100', 'PSI', 'Pressures that map to 4 mA and 20 mA. Only with the analog option.'],
    ['CJC', '33.2', '°C', 'Internal temperature compensation reading. Changes on its own.'],
    ['DZERO / DSPAN', 'PANEL', '', 'Display zero/span trim (front panel). For matching a reference gauge.'],
  ];
  cal.forEach(([n, v, u, desc], i) => {
    const y = 1.85 + i * 0.97;
    led(s, n + ' value', 0.6, y, 2.6, 0.8, v, u, 18, C.accent3);
    s.addText(n, { x: 3.5, y, w: 2.6, h: 0.8, fontSize: 18, bold: true, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
    s.addText(desc, { x: 6.2, y, w: 6.5, h: 0.8, fontSize: 14, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
  });

  // 8. Recommendations -------------------------------------------------------------
  pres.addSection({ title: 'Recommendations' });
  s = content('Recommendations', 'Tuning it for pressure holding', 'The biggest lever is the sensor range, not a setting');
  card(s, 'Accuracy callout', 0.6, 1.85, 4.3, 4.85, true);
  s.addText('±1.8–3.6', { x: 0.8, y: 2.55, w: 3.9, h: 0.9, fontFace: LED, bold: true, fontSize: 40, color: C.accent1, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
  s.addText('PSI', { x: 0.8, y: 3.4, w: 3.9, h: 0.5, fontFace: LED, bold: true, fontSize: 20, color: C.accent5, align: 'center', margin: 0, isTextBox: true });
  s.addText('Accuracy of this −1~50 bar sensor (0.25–0.5% of full scale). At a 20 PSI hold that is ±9–18% of the reading.',
    { x: 0.95, y: 4.3, w: 3.6, h: 1.9, fontSize: 16, color: C.background1, valign: 'top', margin: 0, isTextBox: true });
  const recs = [
    ['Match the sensor range to the test pressure', 'A −1~2 or −1~10 bar unit is about 25× or 5× more accurate near 20 PSI.'],
    ['Update faster', 'IDC_T 5.0 s → 1.0 s gives a smoother decay curve. DPS_Setup can push it.'],
    ['Use the display as pass/fail', 'Set P-1/P-2 around the allowed band; check which color means pass.'],
    ['Lock the panel after setup', 'LOCK = YES stops accidental changes. DPS_Setup can push it.'],
    ['One address per meter', 'Needed when meters share one CP24. Use "Change address to".'],
  ];
  recs.forEach(([head, desc], i) => {
    const y = 1.85 + i * 0.99;
    s.addShape(pres.shapes.OVAL, { x: 5.25, y: y + 0.12, w: 0.6, h: 0.6, fill: { color: C.accent6 }, line: { type: 'none' }, objectName: 'Rec ' + (i + 1) });
    s.addText(String(i + 1), { x: 5.25, y: y + 0.12, w: 0.6, h: 0.6, fontFace: LED, bold: true, fontSize: 20, color: C.accent1, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
    s.addText([{ text: head, options: { bold: true, fontSize: 16, breakLine: true } }, { text: desc, options: { fontSize: 14 } }],
      { x: 6.1, y, w: 6.6, h: 0.85, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
  });

  // 9. Register map ----------------------------------------------------------------
  pres.addSection({ title: 'Reference' });
  s = content('Reference', 'Register map quick reference', 'Address 0, 19200 baud, read with function 03; values as read from the reference meter');
  const regs = [
    ['0x00', 'RANGE', '2 (−1~50 bar)', 'Read-only'], ['0x01', 'UNIT', '5 (PSI)', 'Yes'], ['0x02', 'DP', '2', 'Yes'],
    ['0x03', 'OUT_T', '2 (D)', 'Yes'], ['0x04', 'ADDR', '0', 'Yes'], ['0x05', 'BAUD', '0 (19200)', 'Yes*'],
    ['0x06', 'PARI', '0 (N-8-2)', 'Yes*'], ['0x07', 'LOCK', '0 (NO)', 'Yes'], ['0x08', 'LCUT', '20 (0.20 PSI)', 'Yes'],
    ['0x09', 'IDC_T', '50 (5.0 s)', 'Yes'], ['0x0A', 'HYS', '0', 'Yes'], ['0x0B', 'AZERO', '1000', 'Avoid'],
    ['0x0C', 'ASPAN', '45000', 'Avoid'], ['0x0D', 'CJC', '~330 (33 °C)', 'Avoid'], ['0x0E', 'ANLO', '0', 'Panel'],
    ['0x10', 'ANHI', '10000 (100 PSI)', 'Panel'], ['0x12', 'CODE', '0', 'Panel'], ['0x14', 'P-1', '1000 (10 PSI)', 'Panel'],
    ['0x16', 'P-2', '2000 (20 PSI)', 'Panel'], ['0x1C', 'DISPLAY', 'live pressure', 'Read-only'],
  ];
  const regTable = (part, x) => s.addTable([
    [hdr('Reg'), hdr('Name'), hdr('Now'), hdr('RS-485 write')],
    ...part.map((r, i) => r.map((t, j) => ({ text: t, options: { fill: { color: i % 2 ? C.background2 : C.background1 }, bold: j === 1, fontFace: j === 0 ? LED : undefined } }))),
  ], { x, y: 1.8, w: 5.75, colW: [0.9, 1.25, 2.15, 1.45], rowH: 0.4, fontSize: 12, color: C.text1, valign: 'middle', margin: [0, 0.1, 0, 0.1], border: { type: 'none' } });
  regTable(regs.slice(0, 10), 0.6);
  regTable(regs.slice(10), 6.95);
  s.addText('* Writable, but must match the CP24 bridge or the link drops.   Panel: 32-bit values the meter rejects over RS-485; set them on the front panel.',
    { x: 0.6, y: 6.3, w: 12.1, h: 0.4, fontSize: 11, color: C.accent4, margin: 0, isTextBox: true });

  // 10. Closing --------------------------------------------------------------------
  s = pres.addSlide({ masterName: 'TITLE', sectionTitle: 'Reference' });
  s.addText('Changing the defaults', { placeholder: 'title' });
  s.addText('Agree on target values, test them on one meter, then push them to every meter with DPS_Setup', { placeholder: 'body', bullet: false });
  [
    'Try new values on one meter (front panel or DPS_Setup)',
    'Edit DESIRED at the top of dps_setup.py',
    'Run build_exe.py, then press Set Defaults on each meter',
  ].forEach((t, i) => {
    const y = 2.0 + i * 1.2;
    s.addShape(pres.shapes.OVAL, { x: 8.8, y, w: 0.75, h: 0.75, fill: { color: C.accent6 }, line: { type: 'none' }, objectName: 'Step ' + (i + 1) });
    s.addText(String(i + 1), { x: 8.8, y, w: 0.75, h: 0.75, fontFace: LED, bold: true, fontSize: 24, color: C.accent1, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
    s.addText(t, { x: 9.8, y: y - 0.1, w: 3.0, h: 0.95, fontSize: 16, color: C.background1, valign: 'middle', margin: 0, isTextBox: true });
  });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log('wrote', OUT);
})();
