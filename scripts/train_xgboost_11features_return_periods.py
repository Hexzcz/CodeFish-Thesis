from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
import rasterio
from rasterio.warp import Resampling, reproject


ROOT = Path(__file__).resolve().parents[1]
BACKEND_RASTERS = ROOT / "backend" / "data" / "rasters"
MODELS_DIR = ROOT / "backend" / "data" / "models"
REPORTS_DIR = ROOT / "backend" / "data" / "model_reports"

FEATURES = [
    "elevation",
    "slope",
    "land_cover",
    "dist_waterway",
    "twi",
    "flow_accumulation",
    "aspect",
    "profile_curvature",
    "plan_curvature",
    "spi",
    "sti",
    "HAND",
]

FEATURE_RASTERS = {
    "elevation": BACKEND_RASTERS / "output_hh.tif",
    "slope": BACKEND_RASTERS / "viz.hh_slope.tif",
    "land_cover": BACKEND_RASTERS / "land_cover_aligned.tif",
    "dist_waterway": BACKEND_RASTERS / "distance_to_waterways.tif",
    "twi": ROOT / "terrain_features" / "twi_aligned.tif",
    "flow_accumulation": ROOT / "terrain_features" / "flow_acc_aligned.tif",
    "aspect": ROOT / "terrain_features" / "aspect_aligned.tif",
    "profile_curvature": ROOT / "terrain_features" / "profile_curvature_aligned.tif",
    "plan_curvature": ROOT / "terrain_features" / "plan_curvature_aligned.tif",
    "spi": ROOT / "terrain_features" / "spi_aligned.tif",
    "sti": ROOT / "terrain_features" / "sti_aligned.tif",
    "HAND": ROOT / "terrain_features" / "hand_aligned.tif",
}

LABEL_RASTERS = {
    "5yr": BACKEND_RASTERS / "flood_hazard_fh5yr_aligned.tif",
    "25yr": BACKEND_RASTERS / "flood_hazard_fh25yr_aligned.tif",
    "100yr": BACKEND_RASTERS / "flood_hazard_fh100yr_aligned.tif",
}

CLASS_LABELS = ["No Risk (0)", "Low to Moderate Risk (1)", "High Risk (2)"]
CLASS_IDS = [0, 1, 2]
N_CLASSES = 3

LABEL_MAPPING = {
    0: 0,
    1: 1,
    2: 1,
    3: 2,
}

FOUR_CLASS_HAND_BASELINE_CM = {
    "5yr": np.array(
        [
            [1812, 87, 43, 17],
            [421, 141, 65, 23],
            [176, 76, 200, 80],
            [43, 7, 58, 553],
        ]
    ),
    "25yr": np.array(
        [
            [1404, 120, 59, 35],
            [362, 177, 81, 22],
            [155, 65, 282, 115],
            [49, 3, 64, 809],
        ]
    ),
    "100yr": np.array(
        [
            [1199, 94, 79, 41],
            [326, 190, 87, 20],
            [146, 67, 345, 118],
            [49, 0, 54, 987],
        ]
    ),
}


def read_raster(
    path: Path,
    reference: dict[str, object] | None = None,
    resampling: Resampling = Resampling.bilinear,
) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Missing raster: {path}")

    with rasterio.open(path) as src:
        nodata = src.nodata
        if reference is not None and (
            src.height != reference["height"]
            or src.width != reference["width"]
            or src.transform != reference["transform"]
            or src.crs != reference["crs"]
        ):
            data = np.full((reference["height"], reference["width"]), np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=data,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=nodata,
                dst_transform=reference["transform"],
                dst_crs=reference["crs"],
                dst_nodata=np.nan,
                resampling=resampling,
            )
        else:
            data = src.read(1).astype(np.float32)

    if nodata is not None:
        data[data == nodata] = np.nan
    data[data <= -9999] = np.nan
    return data.reshape(-1)


def build_training_table(scenario: str, save_csv: bool) -> pd.DataFrame:
    with rasterio.open(FEATURE_RASTERS["elevation"]) as ref:
        reference = {
            "height": ref.height,
            "width": ref.width,
            "transform": ref.transform,
            "crs": ref.crs,
        }

    columns: Dict[str, np.ndarray] = {"elevation": read_raster(FEATURE_RASTERS["elevation"], reference)}
    for name in FEATURES[1:]:
        method = Resampling.nearest if name == "land_cover" else Resampling.bilinear
        columns[name] = read_raster(FEATURE_RASTERS[name], reference, method)

    columns["flood_class"] = read_raster(LABEL_RASTERS[scenario], reference, Resampling.nearest)
    df = pd.DataFrame(columns)

    valid = df[FEATURES].notna().all(axis=1)
    valid &= df["flood_class"].notna()
    valid &= df["flood_class"].isin([0, 1, 2, 3])
    valid &= df["land_cover"] != 0
    valid &= np.isfinite(df[FEATURES]).all(axis=1)

    df = df.loc[valid].reset_index(drop=True)
    df["original_flood_class"] = df["flood_class"].astype(np.int64)
    df["flood_class"] = df["original_flood_class"].map(LABEL_MAPPING).astype(np.int64)

    if save_csv:
        csv_path = ROOT / f"training_{scenario}_current_layers_12features_hand_3class.csv"
        df[FEATURES + ["original_flood_class", "flood_class"]].to_csv(csv_path, index=False)

    return df


