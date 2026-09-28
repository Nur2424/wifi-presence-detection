import argparse, csv, re, sys, tty, termios, threading, os, time
from collections import deque
from datetime import datetime
import serial  # type: ignore

# ── CONFIG ──────────────────────────────────────────────
BAUD            = 921600
BUFFER_SECONDS  = 5
# ────────────────────────────────────────────────────────

LABELS = {'0': 'empty', '1': 'occupied'}

# ── SHARED STATE ────────────────────────────────────────
state         = ['idle']
current_label = [None]
warmup_until  = [0.0]
counts        = {'empty': 0, 'occupied': 0}
running       = [True]
buffer        = deque()
buf_lock      = threading.Lock()
# ────────────────────────────────────────────────────────

def get_key():
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def print_status(rssi=None):
    s = state[0]
    if s == 'warming':
        remaining = max(0, warmup_until[0] - time.time())
        tag = f"WARMING UP {remaining:.0f}s  [{current_label[0].upper()}]"
    elif s == 'recording':
        tag = f"● REC  [{current_label[0].upper()}]"
    elif s == 'paused':
        tag = "❚❚ PAUSED"
    else:
        tag = "IDLE"
    total = sum(counts.values())
    rssi_str = f"  rssi={rssi} dBm" if rssi else ""
    print(f"\r  {tag}  |  "
          f"empty={counts['empty']} occupied={counts['occupied']} total={total}"
          f"{rssi_str}   ",
          end='', flush=True)

def key_listener():
    while running[0]:
        key = get_key()

        if key in LABELS:
            current_label[0] = LABELS[key]
            if state[0] in ('idle', 'paused'):
                print(f"\n  Label set to [{LABELS[key].upper()}]  —  press S to start recording.\n")
            else:
                print(f"\n  Label switched to [{LABELS[key].upper()}]\n")

        elif key in ('p', 'P'):
            if state[0] in ('recording', 'warming'):
                with buf_lock:
                    buffer.clear()
                state[0] = 'paused'
                print(f"\n  ❚❚  PAUSED  (last {BUFFER_SECONDS}s discarded)\n")

        elif key in ('s', 'S'):
            if state[0] in ('idle', 'paused'):
                if current_label[0] is None:
                    print(f"\n  ⚠  Choose a label first (0=empty  1=occupied)\n")
                else:
                    state[0] = 'warming'
                    warmup_until[0] = time.time() + BUFFER_SECONDS
                    print(f"\n  ▶  [{current_label[0].upper()}]  —  warming up {BUFFER_SECONDS}s …\n")

        elif key in ('q', 'Q', '\x03'):
            with buf_lock:
                buffer.clear()
            running[0] = False
            print(f"\n\nDone.  empty={counts['empty']}  occupied={counts['occupied']}")
            sys.exit(0)

def amplitudes(csi):
    return [round((csi[i]**2 + csi[i+1]**2)**0.5, 3)
            for i in range(0, len(csi), 2)]

def parse(line):
    if not line.startswith("CSI_DATA"):
        return None
    if '\x00' in line:
        return None
    parts = line.split(",")
    m = re.search(r'\[([^\]]+)\]', line)
    if not m or len(parts) < 15:
        return None
    csi = list(map(int, m.group(1).split(",")))
    return {'rssi': parts[3], 'noise': parts[14], 'amps': amplitudes(csi)}

def writer_thread(f, w):
    while running[0]:
        now = time.time()
        with buf_lock:
            while buffer and (now - buffer[0][0]) >= BUFFER_SECONDS:
                _, label, row = buffer.popleft()
                w.writerow(row)
                f.flush()
                counts[label] += 1
        time.sleep(0.05)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/cu.usbserial-0001',
                        help='Serial port of the ESP32')
    args = parser.parse_args()

    name    = input("Session name: ").strip() or "session"
    outfile = (f"{os.path.dirname(os.path.abspath(__file__))}/../data/feasibility-study/raw/"
               f"{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    print("--------------------------------------------------------------------------------------------")
    print(f"\n  Saving to:  {outfile}")
    print("--------------------------------------------------------------------------------------------")
    print(f"  Keys:  0=empty  1=occupied  |  S=start/resume  P=pause  Q=quit")
    print("--------------------------------------------------------------------------------------------")
    print(f"  Flow:  pick label (0/1)  =>  press S  =>  {BUFFER_SECONDS}s warmup  =>  ● REC")
    print(f"         press P  =>  last {BUFFER_SECONDS}s discarded  =>  PAUSED  =>  press S to resume\n")
    print("--------------------------------------------------------------------------------------------")
    print(f"  >>> Pick a label (0/1), then press S to start.\n")

    threading.Thread(target=key_listener, daemon=True).start()

    ser = serial.Serial(args.port, BAUD, timeout=1)

    with open(outfile, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['time', 'label', 'rssi', 'noise'] + [f'amp_{i}' for i in range(64)])

        threading.Thread(target=writer_thread, args=(f, w), daemon=True).start()

        while running[0]:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                p    = parse(line)
                if not p:
                    continue

                now = time.time()

                if state[0] == 'warming' and now >= warmup_until[0]:
                    state[0] = 'recording'
                    print(f"\n  ● RECORDING [{current_label[0].upper()}]\n")

                if state[0] == 'recording':
                    row = ([datetime.now().isoformat(), current_label[0],
                            p['rssi'], p['noise']] + p['amps'])
                    with buf_lock:
                        buffer.append((now, current_label[0], row))

                print_status(p['rssi'])

            except Exception as e:
                if running[0]:
                    print(f"\nError: {e}")

if __name__ == '__main__':
    main()