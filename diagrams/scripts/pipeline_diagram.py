"""
pipeline_diagram.py — WiFi presence-detection system pipeline.
Outputs: diagrams/pipeline_diagram.png  (180 dpi)
         diagrams/pipeline_diagram.svg
"""

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

matplotlib.rcParams.update({
    'font.family':      'DejaVu Sans',
    'mathtext.fontset': 'dejavusans',
})

C = dict(
    hardware   = "#F5CECE",
    warmup     = "#EEEEEE",
    signal     = "#C5DFF0",
    features   = "#FFF6C0",
    window     = "#F5DEC0",
    supervised = "#E0D0ED",
    anomaly    = "#C8ECC8",
    output     = "#C0E8E0",
    container  = "#F5F5F5",
    border     = "#1A1A1A",
    arrow      = "#1A1A1A",
    text       = "#1A1A1A",
)

FW, FH = 7.5, 11.0
fig, ax = plt.subplots(figsize=(FW, FH))
ax.set_xlim(0, FW); ax.set_ylim(0, FH)
ax.axis('off')
fig.patch.set_facecolor('white')

CX = FW / 2
BW = 5.0

def fbox(cx, cy, w, h, color, text, fs=9.2, lw=1.8, ls='-', border=None):
    b = border or C["border"]
    ax.add_patch(FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.1",
        facecolor=color, edgecolor=b,
        linewidth=lw, linestyle=ls, zorder=2,
    ))
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fs, color=C["text"], linespacing=1.65, zorder=3)

def arr(x, y0, y1, sA=6, sB=4):
    ax.annotate('', xy=(x, y1), xytext=(x, y0),
                arrowprops=dict(arrowstyle='->', color=C["arrow"],
                                lw=1.4, mutation_scale=13,
                                shrinkA=sA, shrinkB=sB), zorder=4)

def seg(x0, y0, x1, y1):
    ax.plot([x0, x1], [y0, y1], color=C["arrow"], lw=1.4,
            solid_capstyle='round', zorder=3)

GAP = 0.50
y   = FH - 0.50

# 1 — ambient label
ax.text(CX, y, 'Ambient 2.4 GHz WiFi traffic',
        ha='center', va='center', fontsize=10.5,
        color=C["text"], style='normal',fontweight='bold', zorder=3)
y -= 0.32; arr(CX, y, y - GAP); y -= GAP

# 2 — hardware
H = 0.78; cy = y - H/2
fbox(CX, cy, BW, H, C["hardware"],
     'ESP32-WROOM-32\n921600 baud  •  ~80 fps  •  64 I/Q pairs / frame',
     fs=9.4, lw=2.0)
y = cy - H/2; arr(CX, y, y - GAP); y -= GAP

# 3 — warmup
H = 0.50; cy = y - H/2
fbox(CX, cy, BW, H, C["warmup"],
     'Discard first 5s (channel stabilisation)')
y = cy - H/2; arr(CX, y, y - GAP); y -= GAP

# 4 — I/Q → amplitude
H = 0.60; cy = y - H/2
fbox(CX, cy, BW, H, C["signal"],
     r'$\sqrt{i^2 + q^2}$ per I/Q pair' + '\n64 raw amplitudes / frame')
y = cy - H/2; arr(CX, y, y - GAP); y -= GAP

# 5 — feature engineering
H = 1.02; cy = y - H/2
fbox(CX, cy, BW, H, C["features"],
     'Remove guard bands  [ 0–1,   27–36,   63 ]\n'
     '51 active amplitudes + 4 scalars / frame\n'
     'csi_mean  •  csi_std  •  csi_max  •  csi_energy\n'
     '= 55 features / frame', fs=8.9)
y = cy - H/2; arr(CX, y, y - GAP); y -= GAP

# 6 — window aggregation
H = 0.92; cy = y - H/2
fbox(CX, cy, BW, H, C["window"],
     'Sliding window  ·  T frames,  stride S\n'
     'W1 = 1   •   W2 = 80   •   W3 = 400   •   W4 = 800\n'
     r'$[\,\mu,\,\sigma\,]$ across T  $\rightarrow$  110-dim vector', fs=8.9)
y = cy - H/2

# fork BW
FORK_D = 0.30;  BH = 1.60;  BW2 = (BW - 0.20) / 2;  SEP = 0.45
sup_cx = CX - BW2/2 - SEP/2;  ano_cx = CX + BW2/2 + SEP/2
split_y = y - FORK_D;  btop = split_y - 0.50
bcy = btop - BH/2;  bbot = bcy - BH/2


seg(CX, y, CX, split_y)
seg(sup_cx, split_y, ano_cx, split_y)
arr(sup_cx, split_y, btop + 0.1, sA=0)
arr(ano_cx, split_y, btop + 0.1, sA=0)

fbox(sup_cx, bcy, BW2, BH, C["anomaly"],
     'Supervised\n\nLR  •  CNN\nTransformer\n\n(both labels)', fs=8.8)
fbox(ano_cx, bcy, BW2, BH, C["anomaly"],
     'Anomaly\ndetection\n\nAE  •  OCSVM\n\n(empty room only)', fs=8.8)

# merge
SPAD = 0.13   # 0.1 pad + 0.03 clearance

MERGE_D = 0.30;  merge_y = bbot - MERGE_D
seg(sup_cx, bbot - SPAD, sup_cx, merge_y)
seg(ano_cx, bbot - SPAD, ano_cx, merge_y)
seg(sup_cx, merge_y, ano_cx, merge_y)

OH = 0.40;  out_cy = merge_y - GAP - OH/2
arr(CX, merge_y, out_cy + OH/2, sA=0)
fbox(CX, out_cy, BW * 0.52, OH, C["signal"],
     '  Empty  /  Occupied', fs=10.5, lw=1.3)  

# 7 — output
OH = 0.40;  out_cy = merge_y - GAP - OH/2
arr(CX, merge_y, out_cy + OH/2)
fbox(CX, out_cy, BW * 0.52, OH, C["signal"],
     '  Empty  /  Occupied', fs=10.5, lw=1.3)

import os
os.makedirs('diagrams', exist_ok=True)
plt.savefig('diagrams/pipeline_diagram.png', dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.savefig('diagrams/pipeline_diagram.svg', bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close() 