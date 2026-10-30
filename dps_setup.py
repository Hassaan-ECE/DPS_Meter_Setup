"""Check and set RE-ATLANTIS DPS-2.5SPD3 pressure switch settings over Modbus RTU.

The meter has no serial-number register, so each configured meter is logged to
dps_meters.csv with the address it was given and the serial from its label (--tag).

Usage:
    python dps_setup.py                                # show current vs desired, no writes
    python dps_setup.py --apply --tag SN12345          # write differences, verify, log
    python dps_setup.py --apply --new-address 3        # also move the meter to address 3
    python dps_setup.py --address 3 --watch            # live pressure readout

Requires: pip install pyserial
"""

import argparse
import csv
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

# ---------------------------------------------------------------------------
# Desired settings: copied from the reference meter on 2026-10-30.
# Values are raw register values (see the sheet's address map); "counts" are
# display units x 10^DP, so with DP=2, 1000 counts = 10.00 PSI.
# Remove a line (or set it to None) to leave that setting untouched.
# ANLO, ANHI, CODE, P1, P2 are 32-bit: checked only, set them from the front panel.
# ---------------------------------------------------------------------------
DESIRED = {
    'UNIT': 5,       # 0 bar, 1 kg/cm2, 2 kPa, 3 MPa, 4 mmHg, 5 PSI, 6 inHg
    'DP': 2,         # decimal places (0-4)
    'OUT_T': 2,      # alarm mode: 0 H (hysteresis), 1 C (window), 2 D (dual)
    'LOCK': 0,       # front panel lock: 0 no, 1 yes
    'LCUT': 20,      # display low cut, counts (20 = readings under 0.20 PSI show 0)
    'IDC_T': 50,     # display/update time in 0.1 s (50 = 5.0 s)
    'HYS': 0,        # alarm hysteresis, counts
    'ANLO': 0,       # analog output zero, counts
    'ANHI': 10000,   # analog output span, counts (100.00 PSI)
    'CODE': 0,       # front panel pass code (0 = none)
    'P1': 1000,      # alarm set point 1, counts (10.00 PSI)
    'P2': 2000,      # alarm set point 2, counts (20.00 PSI)
}

DEFAULT_PORT = 'COM5'
DEFAULT_BAUD = 19200
DEFAULT_ADDRESS = 0
# Next to the .exe when built with PyInstaller, otherwise next to this file.
APP_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
LOG_FILE = APP_DIR / 'dps_meters.csv'

# name: (register, words, signed)
REGS = {
    'RANGE': (0x00, 1, False),
    'UNIT': (0x01, 1, False),
    'DP': (0x02, 1, False),
    'OUT_T': (0x03, 1, False),
    'ADDR': (0x04, 1, False),
    'BAUD': (0x05, 1, False),
    'PARI': (0x06, 1, False),
    'LOCK': (0x07, 1, False),
    'LCUT': (0x08, 1, False),
    'IDC_T': (0x09, 1, False),
    'HYS': (0x0A, 1, False),
    'AZERO': (0x0B, 1, False),
    'ASPAN': (0x0C, 1, False),
    'CJC': (0x0D, 1, True),
    'ANLO': (0x0E, 2, True),
    'ANHI': (0x10, 2, True),
    'CODE': (0x12, 2, False),
    'P1': (0x14, 2, True),
    'P2': (0x16, 2, True),
}
DISPLAY_REG = 0x1C
SETTINGS_WORDS = 0x18  # registers 0x00-0x17 in one read

# Never written by this script: RANGE is read-only, AZERO/ASPAN/CJC are calibration,
# BAUD/PARI must match the RS-485 bridge, ADDR goes through --new-address.
PROTECTED = {'RANGE', 'AZERO', 'ASPAN', 'CJC', 'BAUD', 'PARI', 'ADDR'}

# 32-bit settings: tested 2026-10-30, the meter ignores FC16, rejects FC06 to the low
# word, and FC06 to the high word is stored unchecked. These are checked, never written;
# set them from the front panel.
PANEL_ONLY = {name for name, (_, n, _) in REGS.items() if n == 2}

# Settings this script may write, with the valid range from the register sheet.
# Writes outside these ranges (or to anything else) are refused before reaching the meter.
LIMITS = {'UNIT': (0, 6), 'DP': (0, 4), 'OUT_T': (0, 2), 'ADDR': (0, 255), 'LOCK': (0, 1),
          'LCUT': (0, 999), 'IDC_T': (1, 99), 'HYS': (0, 999)}

UNITS = ['bar', 'kg/cm2', 'kPa', 'MPa', 'mmHg', 'PSI', 'inHg']
RANGES = ['-1~2 bar', '-1~10 bar', '-1~50 bar', '0~250 bar']
OUT_TYPES = ['H (hysteresis)', 'C (window)', 'D (dual)']
BAUDS = [19200, 9600, 4800, 2400]
PARITIES = ['N-8-2', 'N-8-1', 'E-8-1', 'O-8-1']
SCALED = {'LCUT', 'HYS', 'ANLO', 'ANHI', 'P1', 'P2'}

