# WiFi CSI Indoor Presence Detection — Full Study

Binary room occupancy classification from ESP32 Channel State Information (CSI).
This folder contains the complete study pipeline: data collected across **7 sessions
on multiple days**, 5 models, and a stride ablation experiment that
identifies the best training configuration for each model.

> **This is the full study.** An earlier feasibility pass lives in
> `feasibility-study-notebooks/` and used a single two session dataset to
> confirm viability. The notebooks here use the full 7-session dataset,
> proper cross day held out evaluation, and a more rigorous experimental design.

---

## Notebooks

| # | Notebook | What it does |
|---|----------|--------------|
| 00 | `00_preprocessing.ipynb` | Loads raw CSI CSVs, extracts 51 subcarrier amplitudes + 4 scalar stats, segments into windows (W1–W4), saves train/test splits |
| 01 | `01_baseline_lr.ipynb` | Logistic Regression baseline across all 4 window sizes (seed 42) |
| 02 | `02_ocsvm.ipynb` | One Class SVM trained on empty room windows only; RBF kernel, nu=0.05 |
| 03 | `03_autoencoder.ipynb` | FC autoencoder (110 => 64 => 16 => 64 => 110) reconstruction error anomaly detector |
| 04 | `04_cnn.ipynb` | 1D CNN local temporal pattern classifier (W2–W4; W1 excluded by design) |
| 05 | `05_transformer.ipynb` | CLS token Transformer with sinusoidal positional encoding |
| 06 | `06_overlapping_windows.ipynb` | Training stride sweep (W2–W4); best stride selected per window via LR AUC averaged over 3 seeds; all 5 models re-evaluated at best stride |
| 07 | `07_final_results.ipynb` | Consolidated comparison baseline tables, heatmap, ΔF1 chart, conclusions |

---

## Data

**Features:** 55 per frame 51 subcarrier amplitudes (magnitude of complex I/Q
pairs) + `rssi`, `noise_floor`, `csi_mean`, `csi_std`.

**Sessions:** 7 recording sessions across multiple days and times of day.
Labels: `empty` (room unoccupied) and `exist` (room occupied).

**Window sizes:**

| ID | Frames | Duration | Aggregated shape |
|----|--------|----------|-----------------|
| W1 | 1      | ~12 ms   | (55,) — frame level |
| W2 | 80     | ~1 s     | (110,) — mean+std |
| W3 | 400    | ~5 s     | (110,) |
| W4 | 800    | ~10 s    | (110,) |

Windows aggregate (N, T, 55) => (N, 110) via mean and std concatenated across
the time axis (`aggregate_window()`).

**Test set (held-out, cross day):** `session5_morning_empty` and
`session7_morning_occupied`. Test windows are always non-overlapping regardless
of training stride.

---

## Key Results

| Configuration | F1 | AUC | Latency |
|---|---|---|---|
| **Autoencoder @ W2, 0.1 s stride** | **0.9725** | 0.9835 | ~1 s |
| CNN @ W2, 0.1 s stride | 0.9612 | **0.9857** | ~1 s |
| Transformer @ W2, 0.1 s stride | 0.9572 | 0.9825 | ~1 s |
| OCSVM @ W4, non-overlapping | 0.9536 | 0.9935 | ~10 s |
| LR @ W4, 7 s stride | 0.9510 | 0.9549 | ~10 s |

The single most impactful finding: **overlapping training windows** (dense stride)
close most of the gap between simple and deep models. LR at W4 with a 7 s stride
(F1 0.951) matches the deep models sample starvation, not model capacity, was
the bottleneck at longer window sizes.

See `07_final_results.ipynb` for full tables, charts, and interpretation.

---

## How to Run

Run notebooks in order: `00` => `01` => … => `07`.
Notebook `00` must run first it generates the windowed datasets that all
subsequent notebooks load.

**Dependencies:**

```
numpy
pandas
scikit-learn
torch
matplotlib
jupyter
pyserial          # only needed for hardware data collection
```

Install:

```bash
pip install numpy pandas scikit-learn torch matplotlib jupyter
```

---

## Hardware & Data Collection

Raw data was collected with an **ESP32** running Espressif's CSI enabled firmware.
The logger script is at `hardware/csi_logger.py`.

**Usage:**

```bash
python hardware/csi_logger.py --port /dev/cu.usbserial-0001
```

Keys during recording: `0` = empty, `1` = exist, `S` = start/resume,
`P` = pause, `Q` = quit. A 5 second warmup is discarded after each label
switch to avoid transient channel effects at boundaries.

Raw CSVs are saved to `esp32/data/full-study/raw/` and picked up by `00_preprocessing.ipynb`.
