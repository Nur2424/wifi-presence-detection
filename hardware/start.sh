#!/bin/bash

IDF_PATH="$HOME/esp/esp-idf"
FIRMWARE_DIR="$HOME/esp/esp-csi/examples/get-started/csi_recv_router"
LOGGER="$(dirname "$0")/csi_logger.py"

echo ""
echo "=============================="
echo "  ESP32 CSI Data Collector"
echo "=============================="
echo ""

# ── STEP 1: Load ESP-IDF ──────────────────────────────
echo "[1/3] Loading ESP-IDF..."
source "$IDF_PATH/export.sh" > /dev/null 2>&1

if ! command -v idf.py &> /dev/null; then
    echo ""
    echo "ERROR: idf.py not found."
    echo "  Expected ESP-IDF at: $IDF_PATH"
    echo "  Run the setup guide again from Step 3."
    exit 1
fi
echo "      OK"

# ── STEP 2: Find ESP32 port ───────────────────────────
echo "[2/3] Looking for ESP32 on USB..."

PORTS=($(ls /dev/cu.usbserial* /dev/cu.wchusbserial* /dev/cu.SLAB_USBtoUART* 2>/dev/null))

if [ ${#PORTS[@]} -eq 0 ]; then
    echo ""
    echo "ERROR: No ESP32 detected."
    echo ""
    echo "  Things to check:"
    echo "  1. Is the USB cable plugged into both the board and your Mac?"
    echo "  2. Some cheap cables are power-only (no data). Try a different cable."
    echo "  3. Unplug and replug the board, then run this script again."
    exit 1
fi

if [ ${#PORTS[@]} -eq 1 ]; then
    PORT="${PORTS[0]}"
    echo "      Found: $PORT"
else
    echo "      Multiple USB devices found:"
    for i in "${!PORTS[@]}"; do
        echo "        $i) ${PORTS[$i]}"
    done
    read -p "      Which one is the ESP32? Enter number: " choice
    PORT="${PORTS[$choice]}"
fi

# ── STEP 3: Flash firmware ────────────────────────────
echo "[3/3] Flashing firmware to ESP32..."
echo ""
echo "  If it hangs at 'Connecting......'"
echo "  hold the BOOT button on the board, then release it"
echo "  the moment you see 'Writing...' appear."
echo ""

cd "$FIRMWARE_DIR"
idf.py -p "$PORT" flash

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Flashing failed."
    echo ""
    echo "  Most likely fix: hold the BOOT button on the board"
    echo "  while the script runs, release when 'Writing...' appears."
    echo "  Then run this script again."
    exit 1
fi

# ── START LOGGER ──────────────────────────────────────
echo ""
echo "=============================="
echo "  Firmware flashed. Starting data collection."
echo "=============================="
echo ""

# Auto-update the port in csi_logger.py
sed -i '' "s|PORT   = \".*\"|PORT   = \"$PORT\"|" "$LOGGER"

python3 "$LOGGER"