# name: (title, explanation) - shown by the GUI's info buttons.
INFO = {
    'RANGE': ('Sensor range',
              'The pressure range of the sensor, fixed at the factory: -1~2 bar, -1~10 bar, -1~50 bar or '
              '0~250 bar. Read-only.\n\nAccuracy is 0.25% of full scale, so a smaller range reads finer '
              'at low pressure.'),
    'UNIT': ('Display unit',
             'Unit for the displayed pressure: bar, kg/cm2, kPa, MPa, mmHg, PSI or inHg.\n\n'
             'LCUT, HYS, P-1, P-2, ANLO and ANHI are stored as plain numbers, not as pressure. It is not '
             'yet verified whether the meter converts them when the unit changes, so read the meter and '
             'check them (and the front-panel set points) after changing the unit.\n\n'
             '1 bar = 14.5036 PSI = 100 kPa = 0.1 MPa = 1.01972 kg/cm2 = 750.062 mmHg = 29.53 inHg.'),
    'DP': ('Decimal places',
           'How many digits are shown after the decimal point (0-4).\n\n'
           'Every pressure setting is stored as counts = value x 10^DP, so one step of DP moves them by a '
           'factor of 10. This page rescales LCUT and HYS for you; P-1, P-2, ANLO and ANHI are front-panel '
           'only and must be re-entered there.\n\n'
           'The display shows at most 99999 counts (-19999 at the bottom), e.g. 999.99 with DP=2 or 99.999 '
           'with DP=3. Choose DP so the highest test pressure still fits.'),
    'OUT_T': ('Alarm output type',
              'How the two alarm outputs react to pressure, using set points P-1 and P-2:\n\n'
              'H (hysteresis): OUT1 turns on when pressure rises to P-2 and off when it falls to P-1, so '
              'P-1/P-2 form the switching band. OUT2 is the opposite.\n\n'
              'C (window): OUT1 is on while pressure is between P-1 and P-2 (HYS sets the dead band at each '
              'edge). OUT2 is the opposite.\n\n'
              'D (dual): two independent switches. OUT1 turns on above P-1, OUT2 above P-2, each with HYS '
              'dead band.\n\n'
              'RS-485 meters have no alarm wires, so on these units this only changes when the display '
              'turns red or green.'),
    'ADDR': ('Modbus address',
             'The meter\'s address on the RS-485 line (0-255). Every meter sharing one DX-CP24 needs its own '
             'address. Change it with "Change address to" on the Defaults tab or from the front panel.'),
    'BAUD': ('Baud rate',
             'Serial speed: 19200, 9600, 4800 or 2400. It must match the DX-CP24 bridge (19200), otherwise '
             'the meter stops answering. This tool never changes it; use the front panel.'),
    'PARI': ('Parity',
             'Serial framing: N-8-2, N-8-1, E-8-1 or O-8-1. It must match the DX-CP24 bridge (N-8-2), '
             'otherwise the meter stops answering. This tool never changes it; use the front panel.'),
    'LOCK': ('Panel lock',
             'YES locks the front-panel keys so nobody can change settings by hand. Set it last, after P-1 '
             'and P-2 are entered on the panel.\n\nWrites over RS-485 should still work while locked '
             '(not yet tested), so it can be set back to "no" from this page.'),
    'LCUT': ('Display low cut',
             'Readings below this value show as 0. It hides sensor noise near zero. Range 0-999 counts '
             '(0-9.99 with DP=2).\n\nFor pressure-hold testing, keep it well below the smallest pressure '
             'you need to see, or a slow leak toward zero will drop to 0 early.'),
    'IDC_T': ('Display time',
              'How often the reading updates, 0.1-9.9 s. Shorter reacts faster to pressure changes; longer '
              'gives a steadier number. The value read over RS-485 is likely the displayed value, so it '
              'updates at the same rate.'),
    'HYS': ('Alarm hysteresis',
            'Dead band around the set points, 0-999 counts, so the outputs don\'t chatter when pressure '
            'sits right at a set point. Used in C and D alarm modes (see OUT_T).'),
    'AZERO': ('Analog zero trim', 'Factory trim for the 4-20 mA output. Not used on RS-485 units and '
              'never changed by this tool.'),
    'ASPAN': ('Analog span trim', 'Factory trim for the 4-20 mA output. Not used on RS-485 units and '
              'never changed by this tool.'),
    'CJC': ('Internal temperature', 'Temperature inside the meter in 0.1 C (330 = 33.0 C). Live reading, '
            'never written.'),
    'ANLO': ('Analog output zero',
             'Pressure that gives 4 mA on the analog output (-19999~99999 counts). RS-485 units have no '
             'analog output, so it is unused.\n\n32-bit setting: it can only be changed from the front '
             'panel (the meter does not accept 32-bit writes over RS-485).'),
    'ANHI': ('Analog output span',
             'Pressure that gives 20 mA on the analog output (-19999~99999 counts). RS-485 units have no '
             'analog output, so it is unused.\n\n32-bit setting: it can only be changed from the front '
             'panel (the meter does not accept 32-bit writes over RS-485).'),
    'CODE': ('Pass code',
             'Code (0-99999) asked for when entering the settings menu (hold ENT 3 s). 0 means no code.\n\n'
             '32-bit setting: it can only be changed from the front panel.'),
    'P1': ('Set point 1',
           'Alarm set point 1 (-19999~99999 counts). What it does depends on OUT_T.\n\n32-bit setting: '
           'set it from the front panel by holding the down/A-ADJ key for 5 s.'),
    'P2': ('Set point 2',
           'Alarm set point 2 (-19999~99999 counts). What it does depends on OUT_T.\n\n32-bit setting: '
           'set it from the front panel by holding the down/A-ADJ key for 5 s (after P-1).'),
}