def make_model(args: argparse.Namespace) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=N_CLASSES,
        eval_metric="mlogloss",
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        min_child_weight=args.min_child_weight,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        reg_lambda=args.reg_lambda,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )


def format_matrix(cm: np.ndarray) -> str:
    header = "| Actual \\ Predicted | No Risk (0) | Low to Moderate Risk (1) | High Risk (2) |\n"
    header += "|---|---:|---:|---:|\n"
    rows = []
    for idx, label in enumerate(CLASS_LABELS):
        rows.append(f"| {label} | " + " | ".join(f"{int(v):,}" for v in cm[idx]) + " |")
    return header + "\n".join(rows)


def save_confusion_matrix(cm: np.ndarray, scenario: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"confusion_matrix_{scenario}_12features_hand_3class.png"

    fig, ax = plt.subplots(figsize=(8, 6))
    image = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    fig.colorbar(image, ax=ax)
    ax.set_xticks(np.arange(len(CLASS_LABELS)), labels=CLASS_LABELS, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(CLASS_LABELS)), labels=CLASS_LABELS)
    threshold = cm.max() / 2.0
    for row in range(cm.shape[0]):
        for col in range(cm.shape[1]):
            ax.text(
                col,
                row,
                f"{int(cm[row, col]):,}",
                ha="center",
                va="center",
                color="white" if cm[row, col] > threshold else "black",
                fontsize=9,
            )
    plt.title(f"Confusion Matrix - {scenario} XGBoost 12 Features + HAND (3-Class)")
    plt.xlabel("Predicted Class")
    plt.ylabel("Actual Class")
    plt.tight_layout()
    plt.savefig(output_path, dpi=250)
    plt.close()
    return output_path


def metric_line(name: str, value: float) -> str:
    return f"- **{name}:** {value:.4f}"


def collapse_4class_cm_to_3class(cm4: np.ndarray) -> np.ndarray:
    """Collapse original labels 0,1,2,3 to 0,(1+2),3 for fair 3-class comparison."""
    groups = [[0], [1, 2], [3]]
    cm3 = np.zeros((3, 3), dtype=int)
    for actual_idx, actual_group in enumerate(groups):
        for pred_idx, pred_group in enumerate(groups):
            cm3[actual_idx, pred_idx] = int(cm4[np.ix_(actual_group, pred_group)].sum())
    return cm3


def metrics_from_cm(cm: np.ndarray) -> dict[str, object]:
    total = cm.sum()
    accuracy = float(np.trace(cm) / total) if total else 0.0
    support = cm.sum(axis=1)
    predicted = cm.sum(axis=0)
    precision = np.divide(np.diag(cm), predicted, out=np.zeros(cm.shape[0], dtype=float), where=predicted != 0)
    recall = np.divide(np.diag(cm), support, out=np.zeros(cm.shape[0], dtype=float), where=support != 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros(cm.shape[0], dtype=float),
        where=(precision + recall) != 0,
    )
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "macro_precision": float(np.mean(precision)),
        "macro_recall": float(np.mean(recall)),
        "macro_f1": float(np.mean(f1)),
        "weighted_precision": float(np.average(precision, weights=support)),
        "weighted_recall": float(np.average(recall, weights=support)),
        "weighted_f1": float(np.average(f1, weights=support)),
        "support": support,
    }


