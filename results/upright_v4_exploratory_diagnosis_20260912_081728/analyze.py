"""Exploratory, read-only diagnosis on the unchanged 128-point model windows.

No hardware imports, training, parameter selection, or source-file mutation.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from scipy.signal import periodogram

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import pilot_method_comparison as pilot
import common_comparison as common
import independent_normal_test as independent

BUNDLE = ROOT / "results/upright_v4_training_pilot_20260911_130614/run_001/frozen"
PREP = ROOT / "results/upright_v4_pilot_preparation_20260911_123511/dataset"
CURRENT = ROOT / "results/upright_v4_frozen_airflow_test_20260912_073015"
PRIOR = ROOT / "results/upright_v4_independent_normal_20260911_133047"
AXES = ["x_g", "y_g", "z_g"]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(name, value):
    with (OUT / name).open("x") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")

def spectrum(a):
    return periodogram(a, fs=200., window="hann", detrend=False, axis=0, scaling="density")

def decomposition(raw, x, reconstruction):
    # Physical diagnostics use original Float64, without a second scaling fit.
    ac64 = raw - raw.mean(axis=0, keepdims=True)
    physical_axis_energy = np.mean(ac64 ** 2, axis=0)
    input_energy = np.mean(np.square(x), axis=0, dtype=np.float64)
    error = x - reconstruction  # Float32 subtraction/square, exactly as frozen scorer.
    mse = np.mean(np.square(error), axis=0, dtype=np.float64)
    return ac64, physical_axis_energy, input_energy, error, mse

def self_checks():
    t = np.arange(128)
    a = np.column_stack([np.sin(2*np.pi*16*t/128), 2*np.cos(2*np.pi*24*t/128), np.zeros(128)])
    raw = np.array(a + [1., 2., 3.], order="F")
    x = pilot.center_raw_window(raw)
    _, e, z, _, mse = decomposition(raw, x, np.zeros_like(x))
    assert np.allclose(e, [.5, 2., 0.], atol=1e-14)
    assert np.allclose(z, mse)
    assert np.isclose(np.sqrt(e.sum()), np.sqrt(2.5))
    f, p = spectrum(a)
    assert f[np.argmax(p[:, 0])] == 25.
    assert f[np.argmax(p[:, 1])] == 37.5
    _, _, _, _, perfect = decomposition(raw, x, x.copy())
    assert np.all(perfect == 0)
    return {"axis_energy_identity": True, "perfect_and_zero_reconstruction": True,
            "known_sinusoid_frequency_bins": True, "hardware_access": False}

def main():
    checks = self_checks()
    bundle = pilot.load_bundle(BUNDLE)
    assert sha(BUNDLE / "pilot_bundle.json") == "cec1859bfb354bafef77a619e6d2c1ffd85b50787c87595aba9a1e20a80cdae5"
    scorers, runtimes = pilot.model_scorers(bundle, BUNDLE, threads=1)
    interpreter, incoming, outgoing, backend = common.load_interpreter(BUNDLE / "autoencoder_float32.tflite", "litert", 1)
    prepared = pilot.load_inputs(PREP)
    sources = []
    for src in bundle["recordings"]:
        sources.append({**src, "group": src["split"], "name": "train_"+src["state"] if src["split"]=="train" else "validation",
                        "command": src["pwm_command_invocation_monotonic_ns"], "saved_scores": None})
    evals = [(PRIOR / f"evaluation_normal_test_0{i}", "independent_normal", f"normal_test_0{i}") for i in [1,2,3]]
    evals += [(ROOT / "results/upright_v4_frozen_airflow_test_20260911_164040/evaluation_normal_before", "independent_normal", "normal_sep11")]
    evals += [(CURRENT / ("evaluation_"+p), "current_sequence", p) for p in ["normal_before", "airflow_modified", "normal_after"]]
    for path, group, name in evals:
        s = read(path / "summary.json")
        sources.append({**s, "group": group, "name": name, "command": s["pwm_command_invocation_monotonic_ns"],
                        "saved_scores": str(path / "scores.csv")})
    rows, spectral, reconstruction_store = [], [], []
    parity = []
    for src in sources:
        print("Diagnosing", src["name"], flush=True)
        assert sha(src["csv"]) == src["csv_sha256"]
        frame = pd.read_csv(src["csv"], float_precision="round_trip")
        windows, selection = independent.build_windows(frame, src["command"])
        saved = pd.read_csv(src["saved_scores"], float_precision="round_trip") if src["saved_scores"] else None
        prep_rows = None
        if src["group"] in ["train", "validation"]:
            prep_rows = prepared["metadata"][src["split"]].query("recording_id == @src['recording_id']") if False else prepared["metadata"][src["split"]].loc[lambda d:d.recording_id==src["recording_id"]]
            assert len(prep_rows) == len(windows)
        maximum_difference = 0.
        for w in windows:
            meta=w["metadata"]; i=meta["window_index_in_recording"]
            row={"name":src["name"], "group":src["group"], "recording_id":src["recording_id"],
                 "state":"airflow_modified" if src["name"]=="airflow_modified" else "normal", **meta}
            if not meta["quality_valid"]:
                rows.append(row); continue
            if prep_rows is not None:
                old=prep_rows.iloc[i]
                assert int(old.source_start_index)==meta["source_start_index"]
                assert int(old.source_end_index_exclusive)==meta["source_end_index_exclusive"]
                assert np.array_equal(w["ac_float32"],prepared["ac"][src["split"]][int(old.split_index)])
            x=pilot.standardize_ac(w["ac_float32"],bundle["scaler"])
            scores={m:float(fn(x.copy())) for m,fn in scorers.items()}
            if saved is not None:
                old=saved.loc[saved.window_index_in_recording==i]
                assert len(old)==3
                for m,score in scores.items():
                    sr=old.loc[old.method==m].iloc[0]
                    assert int(sr.source_start_index)==meta["source_start_index"]
                    maximum_difference=max(maximum_difference,abs(score-float(sr.score)))
                    assert abs(score-float(sr.score))<=1e-12,(src["name"],m,i,score,sr.score)
                    assert int(score>bundle["thresholds"][m]["value"])==int(sr.prediction)
            interpreter.set_tensor(incoming["index"],x[np.newaxis,...]);interpreter.invoke()
            reconstruction=interpreter.get_tensor(outgoing["index"])[0]
            ac, physical, energy, error, mse=decomposition(w["raw_float64"],x,reconstruction)
            assert abs(float(mse.mean())-scores["tflite_autoencoder"])<=1e-12
            assert abs(float(np.sqrt(energy.mean()))-scores["rms"])<=1e-12
            theoretical=(physical / np.asarray(bundle["scaler"]["scale"])**2).mean()
            assert np.isclose(theoretical, scores["rms"]**2,rtol=2e-7,atol=1e-12)
            row.update(scores);row["ae_alarm"]=scores["tflite_autoencoder"]>bundle["thresholds"]["tflite_autoencoder"]["value"]
            row["physical_vector_ac_rms_mg"]=1000*float(np.sqrt(physical.sum()))
            row["host_window_rate_xyz_s"]=127e9/(meta["last_host_monotonic_ns"]-meta["start_host_monotonic_ns"])
            f, power=spectrum(ac);_, standard_power=spectrum(x.astype(np.float64));_, error_power=spectrum(error.astype(np.float64))
            for j,a in enumerate("xyz"):
                row[a+"_rms_mg"]=1000*float(np.sqrt(physical[j]))
                row[a+"_physical_energy_share"]=float(physical[j]/physical.sum())
                row[a+"_standard_energy"]=float(energy[j])
                row[a+"_standard_energy_share"]=float(energy[j]/energy.sum())
                row[a+"_ae_mse"]=float(mse[j]);row[a+"_ae_error_share"]=float(mse[j]/mse.sum())
                row[a+"_residual_energy_ratio"]=float(mse[j]/energy[j])
                row[a+"_reconstruction_gain"]=float(np.sqrt(np.mean(reconstruction[:,j].astype(float)**2)/energy[j]))
                row[a+"_input_reconstruction_corr"]=float(np.corrcoef(x[:,j],reconstruction[:,j])[0,1])
                peak=int(np.argmax(power[1:,j])+1)
                row[a+"_peak_hz_nominal"]=float(f[peak]);row[a+"_peak_hz_host_estimate"]=float(f[peak]*row["host_window_rate_xyz_s"]/200)
                for low,high in [(0,20),(20,60),(60,100)]:
                    mask=(f>=low)&((f<high) if high<100 else (f<=high))
                    row[f"{a}_power_fraction_{low}_{high}"]=float(power[mask,j].sum()/power[:,j].sum())
                    row[f"{a}_residual_power_fraction_{low}_{high}"]=float(error_power[mask,j].sum()/error_power[:,j].sum())
            row["vector_high_fraction"]=float(power[f>=60].sum()/power.sum())
            row["standard_high_fraction"]=float(standard_power[f>=60].sum()/standard_power.sum())
            rows.append(row)
            spectral.append({"name":src["name"],"ae_alarm":row["ae_alarm"],"physical_psd":power.tolist(),
                             "standard_psd":standard_power.tolist(),"residual_psd":error_power.tolist()})
            reconstruction_store.append(reconstruction)
        parity.append({"name":src["name"],"windows":selection,"training_ac_array_equal":prep_rows is not None,
                       "archived_score_comparison":saved is not None,"max_absolute_archived_score_difference":maximum_difference,
                       "source_csv_sha256":src["csv_sha256"]})
    df=pd.DataFrame(rows)
    df.to_csv(OUT/"window_diagnostics.csv",index=False,mode="x")
    np.savez_compressed(OUT/"spectra_and_reconstruction.npz",frequency_hz_nominal=f,
                        physical_psd=np.array([s["physical_psd"] for s in spectral]),
                        standard_psd=np.array([s["standard_psd"] for s in spectral]),
                        residual_psd=np.array([s["residual_psd"] for s in spectral]),
                        reconstruction=np.array(reconstruction_store))
    fields=[k for k in df.select_dtypes(include="number").columns if not k.endswith("ns") and k not in ["source_start_index","source_end_index_exclusive"]]
    summaries=[]
    for name,g in df.groupby("name",sort=False):
        stats={k:{"mean":float(g[k].mean()),"median":float(g[k].median()),"std":float(g[k].std()),
                  "min":float(g[k].min()),"max":float(g[k].max()),"p05":float(g[k].quantile(.05)),"p95":float(g[k].quantile(.95))} for k in fields}
        summaries.append({"name":name,"group":g.group.iloc[0],"windows":len(g),"valid":int(g.quality_valid.sum()),
                          "ae_alarms":int(g.ae_alarm.sum()),"statistics":stats})
    write("recording_summary.json",summaries)
    write("source_inventory.json",sources)
    write("verification.json",{"created_utc":datetime.now(timezone.utc).isoformat(),"self_checks":checks,
                              "parity_by_recording":parity,"rows":len(df),"source_recordings":len(sources),
                              "bundle_sha256":sha(BUNDLE/"pilot_bundle.json"),"analysis_sha256":sha(__file__),
                              "runtimes":runtimes,"decomposed_runtime":backend,"scaler":bundle["scaler"],
                              "thresholds":bundle["thresholds"],"hardware_access":False,"training":False})
    print("Saved",len(df),"windows from",len(sources),"recordings",flush=True)

if __name__=="__main__":main()