class ModbusError(Exception):
    pass


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class Meter:
    def __init__(self, port, baud, address, timeout=1.5, retries=2):
        self.sp = serial.Serial(port, baud, bytesize=8, parity='N', stopbits=2, timeout=0)
        self.address = address
        self.timeout = timeout
        self.retries = retries

    def close(self):
        self.sp.close()

    def _transact(self, pdu, reply_len):
        frame = bytes([self.address]) + pdu
        frame += struct.pack('<H', crc16(frame))
        for attempt in range(self.retries + 1):
            self.sp.reset_input_buffer()
            self.sp.write(frame)
            buf = b''
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                buf += self.sp.read(self.sp.in_waiting or 1)
                if len(buf) >= 5 and buf[1] & 0x80:
                    break
                if len(buf) >= reply_len:
                    break
                time.sleep(0.005)
            if len(buf) >= 5 and buf[1] & 0x80 and crc16(buf[:5]) == 0:
                raise ModbusError(f'meter rejected request (exception code {buf[2]})')
            if len(buf) >= reply_len and crc16(buf[:reply_len]) == 0:
                return buf[:reply_len]
        raise ModbusError(f'no valid reply from address {self.address}')

    def read(self, start, count):
        reply = self._transact(struct.pack('>BHH', 3, start, count), 5 + 2 * count)
        return list(struct.unpack(f'>{count}H', reply[3:3 + 2 * count]))

    def write(self, reg, value):
        # FC06 only: the meter ignores FC16 and rejects/mangles 32-bit values written as words.
        self._transact(struct.pack('>BHH', 6, reg, value & 0xFFFF), 8)
        time.sleep(0.1)  # let the EEPROM write finish

    def read_settings(self):
        words = self.read(0, SETTINGS_WORDS)
        values = {}
        for name, (reg, n, signed) in REGS.items():
            if n == 1:
                v = words[reg]
                if signed and v >= 0x8000:
                    v -= 0x10000
            else:
                v = (words[reg] << 16) | words[reg + 1]
                if signed and v >= 0x80000000:
                    v -= 0x100000000
            values[name] = v
        return values

    def write_setting(self, name, value):
        if name in PANEL_ONLY:
            raise ValueError(f'{name} is 32-bit and cannot be written over Modbus')
        if name not in LIMITS:
            raise ValueError(f'{name} is not writable by this tool')
        lo, hi = LIMITS[name]
        if not lo <= value <= hi:
            raise ValueError(f'{name} must be {lo}-{hi}, got {value}')
        self.write(REGS[name][0], value)

    def read_pressure(self):
        hi, lo = self.read(DISPLAY_REG, 2)
        raw = (hi << 16) | lo
        return raw - 0x100000000 if raw >= 0x80000000 else raw


def describe(name, v, settings):
    dp = settings['DP']
    unit = UNITS[settings['UNIT']] if settings['UNIT'] < len(UNITS) else '?'
    lookup = {'UNIT': UNITS, 'RANGE': RANGES, 'OUT_T': OUT_TYPES, 'BAUD': BAUDS, 'PARI': PARITIES}
    if name in lookup:
        table = lookup[name]
        return str(table[v]) if 0 <= v < len(table) else f'? ({v})'
    if name in SCALED:
        return f'{v / 10 ** dp:.{dp}f} {unit}'
    if name == 'IDC_T':
        return f'{v / 10:.1f} s'
    if name == 'CJC':
        return f'{v / 10:.1f} C'
    if name == 'LOCK':
        return 'yes' if v else 'no'
    return str(v)


