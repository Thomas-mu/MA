"""Read frozen pilot models and produce development diagnostics; never fit."""
from pathlib import Path
import sys
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pilot_method_comparison as pilot
import common_comparison as common


def stats(values):
    values = np.asarray(values, dtype=np.float64)
    assert np.isfinite(values).all()
    return {"n": len(values), "mean": float(values.mean()),
            "sd_population": float(values.std(ddof=0)), "min": float(values.min()),
            "p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95)),
            "p99": float(np.percentile(values, 99)), "max": float(values.max())}


def main():
    frozen = BASE / "run_001/frozen"
    dataset = ROOT / "results/upright_v4_pilot_preparation_20260911_123511/dataset"
    output = BASE / "analysis"
    assert not output.exists(), "No overwrite"
    bundle = pilot.load_bundle(frozen)
    anchor = common.sha256(frozen / "pilot_bundle.json")
    inputs = pilot.load_inputs(dataset)
    funcs, runtimes = pilot.model_scorers(bundle, frozen, "auto", 1)
    rows = []
    input_rows = []
    for split in ("train", "validation"):
        frame = inputs["metadata"][split].copy()
        ac = inputs["ac"][split]
        # Float32 AC is retained; Float64 sums avoid an additional accumulator error.
        vector = np.sqrt(np.sum(np.mean(ac.astype(np.float64) ** 2, axis=1), axis=1)) * 1000
        for i, row in enumerate(frame.to_dict("records")):
            input_rows.append({**row, "vector_ac_rms_mg": float(vector[i])})
        rows.extend(pilot.dispatch_prepared(ac, frame.to_dict("records"), bundle, funcs))
    predictions = pd.DataFrame(rows)
    assert predictions["decision"].ne("INVALID").all()
    original = pd.read_csv(BASE / "run_001/validation_diagnostics.csv", float_precision="round_trip")
    repeated = pd.read_csv(BASE / "replay_001/development_validation_replay.csv", float_precision="round_trip")
    current = predictions.loc[predictions["split"] == "validation"].reset_index(drop=True)
    pd.testing.assert_frame_equal(original, repeated, check_exact=True)
    pd.testing.assert_frame_equal(original, current, check_exact=True)
    inputs_frame = pd.DataFrame(input_rows)
    summaries = []
    for source in inputs["manifest"]["sources"]:
        recording = source["recording_id"]
        values = inputs_frame.loc[inputs_frame["recording_id"] == recording]
        summary = {"recording_id": recording, "original_state": source["state"], "split": source["split"],
                   "vector_ac_rms_mg": stats(values["vector_ac_rms_mg"]), "methods": {}}
        for method in pilot.METHODS:
            scores = predictions.loc[(predictions["recording_id"] == recording) & (predictions["method"] == method)]
            summary["methods"][method] = {**stats(scores["score"]),
                "threshold": bundle["thresholds"][method]["value"],
                "threshold_exceedances": int(scores["prediction"].sum()),
                "invalid_decisions": int(scores["decision"].eq("INVALID").sum())}
        summaries.append(summary)
    pilot.load_bundle(frozen)
    assert anchor == common.sha256(frozen / "pilot_bundle.json")
    output.mkdir()
    common.write_rows(output / "all_normal_window_scores.csv", rows)
    common.write_rows(output / "normal_input_window_rms.csv", input_rows)
    common.write_json(output / "diagnostics.json", {
        "evidence_scope": "training_and_calibration_diagnostics_not_independent_evaluation",
        "bundle_sha256": anchor, "models_or_scaler_fitted": False, "thresholds_adjusted": False,
        "exact_validation_replay_rows": len(original), "runtimes": runtimes, "recordings": summaries,
        "recording_replicates": {"train": 2, "validation": 1},
        "windows_are_not_independent_replicates": True,
        "script_sha256": common.sha256(Path(__file__))})
    history = pd.read_csv(BASE / "run_001/training_stage/results/training_history.csv")
    colors = {"normal_before": "#0072B2", "normal_after": "#009E73", "normal_followup": "#D55E00"}
    names = {"normal_before": "Normal davor · Training", "normal_after": "Normal danach · Training",
             "normal_followup": "Zusatzlauf · Validierung"}
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    axes[0, 0].plot(history["epoch"], history["loss"], label="Training", color="#0072B2")
    axes[0, 0].plot(history["epoch"], history["val_loss"], label="Validierung", color="#D55E00")
    axes[0, 0].set(title="Autoencoder: 100 Epochen, beste Epoche 100", xlabel="Epoche", ylabel="Rekonstruktions-MSE")
    axes[0, 0].legend()
    for ax, method, label in zip([axes[0, 1], axes[1, 0], axes[1, 1]], pilot.METHODS,
                                 ["RMS-Score", "Isolation-Forest-Score", "TFLite-AE: Rekonstruktions-MSE"]):
        for state in colors:
            selected = predictions.loc[(predictions["original_state"] == state) & (predictions["method"] == method)]
            x = (selected["start_since_command_s"] + selected["last_since_command_s"]) / 2
            ax.plot(x, selected["score"], lw=.65, alpha=.8, color=colors[state], label=names[state])
        ax.axhline(bundle["thresholds"][method]["value"], color="black", ls="--", lw=1, label="Eingefrorene P99-Schwelle")
        ax.set(title=label, xlabel="Zeit seit Stellbefehl [s]", ylabel="Dimensionsloser Score", xlim=(180, 300))
    for ax in axes.flat:
        ax.grid(alpha=.2)
    axes[0, 1].legend(fontsize=8, loc="lower right")
    fig.suptitle("Erster v4-Trainingspilot · ausschließlich normale Entwicklungsdaten\n128 XYZ/Fenster · keine unabhängige Erkennungsbewertung", fontsize=13)
    fig.savefig(output / "training_and_normal_scores.png", dpi=170)
    fig.savefig(output / "training_and_normal_scores.pdf")
    plt.close(fig)
    print(json.dumps({"recordings": summaries, "exact_validation_replay_rows": len(original)}, indent=2))


if __name__ == "__main__":
    main()
