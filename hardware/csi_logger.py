import argparse, csv, re, sys, tty, termios, threading, os, time
from collections import deque
from datetime import datetime
import serial  # type: ignore
 
# ── CONFIG ───────────────────────────────────────────────────────────────────
BAUD           = 921600
WARMUP_SECONDS = 5
LABELS         = {'0': 'empty', '1': 'exist'}
 
# ── SHARED STATE ─────────────────────────────────────────────────────────────
state         = ['idle']        # idle | warming | recording | paused
current_label = [None]
warmup_until  = [0.0]
counts        = {'empty': 0, 'exist': 0}
running       = [True]
buf           = deque()         # (timestamp, label, csv_row)
buf_lock      = threading.Lock()
 
 
# ── HELPERS ──────────────────────────────────────────────────────────────────
def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
 
 
def amplitudes(csi_str):
    nums = list(map(int, csi_str.strip('[]').split(',')))
    return [round((nums[i]**2 + nums[i+1]**2)**0.5, 3)
            for i in range(0, len(nums) - 1, 2)]
 
 
def parse(line):
    if not line.startswith("CSI_DATA"):
        return None
    parts = line.split(",")
    m = re.search(r'"(\[.+?\])"', line)
    if not m or len(parts) < 4:
        return None
    try:
        csi   = amplitudes(m.group(1))
        rssi  = parts[3]
        noise = parts[14] if len(parts) > 14 else '0'
        return {'rssi': rssi, 'noise': noise, 'amps': csi}
    except Exception:
        return None
 
 
def print_status(rssi):
    s = state[0]
    if s == 'warming':
        remaining = max(0, warmup_until[0] - time.time())
        tag = f"WARMING {remaining:.0f}s [{current_label[0].upper()}]"
    elif s == 'recording':
        tag = f"REC [{current_label[0].upper()}]"
    elif s == 'paused':
        tag = "PAUSED"
    else:
        tag = "IDLE"
    total = sum(counts.values())
    print(f"\r  {tag}  |  empty={counts['empty']}  exist={counts['exist']}  total={total}  rssi={rssi} dBm   ",
          end='', flush=True)
 
 
# ── THREADS ──────────────────────────────────────────────────────────────────
def key_listener():
    while running[0]:
        key = get_key()
 
        if key in LABELS:
            current_label[0] = LABELS[key]
            if state[0] in ('idle', 'paused'):
                print(f"\n  Label -> [{LABELS[key].upper()}]  Press S to start.\n")
            else:
                print(f"\n  Label switched -> [{LABELS[key].upper()}]\n")
 
        elif key in ('s', 'S'):
            if state[0] in ('idle', 'paused'):
                if current_label[0] is None:
                    print(f"\n  WARNING: Pick a label first: 0=empty  1=exist\n")
                else:
                    state[0]        = 'warming'
                    warmup_until[0] = time.time() + WARMUP_SECONDS
                    print(f"\n  >> [{current_label[0].upper()}]  warming up {WARMUP_SECONDS}s ...\n")
 
        elif key in ('p', 'P'):
            if state[0] in ('recording', 'warming'):
                with buf_lock:
                    buf.clear()
                state[0] = 'paused'
                print(f"\n  PAUSED\n")
 
        elif key in ('q', 'Q', '\x03'):
            running[0] = False
            print(f"\n\nDone.  empty={counts['empty']}  exist={counts['exist']}")
            sys.exit(0)
 
 
def writer_thread(f, w):
    while running[0]:
        now = time.time()
        with buf_lock:
            while buf and (now - buf[0][0]) >= WARMUP_SECONDS:
                _, label, row = buf.popleft()
                w.writerow(row)
                counts[label] += 1
        f.flush()
        time.sleep(0.05)
 
 
# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/cu.usbserial-0001')
    args = parser.parse_args()
 
    name   = input("Session name: ").strip() or "session"
    base   = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(base, '..', 'esp32', 'data', 'full-study', 'raw')
    os.makedirs(outdir, exist_ok=True)
    outfile = os.path.join(outdir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
 
    print("\n" + "-" * 70)
    print(f"  Saving -> {os.path.abspath(outfile)}")
    print(f"  Port   -> {args.port}")
    print("-" * 70)
    print("  Keys:  0=empty  1=exist  |  S=start/resume  P=pause  Q=quit")
    print("  Flow:  pick label -> S -> 5s warmup -> REC")
    print("-" * 70)
    print("\n  >>> Pick a label (0 or 1), then press S.\n")
 
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
                    print(f"\n  RECORDING [{current_label[0].upper()}]\n")
 
                if state[0] == 'recording':
                    row = ([datetime.now().isoformat(), current_label[0],
                            p['rssi'], p['noise']] + p['amps'])
                    with buf_lock:
                        buf.append((now, current_label[0], row))
 
                print_status(p['rssi'])
 
            except Exception as e:
                if running[0]:
                    print(f"\nError: {e}")
 
    ser.close()
 
 
if __name__ == '__main__':
    main()