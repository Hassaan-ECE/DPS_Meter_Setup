"""PyQt6 front end for dps_setup: pick the COM port, press Set Defaults, or change
individual settings on the Settings tab.

Run:   python dps_gui.py
Build: python build_exe.py   (makes dist\\DPS_Setup.exe)
"""

import html
import sys

import serial
from serial.tools import list_ports
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                             QScrollArea, QSpinBox, QTabWidget, QToolButton, QVBoxLayout, QWidget)

import dps_setup as dps

CH340_VID = 0x1A86  # DX-CP11 Bluetooth dongle

# Settings tab rows. EDITABLE are 16-bit and written with FC06; READ_ONLY are shown for reference.
EDITABLE = ['UNIT', 'DP', 'LCUT', 'IDC_T', 'OUT_T', 'HYS', 'LOCK']
READ_ONLY = ['P1', 'P2', 'CODE', 'ANLO', 'ANHI', 'ADDR', 'BAUD', 'PARI', 'RANGE']
CHOICES = {'UNIT': dps.UNITS, 'OUT_T': dps.OUT_TYPES, 'LOCK': ['no', 'yes']}
CHANGED_STYLE = 'color: #9a6700; font-weight: bold;'


class Job(QThread):
    """Connects to the meter and runs one task off the UI thread (Bluetooth replies are slow)."""
    line = pyqtSignal(str)
    settings_read = pyqtSignal(dict)
    finished_ok = pyqtSignal(bool)

    def __init__(self, port, address, task, writes):
        super().__init__()
        self.port, self.address, self.task, self.writes = port, address, task, writes

    def run(self):
        ok = False
        meter = None
        try:
            meter = dps.Meter(self.port, dps.DEFAULT_BAUD, self.address)
            settings = meter.read_settings()
            self.line.emit(f'Connected to {self.port}, address {self.address}, '
                           f'range {dps.describe("RANGE", settings["RANGE"], settings)}')
            self.line.emit(f'Pressure: {dps.format_pressure(meter.read_pressure(), settings)}\n')
            ok = self.task(meter, settings, self.line.emit)
            self.settings_read.emit(meter.read_settings() if self.writes else settings)
        except (dps.ModbusError, serial.SerialException, ValueError) as e:
            self.line.emit(f'Error: {e}')
        finally:
            if meter:
                meter.close()
            self.finished_ok.emit(ok)


def show_task(meter, settings, out):
    dps.show(settings, dps.DESIRED, out=out)
    out(f'\n{len(dps.diffs(settings, dps.DESIRED))} setting(s) differ from defaults (*).')
    return True


