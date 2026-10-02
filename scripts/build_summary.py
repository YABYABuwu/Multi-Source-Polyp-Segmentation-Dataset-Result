"""Recalculate model comparison from the published per-image CSV files."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODELS = {"YOLO26m": "yolo26m", "YOLO26s": "yolo26s"}
SUBSETS = {
    "full_test": "full_test_per_image_metrics.csv",
    "primary_wli": "primary_wli_balanced_test.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def summarize(rows: list[dict[str, str]]) -> dict[str, float | int]:
    counts = Counter((row["gt_present"], row["pred_present"]) for row in rows)
    tp, fn = counts[("True", "True")], counts[("True", "False")]
    tn, fp = counts[("False", "False")], counts[("False", "True")]
    positives = [row for row in rows if row["gt_present"] == "True"]
    assert tp + fn + tn + fp == len(rows)
    assert positives and tn + fp
    return {
        "images": len(rows), "positive": len(positives), "negative": tn + fp,
        "tp": tp, "fn": fn, "tn": tn, "fp": fp,
        "sensitivity": tp / (tp + fn),
        "specificity": tn / (tn + fp),
        "balanced_accuracy": (tp / (tp + fn) + tn / (tn + fp)) / 2,
        "mean_positive_dice": statistics.mean(float(row["dice"]) for row in positives),
        "mean_positive_iou": statistics.mean(float(row["iou"]) for row in positives),
    }


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for subset, filename in SUBSETS.items():
        by_model = {name: read_csv(ROOT / "runs" / folder / filename)
                    for name, folder in MODELS.items()}
        reference = {row["id"]: row["gt_present"] for row in by_model["YOLO26m"]}
        for name, rows in by_model.items():
            assert len(rows) == len({row["id"] for row in rows}), f"Duplicate IDs in {name} {subset}"
            assert {row["id"]: row["gt_present"] for row in rows} == reference, (
                f"Models use different images or labels in {subset}")
        result[subset] = {name: summarize(rows) for name, rows in by_model.items()}

    assert result["full_test"]["YOLO26m"]["images"] == 1390
    assert result["primary_wli"]["YOLO26m"]["images"] == 874
    (ROOT / "results_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    metrics = [
        ("Sensitivity", "sensitivity"),
        ("Specificity", "specificity"),
        ("Mean positive Dice", "mean_positive_dice"),
        ("Mean positive IoU", "mean_positive_iou"),
    ]
    colors = {"YOLO26m": "#2378b5", "YOLO26s": "#e68128"}
    fig, axes = plt.subplots(1, 4, figsize=(15, 4), sharey=True)
    for ax, (label, key) in zip(axes, metrics):
        for index, name in enumerate(MODELS):
            value = result["full_test"][name][key]
            ax.bar(index, value * 100, color=colors[name], width=.62)
            ax.text(index, value * 100 + 1.0, f"{value * 100:.1f}%", ha="center", fontsize=10)
        ax.set_xticks((0, 1), MODELS)
        ax.set_title(label)
        ax.set_ylim(0, 105)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Full balanced test (%)")
    fig.suptitle("Polyp segmentation results · 695 positive + 695 negative images", fontsize=13)
    fig.tight_layout()
    figures = ROOT / "figures"
    figures.mkdir(exist_ok=True)
    fig.savefig(figures / "model_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("Wrote results_summary.json and figures/model_comparison.png")


if __name__ == "__main__":
    main()