def train_and_evaluate(scenario: str, args: argparse.Namespace) -> str:
    print(f"\n=== {scenario} ===")
    df = build_training_table(scenario, save_csv=args.save_csv)
    print(f"Valid pixels: {len(df):,}")
    print("Class distribution:")
    print(df["flood_class"].value_counts().sort_index())

    X = df[FEATURES]
    y = df["flood_class"]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=args.test_size,
        random_state=42,
        stratify=y,
    )

    model = make_model(args)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    report_dict = classification_report(
        y_test,
        y_pred,
        labels=CLASS_IDS,
        target_names=CLASS_LABELS,
        digits=4,
        output_dict=True,
        zero_division=0,
    )
    cm = confusion_matrix(y_test, y_pred, labels=CLASS_IDS)
    macro_auc = roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro")
    per_class_auc = {}
    for idx, class_id in enumerate(CLASS_IDS):
        per_class_auc[CLASS_LABELS[idx]] = roc_auc_score((y_test == class_id).astype(int), y_prob[:, idx])

    precision, recall, f1, support = precision_recall_fscore_support(
        y_test,
        y_pred,
        labels=CLASS_IDS,
        zero_division=0,
    )

    collapsed_baseline_cm = collapse_4class_cm_to_3class(FOUR_CLASS_HAND_BASELINE_CM[scenario])
    collapsed_baseline_metrics = metrics_from_cm(collapsed_baseline_cm)
    comparison_rows = [
        "| Class | Collapsed Previous 4-Class F1 | New 3-Class F1 | Delta | Flag |",
        "|---|---:|---:|---:|---|",
    ]
    f1_by_class = {idx: float(f1[idx]) for idx in CLASS_IDS}
    baseline_f1 = collapsed_baseline_metrics["f1"]
    intermediate_improved = f1_by_class[1] > baseline_f1[1]
    high_degradation = f1_by_class[2] < baseline_f1[2] - args.significant_degradation

    for idx, class_name in enumerate(CLASS_LABELS):
        delta = f1_by_class[idx] - baseline_f1[idx]
        if idx == 1:
            flag = "improved" if delta > 0 else "not improved"
        else:
            flag = "significant degradation" if delta < -args.significant_degradation else "no significant degradation"
        comparison_rows.append(
            f"| {class_name} | {baseline_f1[idx]:.4f} | {f1_by_class[idx]:.4f} | {delta:+.4f} | {flag} |"
        )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    backend_model_path = MODELS_DIR / f"model_{scenario}.pkl"
    root_model_path = ROOT / f"model_{scenario}_current_layers_12features_hand_3class.pkl"
    joblib.dump(model, backend_model_path)
    joblib.dump(model, root_model_path)

    importance = pd.DataFrame(
        {"Feature": FEATURES, "Importance": model.feature_importances_}
    ).sort_values("Importance", ascending=False)
    importance["Rank"] = range(1, len(importance) + 1)
    importance_path = REPORTS_DIR / f"feature_importance_{scenario}_12features_hand_3class.csv"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    importance.to_csv(importance_path, index=False)

    cm_path = save_confusion_matrix(cm, scenario)

    print(f"Accuracy: {accuracy:.4f}")
    print(classification_report(y_test, y_pred, labels=CLASS_IDS, target_names=CLASS_LABELS, digits=4))
    print(f"Saved model: {backend_model_path}")

    per_class_rows = [
        "| Class | Precision | Recall | F1-Score | Support | AUC OVR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for idx, class_name in enumerate(CLASS_LABELS):
        per_class_rows.append(
            f"| {class_name} | {precision[idx]:.4f} | {recall[idx]:.4f} | "
            f"{f1[idx]:.4f} | {int(support[idx]):,} | {per_class_auc[class_name]:.4f} |"
        )

    distribution = df["flood_class"].value_counts().sort_index()
    distribution_line = ", ".join(f"{int(cls)}={int(count):,}" for cls, count in distribution.items())
    hand_row = importance.loc[importance["Feature"] == "HAND"].iloc[0]
    hand_rank = int(hand_row["Rank"])
    hand_importance = float(hand_row["Importance"])
    summary_rows = [
        "| Metric | Collapsed Previous 4-Class HAND | New 3-Class HAND | Delta |",
        "|---|---:|---:|---:|",
        f"| Accuracy | {collapsed_baseline_metrics['accuracy']:.4f} | {accuracy:.4f} | {accuracy - collapsed_baseline_metrics['accuracy']:+.4f} |",
        f"| Macro Precision | {collapsed_baseline_metrics['macro_precision']:.4f} | {report_dict['macro avg']['precision']:.4f} | {report_dict['macro avg']['precision'] - collapsed_baseline_metrics['macro_precision']:+.4f} |",
        f"| Macro Recall | {collapsed_baseline_metrics['macro_recall']:.4f} | {report_dict['macro avg']['recall']:.4f} | {report_dict['macro avg']['recall'] - collapsed_baseline_metrics['macro_recall']:+.4f} |",
        f"| Macro F1 | {collapsed_baseline_metrics['macro_f1']:.4f} | {report_dict['macro avg']['f1-score']:.4f} | {report_dict['macro avg']['f1-score'] - collapsed_baseline_metrics['macro_f1']:+.4f} |",
        f"| Weighted Precision | {collapsed_baseline_metrics['weighted_precision']:.4f} | {report_dict['weighted avg']['precision']:.4f} | {report_dict['weighted avg']['precision'] - collapsed_baseline_metrics['weighted_precision']:+.4f} |",
        f"| Weighted Recall | {collapsed_baseline_metrics['weighted_recall']:.4f} | {report_dict['weighted avg']['recall']:.4f} | {report_dict['weighted avg']['recall'] - collapsed_baseline_metrics['weighted_recall']:+.4f} |",
        f"| Weighted F1 | {collapsed_baseline_metrics['weighted_f1']:.4f} | {report_dict['weighted avg']['f1-score']:.4f} | {report_dict['weighted avg']['f1-score'] - collapsed_baseline_metrics['weighted_f1']:+.4f} |",
        f"| Macro AUC OVR | n/a from confusion matrix | {macro_auc:.4f} | n/a |",
    ]
    importance_rows = [
        "| Rank | Feature | Importance |",
        "|---:|---|---:|",
    ]
    for _, row in importance.iterrows():
        importance_rows.append(f"| {int(row['Rank'])} | {row['Feature']} | {float(row['Importance']):.6f} |")

    return "\n".join(
        [
            f"## {scenario}",
            "",
            f"- Training rows: {len(df):,}",
            f"- Class distribution: {distribution_line}",
            metric_line("Accuracy", accuracy),
            metric_line("Macro Precision", report_dict["macro avg"]["precision"]),
            metric_line("Macro Recall", report_dict["macro avg"]["recall"]),
            metric_line("Macro F1-Score", report_dict["macro avg"]["f1-score"]),
            metric_line("Weighted Precision", report_dict["weighted avg"]["precision"]),
            metric_line("Weighted Recall", report_dict["weighted avg"]["recall"]),
            metric_line("Weighted F1-Score", report_dict["weighted avg"]["f1-score"]),
            metric_line("Macro AUC OVR", macro_auc),
            "- Training used no `sample_weight`.",
            f"- Backend model: `{backend_model_path.relative_to(ROOT)}`",
            f"- Confusion matrix image: `{cm_path.relative_to(ROOT)}`",
            f"- Feature importance: `{importance_path.relative_to(ROOT)}`",
            f"- HAND importance rank: `{hand_rank}` of `{len(FEATURES)}` with importance `{hand_importance:.6f}`.",
            "",
            "### Summary Comparison Against Previous 4-Class HAND Baseline",
            "",
            "\n".join(summary_rows),
            "",
            "### Confusion Matrix",
            "",
            format_matrix(cm),
            "",
            "### Per-Class Metrics",
            "",
            "\n".join(per_class_rows),
            "",
            "### F1 Comparison Against Collapsed 4-Class HAND Baseline",
            "",
            "\n".join(comparison_rows),
            "",
            f"Merged intermediate class improved: **{'yes' if intermediate_improved else 'no'}**.",
            f"High-risk class avoided significant degradation (threshold `{args.significant_degradation:.3f}` F1): "
            f"**{'no' if high_degradation else 'yes'}**.",
            "",
            "### Feature Importance",
            "",
            "\n".join(importance_rows),
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train 3-class XGBoost flood models for 5yr, 25yr, and 100yr with 12 current-layer features including HAND."
    )
    parser.add_argument("--scenarios", nargs="+", default=["5yr", "25yr", "100yr"], choices=LABEL_RASTERS.keys())
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.06)
    parser.add_argument("--min-child-weight", type=int, default=3)
    parser.add_argument("--subsample", type=float, default=0.9)
    parser.add_argument("--colsample-bytree", type=float, default=0.9)
    parser.add_argument("--reg-lambda", type=float, default=1.0)
    parser.add_argument("--significant-degradation", type=float, default=0.02)
    parser.add_argument("--save-csv", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sections = [
        "# XGBoost 3-Class 12-Feature Flood Model Evaluation with HAND",
        "",
        "Models were trained as 3-class classifiers: 0=no risk, 1=low to moderate risk, 2=high risk.",
        "Relabeling was applied before train/test splitting: original 0 -> 0, original 1/2 -> 1, original 3 -> 2.",
        "Feature rasters were read from the same aligned map layers used by the backend/current layer stack.",
        "HAND was derived from the DEM using fill depressions, D8 flow direction, D8 flow accumulation, stream extraction by thresholding, and elevation above stream.",
        "Class-weighted training was removed; no `sample_weight` was passed to XGBoost.",
        "All XGBoost hyperparameters, train/test split settings, and random seeds were kept identical to the prior baseline experiments.",
        "",
        "Features: " + ", ".join(f"`{feature}`" for feature in FEATURES),
        "",
    ]

    for scenario in args.scenarios:
        sections.append(train_and_evaluate(scenario, args))

    report = "\n".join(sections)
    report_path = ROOT / "model_evaluation_results.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nWrote report: {report_path}")


if __name__ == "__main__":
    main()