class SettingsPage(QWidget):
    """One row per setting: value on the meter, new value, default, and an info button."""
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.meter = None  # settings from the last read
        self.titles, self.current, self.defaults, self.editors = {}, {}, {}, {}

        grid = QGridLayout(self)
        grid.setHorizontalSpacing(16)
        for col, text in enumerate(['Setting', 'On meter', 'New value', 'Default']):
            header = QLabel(text)
            header.setStyleSheet('font-weight: bold;')
            grid.addWidget(header, 0, col)
        row = 1
        for name in EDITABLE:
            self.add_row(grid, row, name, self.make_editor(name))
            row += 1
        line = QFrame(frameShape=QFrame.Shape.HLine)
        grid.addWidget(line, row, 0, 1, 5)
        note = QLabel('Front-panel / fixed settings (shown for reference):')
        note.setStyleSheet('color: gray;')
        grid.addWidget(note, row + 1, 0, 1, 5)
        row += 2
        for name in READ_ONLY:
            text = 'front panel only' if name in dps.PANEL_ONLY else 'not changed here'
            label = QLabel(text)
            label.setStyleSheet('color: gray;')
            self.add_row(grid, row, name, label)
            row += 1
        grid.setRowStretch(row, 1)
        grid.setColumnStretch(2, 1)
        self.show_defaults({'DP': dps.DESIRED['DP'], 'UNIT': dps.DESIRED['UNIT']})

    def add_row(self, grid, row, name, editor):
        title, text = dps.INFO[name]
        self.titles[name] = QLabel(f'{title} ({name})')
        self.current[name] = QLabel('-')
        self.defaults[name] = QLabel()
        info = QToolButton(text='?')
        info.setToolTip(f'<p>{html.escape(text)}</p>')
        info.clicked.connect(lambda _, n=name: QMessageBox.information(self, dps.INFO[n][0], dps.INFO[n][1]))
        for col, w in enumerate([self.titles[name], self.current[name], editor, self.defaults[name], info]):
            grid.addWidget(w, row, col)

    def make_editor(self, name):
        if name in CHOICES:
            w = QComboBox()
            w.addItems([str(c) for c in CHOICES[name]])
            w.currentIndexChanged.connect(self.on_scale_change if name == 'UNIT' else self.refresh)
        elif name == 'DP':
            w = QSpinBox()
            w.setRange(*dps.LIMITS['DP'])
            w.valueChanged.connect(self.on_scale_change)
        else:
            w = QDoubleSpinBox()
            if name == 'IDC_T':
                w.setDecimals(1)
                w.setRange(0.1, 9.9)
                w.setSingleStep(0.1)
                w.setSuffix(' s')
            w.valueChanged.connect(self.refresh)
        w.setEnabled(False)  # until the first read
        self.editors[name] = w
        return w

    def value(self, name):
        """Raw register value for what the editor shows."""
        w = self.editors[name]
        if name in CHOICES:
            return w.currentIndex()
        if name == 'DP':
            return w.value()
        if name == 'IDC_T':
            return round(w.value() * 10)
        return round(w.value() * 10 ** self.editors['DP'].value())

    def set_value(self, name, v):
        w = self.editors[name]
        if name in CHOICES:
            w.setCurrentIndex(v)
        elif name == 'DP':
            w.setValue(v)
        elif name == 'IDC_T':
            w.setValue(v / 10)
        else:
            w.setValue(v / 10 ** self.editors['DP'].value())

    def rescale(self):
        """Match LCUT/HYS to the DP and UNIT being edited, keeping the pressure they stand for."""
        dp = self.editors['DP'].value()
        for name in ('LCUT', 'HYS'):
            w = self.editors[name]
            v = w.value()
            was_blocked = w.blockSignals(True)
            w.setDecimals(dp)
            w.setSingleStep(10 ** -dp)
            w.setRange(0, dps.LIMITS[name][1] / 10 ** dp)
            w.setSuffix(f' {self.editors["UNIT"].currentText()}')
            w.setValue(v)
            w.blockSignals(was_blocked)

    def on_scale_change(self):
        self.rescale()
        self.refresh()

    def load(self, settings):
        """Show a fresh read from the meter and reset the editors to it."""
        self.meter = settings
        for name, label in self.current.items():
            label.setText(dps.describe(name, settings[name], settings))
        self.show_defaults(settings)
        for w in self.editors.values():
            w.setEnabled(True)
        self.fill(settings)

    def show_defaults(self, settings):
        for name, label in self.defaults.items():
            want = dps.DESIRED.get(name)
            label.setText('' if want is None else dps.describe(name, want, settings))

    def fill(self, values):
        """Put raw register values into the editors (DP and UNIT first, since LCUT/HYS depend on them)."""
        for w in self.editors.values():
            w.blockSignals(True)
        self.set_value('DP', values['DP'])
        self.set_value('UNIT', values['UNIT'])
        self.rescale()
        for name in EDITABLE:
            self.set_value(name, values[name])
        for w in self.editors.values():
            w.blockSignals(False)
        self.refresh()

    def fill_defaults(self):
        self.fill({**self.meter, **{k: dps.DESIRED[k] for k in EDITABLE if dps.DESIRED.get(k) is not None}})

    def revert(self):
        self.fill(self.meter)

    def changes(self):
        if self.meter is None:
            return {}
        return {n: self.value(n) for n in EDITABLE if self.value(n) != self.meter[n]}

    def refresh(self):
        changes = self.changes()
        for name in EDITABLE:
            self.titles[name].setStyleSheet(CHANGED_STYLE if name in changes else '')
        self.changed.emit()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DPS Meter Setup')
        self.job = None
        self.busy = False

        self.port = QComboBox()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.load_ports)
        port_row = QHBoxLayout()
        port_row.addWidget(self.port, 1)
        port_row.addWidget(refresh)

        self.address = QSpinBox()
        self.address.setRange(0, 255)
        self.address.setValue(dps.DEFAULT_ADDRESS)

        self.tag = QLineEdit()
        self.tag.setPlaceholderText('From the meter label (optional, for the log)')

        form = QFormLayout()
        form.addRow('COM port', port_row)
        form.addRow('Meter address', self.address)
        form.addRow('Meter serial / tag', self.tag)

        tabs = QTabWidget()
        tabs.addTab(self.defaults_tab(), 'Defaults')
        tabs.addTab(self.settings_tab(), 'Settings')

        self.status = QLabel()
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setFont(QFont('Consolas', 9))
        self.log.setMinimumSize(560, 160)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(tabs, 2)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)
        self.resize(760, 820)

        self.load_ports()
        self.set_busy(False)

    def defaults_tab(self):
        self.new_address = QSpinBox()
        self.new_address.setRange(0, 255)
        self.new_address.setSpecialValueText('Keep')  # 0 shows as "Keep"

        self.read_btn = QPushButton('Read')
        self.read_btn.clicked.connect(self.read)
        self.apply_btn = QPushButton('Set Defaults')
        self.apply_btn.setMinimumHeight(44)
        font = self.apply_btn.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.apply_btn.setFont(font)
        self.apply_btn.clicked.connect(self.set_defaults)
        buttons = QHBoxLayout()
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.apply_btn, 1)

        form = QFormLayout()
        form.addRow('Change address to', self.new_address)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return tab

    def settings_tab(self):
        self.page = SettingsPage()
        self.page.changed.connect(self.update_buttons)
        scroll = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        scroll.setWidget(self.page)

        self.read2_btn = QPushButton('Read meter')
        self.read2_btn.clicked.connect(self.read)
        self.fill_btn = QPushButton('Load defaults')
        self.fill_btn.setToolTip('Fill in the default values; nothing is written until you press Write')
        self.fill_btn.clicked.connect(self.page.fill_defaults)
        self.revert_btn = QPushButton('Revert')
        self.revert_btn.setToolTip('Go back to the values on the meter')
        self.revert_btn.clicked.connect(self.page.revert)
        self.write_btn = QPushButton('Write changes')
        font = self.write_btn.font()
        font.setBold(True)
        self.write_btn.setFont(font)
        self.write_btn.clicked.connect(self.write_changes)
        buttons = QHBoxLayout()
        for b in (self.read2_btn, self.fill_btn, self.revert_btn):
            buttons.addWidget(b)
        buttons.addWidget(self.write_btn, 1)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel('Read the meter, change any values, then Write. Changed settings are '
                                'highlighted; press ? for what a setting does.', wordWrap=True))
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)
        return tab

    def load_ports(self):
        self.port.clear()
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        for p in ports:
            self.port.addItem(f'{p.device} - {p.description}', p.device)
        # Prefer the CH340 Bluetooth dongle if it is plugged in.
        for i, p in enumerate(ports):
            if p.vid == CH340_VID:
                self.port.setCurrentIndex(i)
                break
        if not ports:
            self.set_status('No COM ports found. Plug in the dongle and press Refresh.', False)

    def read(self):
        self.run_job(show_task, 'Reading...', 'Read OK.')

    def set_defaults(self):
        port, tag = self.port.currentData(), self.tag.text().strip()
        new_address = self.new_address.value() or None

        def task(meter, settings, out):
            return dps.apply_settings(meter, port, new_address, tag, out=out)

        def moved():
            if new_address is not None:
                self.address.setValue(new_address)
                self.new_address.setValue(0)

        self.run_job(task, 'Setting defaults...', 'Done - defaults set and verified.', writes=True, on_ok=moved)

    def write_changes(self):
        changes = self.page.changes()
        if not changes:
            return
        old = self.page.meter
        new = {**old, **changes}
        lines = [f'{dps.INFO[n][0]} ({n}):  {dps.describe(n, old[n], old)}  ->  {dps.describe(n, v, new)}'
                 for n, v in changes.items()]
        if 'DP' in changes or 'UNIT' in changes:
            lines.append('\nP-1, P-2, ANLO and ANHI are not converted. Check them on the front panel '
                         'afterwards.')
        question = f'Write {len(changes)} change(s) to the meter at address {self.address.value()}?\n\n'
        if QMessageBox.question(self, 'Write settings', question + '\n'.join(lines)) \
                != QMessageBox.StandardButton.Yes:
            return

        port, tag = self.port.currentData(), self.tag.text().strip()

        def task(meter, settings, out):
            return dps.apply_custom(meter, port, changes, tag, out=out)

        self.run_job(task, 'Writing settings...', 'Done - settings written and verified.', writes=True)

    def run_job(self, task, busy_text, ok_text, writes=False, on_ok=None):
        port = self.port.currentData()
        if not port:
            self.set_status('Pick a COM port first.', False)
            return
        self.log.clear()
        self.set_status(busy_text, None)
        self.set_busy(True)
        self.job = Job(port, self.address.value(), task, writes)
        self.job.line.connect(self.log.appendPlainText)
        self.job.settings_read.connect(self.page.load)
        self.job.finished_ok.connect(lambda ok: self.done(ok, ok_text, on_ok))
        self.job.start()

    def done(self, ok, ok_text, on_ok):
        self.set_busy(False)
        if ok:
            self.set_status(ok_text, True)
            if on_ok:
                on_ok()
        else:
            self.set_status('Failed - see log below.', False)

    def set_busy(self, busy):
        self.busy = busy
        self.update_buttons()

    def update_buttons(self):
        loaded = self.page.meter is not None
        n = len(self.page.changes())
        for b in (self.read_btn, self.apply_btn, self.read2_btn):
            b.setEnabled(not self.busy)
        self.fill_btn.setEnabled(loaded and not self.busy)
        self.revert_btn.setEnabled(loaded and not self.busy)
        self.write_btn.setEnabled(n > 0 and not self.busy)
        self.write_btn.setText(f'Write {n} change(s)' if n else 'Write changes')

    def set_status(self, text, ok):
        color = {True: '#1a7f37', False: '#cf222e', None: ''}[ok]
        self.status.setStyleSheet(f'color: {color}; font-weight: bold;' if color else '')
        self.status.setText(text)


def main():
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
