import serial, csv, re, sys, tty, termios, threading, os
from datetime import datetime

# ── CONFIG ─────────────────────────────────────────────
PORT   = "/dev/cu.usbserial-0001"   # change to your port (Phase B)
BAUD   = 115200
# ───────────────────────────────────────────────────────

LABELS = {'0': 'empty', '1': 'sitting', '2': 'walking'}

current_label = ['empty']
counts        = {'empty': 0, 'sitting': 0, 'walking': 0}
running       = [True]

def get_key():
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def key_listener():
    while running[0]:
        key = get_key()
        if key in LABELS:
            current_label[0] = LABELS[key]
            print(f"\n\n  >>> switched to  [ {current_label[0].upper()} ]\n")
        elif key in ('q', 'Q', '\x03'):
            running[0] = False
            print(f"\n\nDone.  empty={counts['empty']}  sitting={counts['sitting']}  walking={counts['walking']}")
            sys.exit(0)

def amplitudes(csi):
    return [round((csi[i]**2 + csi[i+1]**2)**0.5, 3)
            for i in range(0, len(csi)-1, 2)]

def parse(line):
    if not line.startswith("CSI_DATA"):
        return None
    parts = line.split(",")
    m = re.search(r'\[([^\]]+)\]', line)
    if not m or len(parts) < 15:
        return None
    csi = list(map(int, m.group(1).split(",")))
    return {'rssi': parts[3], 'noise': parts[14], 'amps': amplitudes(csi)}

def main():
    name = input("Session name (e.g. room_a, dorm_test): ").strip() or "session"
    outfile = f"{os.path.dirname(os.path.abspath(__file__))}/../data/raw/{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    print(f"\n  Saving to:  {outfile}")
    print(f"  Keys:  0 = empty   1 = sitting   2 = walking   Q = quit\n")
    print(f"  >>> starting with label  [ EMPTY ]\n")

    threading.Thread(target=key_listener, daemon=True).start()

    ser   = serial.Serial(PORT, BAUD, timeout=1)
    total = 0

    with open(outfile, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time', 'label', 'rssi', 'noise'] + [f'amp_{i}' for i in range(64)])

        while running[0]:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                p = parse(line)
                if p:
                    label = current_label[0]
                    w.writerow([datetime.now().isoformat(), label,
                                 p['rssi'], p['noise']] + p['amps'])
                    f.flush()
                    total += 1
                    counts[label] += 1
                    print(f"\r  empty={counts['empty']}  sitting={counts['sitting']}  "
                          f"walking={counts['walking']}  total={total}  rssi={p['rssi']} dBm",
                          end='', flush=True)
            except Exception as e:
                if running[0]:
                    print(f"\nError: {e}")

if __name__ == '__main__':
    main()