def format_pressure(raw, settings):
    dp = settings['DP']
    return f'{raw / 10 ** dp:.{dp}f} {UNITS[settings["UNIT"]]}'


def show(settings, desired, out=print):
    out(f'{"Setting":<7} {"Current":>9}  {"Desired":>9}  Meaning')
    for name, v in settings.items():
        want = desired.get(name)
        mark = '*' if want is not None and want != v else ' '
        want_s = '' if want is None else str(want)
        out(f'{name:<7} {v:>9}  {want_s:>9} {mark} {describe(name, v, settings)}')


def diffs(settings, desired):
    return {k: v for k, v in desired.items()
            if v is not None and k not in PROTECTED and settings[k] != v}


def log_meter(port, address, tag, settings, pressure):
    new_file = not LOG_FILE.exists()
    with LOG_FILE.open('a', newline='') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['timestamp', 'tag', 'port', 'address', 'pressure', *REGS])
        w.writerow([datetime.now().isoformat(timespec='seconds'), tag, port, address,
                    format_pressure(pressure, settings), *settings.values()])


def write_settings(meter, changes, out=print):
    """Write {name: value}, ADDR last since it moves the meter, and return the read-back settings."""
    for name in sorted(changes, key=lambda n: n == 'ADDR'):
        out(f'Writing {name} = {changes[name]}')
        meter.write_setting(name, changes[name])
        if name == 'ADDR':
            meter.address = changes[name]
    return meter.read_settings()


def apply_settings(meter, port, new_address=None, tag='', out=print):
    """Write DESIRED (and optionally a new address), verify by read-back, and log. True on success."""
    if new_address is not None and not 1 <= new_address <= 255:
        raise ValueError('new address must be 1-255')
    settings = meter.read_settings()
    changes = {}
    for name, value in diffs(settings, DESIRED).items():
        if name in PANEL_ONLY:
            out(f'Skipping {name}: set it to {describe(name, value, settings)} from the front panel')
        else:
            changes[name] = value
    if new_address is not None and new_address != meter.address:
        changes['ADDR'] = new_address

    settings = write_settings(meter, changes, out)
    bad = list(diffs(settings, DESIRED))
    if 'ADDR' in changes and settings['ADDR'] != changes['ADDR']:
        bad.append('ADDR')
    return finish(meter, port, tag, settings, bad, out)


def apply_custom(meter, port, wanted, tag='', out=print):
    """Write the chosen {name: value} settings that differ from the meter, verify, and log. True on success."""
    settings = meter.read_settings()
    changes = {k: v for k, v in wanted.items() if settings[k] != v}
    if not changes:
        out('Meter already has these values; nothing written.')
    settings = write_settings(meter, changes, out)
    bad = [k for k, v in wanted.items() if settings[k] != v]
    return finish(meter, port, tag, settings, bad, out)


def finish(meter, port, tag, settings, bad, out):
    """Report a failed verify, or log the meter and report success. True on success."""
    if bad:
        out(f'Verify FAILED for: {", ".join(bad)}')
        return False

    pressure = meter.read_pressure()
    log_meter(port, meter.address, tag, settings, pressure)
    out(f'Verified. Meter now at address {meter.address}, reading {format_pressure(pressure, settings)}.')
    out(f'Logged to {LOG_FILE}')
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', default=DEFAULT_PORT)
    ap.add_argument('--baud', type=int, default=DEFAULT_BAUD)
    ap.add_argument('--address', type=int, default=DEFAULT_ADDRESS, help='current Modbus address')
    ap.add_argument('--apply', action='store_true', help='write settings that differ from DESIRED')
    ap.add_argument('--new-address', type=int, help='move the meter to this address (1-255)')
    ap.add_argument('--tag', default='', help='serial/asset number from the meter label, for the log')
    ap.add_argument('--watch', action='store_true', help='print live pressure until Ctrl+C')
    args = ap.parse_args()

    meter = Meter(args.port, args.baud, args.address)
    try:
        settings = meter.read_settings()

        if args.watch:
            while True:
                print(f'{datetime.now():%H:%M:%S}  {format_pressure(meter.read_pressure(), settings)}')
                time.sleep(max(settings['IDC_T'] / 10, 0.5))

        print(f'Meter at {args.port}, address {args.address}, range {describe("RANGE", settings["RANGE"], settings)}')
        print(f'Pressure: {format_pressure(meter.read_pressure(), settings)}\n')
        show(settings, DESIRED)

        if not args.apply:
            print(f'\n{len(diffs(settings, DESIRED))} setting(s) differ (*). Run with --apply to write them.')
            return 0

        print()
        return 0 if apply_settings(meter, args.port, args.new_address, args.tag) else 1
    except (ModbusError, ValueError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    finally:
        meter.close()


if __name__ == '__main__':
    sys.exit(main())
