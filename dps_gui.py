"""PyQt6 front end for dps_setup: pick the COM port, press Set Defaults.

Run:   python dps_gui.py
Build: python build_exe.py   (makes dist\\DPS_Setup.exe)
"""

import sys

import serial
from serial.tools import list_ports
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
                             QWidget)

import dps_setup as dps

CH340_VID = 0x1A86  # DX-CP11 Bluetooth dongle


class Job(QThread):
    """Runs one read or apply against the meter off the UI thread (Bluetooth replies are slow)."""
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(bool)

    def __init__(self, apply, port, address, new_address, tag):
        super().__init__()
        self.apply, self.port, self.address = apply, port, address
        self.new_address, self.tag = new_address, tag

    def run(self):
        ok = False
        meter = None
        try:
            meter = dps.Meter(self.port, dps.DEFAULT_BAUD, self.address)
            settings = meter.read_settings()
            self.line.emit(f'Connected to {self.port}, address {self.address}, '
                           f'range {dps.describe("RANGE", settings["RANGE"], settings)}')
            self.line.emit(f'Pressure: {dps.format_pressure(meter.read_pressure(), settings)}\n')
            if self.apply:
                ok = dps.apply_settings(meter, self.port, self.new_address, self.tag, out=self.line.emit)
            else:
                dps.show(settings, dps.DESIRED, out=self.line.emit)
                n = len(dps.diffs(settings, dps.DESIRED))
                self.line.emit(f'\n{n} setting(s) differ from defaults (*).')
                ok = True
        except (dps.ModbusError, serial.SerialException, ValueError) as e:
            self.line.emit(f'Error: {e}')
        finally:
            if meter:
                meter.close()
            self.finished_ok.emit(ok)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DPS Meter Setup')
        self.job = None

        self.port = QComboBox()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.load_ports)
        port_row = QHBoxLayout()
        port_row.addWidget(self.port, 1)
        port_row.addWidget(refresh)

        self.address = QSpinBox()
        self.address.setRange(0, 255)
        self.address.setValue(dps.DEFAULT_ADDRESS)

        self.new_address = QSpinBox()
        self.new_address.setRange(0, 255)
        self.new_address.setSpecialValueText('Keep')  # 0 shows as "Keep"

        self.tag = QLineEdit()
        self.tag.setPlaceholderText('From the meter label (optional, for the log)')

        form = QFormLayout()
        form.addRow('COM port', port_row)
        form.addRow('Meter address', self.address)
        form.addRow('Change address to', self.new_address)
        form.addRow('Meter serial / tag', self.tag)

        self.read_btn = QPushButton('Read')
        self.read_btn.clicked.connect(lambda: self.start(apply=False))
        self.apply_btn = QPushButton('Set Defaults')
        self.apply_btn.setMinimumHeight(44)
        font = self.apply_btn.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.apply_btn.setFont(font)
        self.apply_btn.clicked.connect(lambda: self.start(apply=True))
        buttons = QHBoxLayout()
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.apply_btn, 1)

        self.status = QLabel()
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setFont(QFont('Consolas', 9))
        self.log.setMinimumSize(560, 320)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)

        self.load_ports()

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

    def start(self, apply):
        port = self.port.currentData()
        if not port:
            self.set_status('Pick a COM port first.', False)
            return
        new_address = self.new_address.value() or None
        self.log.clear()
        self.set_status('Setting defaults...' if apply else 'Reading...', None)
        self.read_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.job = Job(apply, port, self.address.value(), new_address, self.tag.text().strip())
        self.job.line.connect(self.log.appendPlainText)
        self.job.finished_ok.connect(lambda ok: self.done(apply, ok, new_address))
        self.job.start()

    def done(self, apply, ok, new_address):
        self.read_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
        if apply and ok:
            if new_address is not None:
                self.address.setValue(new_address)
                self.new_address.setValue(0)
            self.set_status('Done - defaults set and verified.', True)
        elif ok:
            self.set_status('Read OK.', True)
        else:
            self.set_status('Failed - see log below.', False)

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
