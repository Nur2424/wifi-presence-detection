"""
utils.py — shared utilities for the WIFIAD full-study modeling notebooks (01–06)

Import with:
    from utils import (
        FEATURE_COLS, WINDOW_SIZES, TEST_SESSIONS,
        load_data, make_windows, session_split, evaluate, plot_ablation,
    )
"""

import numpy as np
import os
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score,
    recall_score, roc_auc_score,
)

# --- Paths -------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
PROCESSED_CSV = os.path.join(_HERE, "../data/full-study/processed/processed.csv")

# --- Feature columns ----------------------------------------------------------

# Guard and pilot subcarrier indices to drop (out of 64 raw amp columns)
_DROP_IDX  = set([0, 1] + list(range(27, 37)) + [63])
AMP_COLS   = [f"amp_{i}" for i in range(64) if i not in _DROP_IDX]   # 51 cols
SCALAR_COLS = ["csi_mean", "csi_std", "csi_max", "csi_energy"]
FEATURE_COLS = AMP_COLS + SCALAR_COLS                                # 55 cols

# --- Experimental settings ----------------------------------------------------

WINDOW_SIZES = {
    "W1_snapshot": 1,
    "W2_1s":       80,
    "W3_5s":       400,
    "W4_10s":      800,
}

# Sessions held out for evaluation (matched by substring)
TEST_SESSIONS = ["session5_morning_empty", "session7_morning_occupied"]

# --- Data loading ----------------------------------------------------

def load_data(path: str = PROCESSED_CSV) -> pd.DataFrame:
    """
    Load processed.csv and return the full DataFrame.

    The processed file is already clean no rows are dropped here.
    Each notebook is responsible for its own feature selection.
    """
    df = pd.read_csv(path)
    df["label_bin"] = (df["label"] == "occupied").astype(int)
    return df


# ── Windowing ─────────────────────────────────────────────────────────────────

def make_windows(
    df: pd.DataFrame,
    window_size: int,
    feature_cols: list = FEATURE_COLS,
    stride: int = None,
):
    """
    Slide a fixed length window over each recording session independently.

    Windows never cross session boundaries each session is windowed
    separately and the results are concatenated.

    Parameters
    ----------
    df           : DataFrame with a 'session' column and 'label_bin' column.
    window_size  : Number of rows per window.
    feature_cols : Columns to include as features (default: all 55).
    stride       : Step between window starts. Defaults to window_size
                   (non overlapping windows).

    Returns
    -------
    X        : ndarray of shape (n_windows, window_size, n_features)
    y        : ndarray of shape (n_windows,) majority label per window
    sessions : list of session names, one per window
    """
    if stride is None:
        stride = window_size

    X_list, y_list, sess_list = [], [], []

    for sess_name, group in df.groupby("session", sort=False):
        feats  = group[feature_cols].values
        labels = group["label_bin"].values
        n      = len(feats)

        for start in range(0, n - window_size + 1, stride):
            end = start + window_size
            X_list.append(feats[start:end])
            y_list.append(int(labels[start:end].mean() >= 0.5))
            sess_list.append(sess_name)

    if not X_list:
        raise ValueError(
            f"No windows produced dataset too small for window_size={window_size}."
        )

    return np.array(X_list), np.array(y_list), sess_list


# --- Train / test split ------------------------------------------------------

def session_split(X, y, sessions, test_sessions=TEST_SESSIONS):
    """
    Split windows into train and test sets by session name.

    A window goes to the test set if its session name contains any of the
    substrings in `test_sessions` all others go to train.

    Returns
    -------
    X_train, X_test, y_train, y_test
    """
    sessions = np.array(sessions)
    test_mask = np.zeros(len(sessions), dtype=bool)
    for substr in test_sessions:
        test_mask |= np.char.find(sessions.astype(str), substr) >= 0

    return X[~test_mask], X[test_mask], y[~test_mask], y[test_mask]


# --- Evaluation ---------------------------------------------------------

def evaluate(y_true, y_pred, y_score=None, verbose: bool = True) -> dict:
    """
    Compute classification metrics and optionally print a summary.

    Parameters
    ----------
    y_true  : Ground truth binary labels.
    y_pred  : Predicted binary labels.
    y_score : Continuous scores for ROC-AUC (optional)
    verbose : If True, print a one line summary.

    Returns
    -------
    dict with keys: accuracy, f1, precision, recall, roc_auc (None if no scores)
    """
    metrics = {
        "accuracy":  accuracy_score(y_true, y_pred),
        "f1":        f1_score(y_true, y_pred, zero_division=0),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall":    recall_score(y_true, y_pred, zero_division=0),
        "roc_auc":   roc_auc_score(y_true, y_score) if y_score is not None else None,
    }

    if verbose:
        auc_str = f"  AUC={metrics['roc_auc']:.4f}" if metrics["roc_auc"] else ""
        print(
            f"  Acc={metrics['accuracy']:.4f}  "
            f"F1={metrics['f1']:.4f}  "
            f"Prec={metrics['precision']:.4f}  "
            f"Rec={metrics['recall']:.4f}"
            f"{auc_str}"
        )

    return metrics


# --- Ablation plot ------------------------------------------------------------------

def plot_ablation(results: dict, metric: str = "f1", title: str = "", save_path: str = None):
    """
    Line chart showing one metric across window sizes.

    Parameters
    ----------
    results   : {window_label: metrics_dict} e.g. {"W1": {...}, "W2": {...}}
    metric    : Key in each metrics_dict to plot (default: 'f1').
    title     : Plot title.
    save_path : If provided, saves the figure to this path.
    """
    labels = list(results.keys())
    values = [results[k][metric] for k in labels]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(labels, values, marker="o", color="#2C7BB6", linewidth=2, markersize=8)

    for label, val in zip(labels, values):
        ax.annotate(
            f"{val:.4f}",
            xy=(label, val),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )

    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Window size")
    ax.set_ylabel(metric.upper())
    ax.set_title(title or f"{metric.upper()} across window sizes")
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()