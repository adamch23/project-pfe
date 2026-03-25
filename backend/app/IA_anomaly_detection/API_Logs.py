# ================================================================
# DETECTION D'ANOMALIES API LOGS — PIPELINE CRISP-DM v4
# ================================================================
# Fichier : E:\backend\app\IA_anomaly_detection\API_Logs.py
# CSV attendus dans le meme dossier :
#   - APILogs.csv       (train)
#   - Testlogs.csv      (test)
# Sorties dans le sous-dossier API_info/
# ================================================================

import sys
import os
import io
import traceback
import warnings

# ================================================================
# STDOUT — setup robuste (Windows + subprocess capture_output)
# ================================================================
# Sur Windows avec capture_output=True, sys.stdout.buffer peut être
# un BufferedWriter sans reconfigure(). On essaie d'abord reconfigure,
# sinon on wrappe manuellement, sinon on laisse tel quel.
def _setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        return
    except Exception:
        pass
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
        return
    except Exception:
        pass
    # Dernier recours : on laisse sys.stdout intact

_setup_stdout()

def _log(msg=""):
    """Print avec flush immédiat — évite les buffers perdus en cas d'erreur."""
    print(msg, flush=True)


# ================================================================
# WRAPPER GLOBAL — toute exception remonte dans stderr/stdout
# ================================================================
import warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    from datetime import datetime, timezone

    from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
    from sklearn.ensemble import IsolationForest
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.decomposition import PCA

    import tensorflow as tf
    from tensorflow.keras.models import Model
    from tensorflow.keras.layers import (Input, Dense, LSTM, RepeatVector,
                                          TimeDistributed, Dropout)
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.optimizers import Adam

    from pymongo import MongoClient, UpdateOne

    tf.random.set_seed(42)
    np.random.seed(42)

    _log("  OK imports")

except Exception as _import_err:
    print(f"ERREUR IMPORT : {_import_err}", flush=True)
    traceback.print_exc()
    sys.exit(1)


# ================================================================
# SECTION 0 — CONFIGURATION GLOBALE
# ================================================================
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "API_info")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRAIN_PATH  = os.path.join(BASE_DIR, "APILogs.csv")
TEST_PATH   = os.path.join(BASE_DIR, "Testlogs.csv")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "Detected_API_Anomalies.csv")
ANOM_PATH   = os.path.join(OUTPUT_DIR, "Detected_API_Anomalies_anomalies_only.csv")

PLOT_DISTRIBUTIONS = os.path.join(OUTPUT_DIR, "plot_api_distributions.png")
PLOT_CONVERGENCE   = os.path.join(OUTPUT_DIR, "plot_api_convergence.png")
PLOT_PCA           = os.path.join(OUTPUT_DIR, "plot_api_pca.png")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "API_db")
MONGO_COL = "detected_api_anomalies"

CATEGORICAL_COLS_EXPECTED = [
    "api_name", "http_method", "client_type",
    "error_type", "authentication_type"
]
NUMERIC_FEATURES_EXPECTED = [
    "request_size_bytes", "response_size_bytes", "response_time_ms",
    "http_status_code", "requests_per_minute_user", "requests_per_minute_ip",
    "concurrent_requests", "cpu_usage_server_pct", "memory_usage_server_pct",
    "db_query_time_ms", "rate_limit_triggered", "retry_count",
    "hour", "day_of_week", "is_weekend", "is_night"
]

IF_CONTAMINATION = "auto"
N_SIGMA_AE       = 1.5
N_SIGMA_LSTM     = 1.5
VOTE_THRESHOLD   = 1
LSTM_WINDOW      = 5
LSTM_SAMPLE      = 8_000
RANDOM_STATE     = 42


# ================================================================
# UTILITAIRES
# ================================================================
def safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (f != f) else f
    except Exception:
        return default

def safe_int(v, default=0):
    try: return int(safe_float(v, default))
    except Exception: return default

def row_get(row, col, default=0):
    try:
        d = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        v = d.get(col, default)
        if v is None: return default
        if isinstance(v, float) and v != v: return default
        return v
    except Exception:
        return default


# ================================================================
# SCRIPT PRINCIPAL — encapsulé dans try/except global
# ================================================================
try:

    # ============================================================
    # PHASE 1 — BUSINESS UNDERSTANDING
    # ============================================================
    _log("=" * 65)
    _log("PHASE 1 — BUSINESS UNDERSTANDING")
    _log("=" * 65)
    _log(f"  Objectif : Detection anomalies API Logs")
    _log(f"  MongoDB  : {MONGO_URI} / {MONGO_DB} / {MONGO_COL}")
    _log(f"  Dossier  : {OUTPUT_DIR}")


    # ============================================================
    # PHASE 2 — DATA UNDERSTANDING
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 2 — DATA UNDERSTANDING")
    _log("=" * 65)

    df_train    = pd.read_csv(TRAIN_PATH)
    df_test_raw = pd.read_csv(TEST_PATH)

    # Normalisation colonnes : lowercase + strip
    df_train.columns    = df_train.columns.str.lower().str.strip()
    df_test_raw.columns = df_test_raw.columns.str.lower().str.strip()

    _log(f"  [TRAIN] {df_train.shape}  colonnes: {list(df_train.columns)}")
    _log(f"  [TEST]  {df_test_raw.shape}  colonnes: {list(df_test_raw.columns)}")

    # Copie ML du test (sera encodée) — test_raw reste intact
    df_test = df_test_raw.copy()

    # Feature engineering temporel
    _ts_col = next((c for c in ["timestamp","time","date","datetime"]
                    if c in df_train.columns), None)
    _log(f"  Colonne timestamp detectee : {_ts_col}")

    for df in [df_train, df_test, df_test_raw]:
        if _ts_col and _ts_col in df.columns:
            df[_ts_col]     = pd.to_datetime(df[_ts_col], errors="coerce")
            df["hour"]        = df[_ts_col].dt.hour.fillna(0).astype(int)
            df["day_of_week"] = df[_ts_col].dt.dayofweek.fillna(0).astype(int)
            df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
            df["is_night"]    = ((df["hour"] < 6) | (df["hour"] > 22)).astype(int)
        else:
            for c in ["hour", "day_of_week", "is_weekend", "is_night"]:
                if c not in df.columns:
                    df[c] = 0

    CATEGORICAL_COLS = [c for c in CATEGORICAL_COLS_EXPECTED if c in df_train.columns]
    NUMERIC_FEATURES = [c for c in NUMERIC_FEATURES_EXPECTED if c in df_train.columns]
    FEATURES         = NUMERIC_FEATURES + CATEGORICAL_COLS

    _log(f"  Categories ({len(CATEGORICAL_COLS)}): {CATEGORICAL_COLS}")
    _log(f"  Numeriques ({len(NUMERIC_FEATURES)}): {NUMERIC_FEATURES}")

    if not NUMERIC_FEATURES:
        raise ValueError(
            "Aucune feature numerique disponible. "
            f"Colonnes attendues: {NUMERIC_FEATURES_EXPECTED}. "
            f"Colonnes presentes: {list(df_train.columns)}"
        )

    # Distributions
    n_plots = min(12, len(NUMERIC_FEATURES))
    fig, axes = plt.subplots(3, 4, figsize=(18, 10))
    for ax, feat in zip(axes.flatten(), NUMERIC_FEATURES[:n_plots]):
        v = df_train[feat].dropna().astype(float)   # FIX: bool → float avant quantile
        if len(v) > 0:
            lo, hi = v.quantile(0.01), v.quantile(0.99)
            v.clip(lower=lo, upper=hi).plot(
                kind="hist", bins=40, ax=ax, color="#0077b6", edgecolor="white")
        ax.set_title(feat, fontsize=9); ax.set_xlabel("")
    for ax in axes.flatten()[n_plots:]:
        ax.set_visible(False)
    plt.suptitle("Phase 2 - Distributions API Logs (TRAIN)", fontsize=13)
    plt.tight_layout()
    fig.savefig(PLOT_DISTRIBUTIONS, dpi=100); plt.close(fig)
    _log(f"  OK {PLOT_DISTRIBUTIONS}")


    # ============================================================
    # PHASE 3 — DATA PREPARATION
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 3 — DATA PREPARATION")
    _log("=" * 65)

    def prepare_data(df_tr_in, df_te_in, features, cat_cols):
        df_tr = df_tr_in.copy()
        df_te = df_te_in.copy()
        les = {}
        for col in cat_cols:
            if col not in df_tr.columns:
                _log(f"  WARN col absente: {col}")
                continue
            le = LabelEncoder()
            df_tr[col] = df_tr[col].fillna("NA").astype(str)
            df_te[col] = df_te[col].fillna("NA").astype(str)
            le.fit(df_tr[col])
            unk = set(df_te[col]) - set(le.classes_)
            if unk:
                le.classes_ = np.append(le.classes_, sorted(list(unk)))
            df_tr[col] = le.transform(df_tr[col])
            df_te[col] = le.transform(df_te[col])
            les[col] = le

        avail    = [f for f in features if f in df_tr.columns]
        X_tr_raw = df_tr[avail].fillna(0).values.astype(np.float32)
        X_te_raw = df_te[avail].fillna(0).values.astype(np.float32)

        sc_std   = StandardScaler()
        X_tr_std = sc_std.fit_transform(X_tr_raw)
        X_te_std = sc_std.transform(X_te_raw)

        sc_mm   = MinMaxScaler()
        X_tr_mm = sc_mm.fit_transform(X_tr_raw)
        X_te_mm = sc_mm.transform(X_te_raw)

        _log(f"  OK {len(avail)} features | Train{X_tr_std.shape} | Test{X_te_std.shape}")
        return X_tr_std, X_te_std, X_tr_mm, X_te_mm, avail, les, sc_std, sc_mm

    (X_train_std, X_test_std, X_train_mm, X_test_mm,
     avail_features, label_encoders, scaler_std, scaler_mm) = prepare_data(
        df_train, df_test, FEATURES, CATEGORICAL_COLS)

    n_feat = X_train_std.shape[1]

    # Valeur "sans erreur" de error_type
    _err_col          = "error_type"
    _none_err_str     = "NONE"
    _none_err_encoded = -1

    if _err_col in label_encoders:
        _le_err = label_encoders[_err_col]
        for _cand in ["NONE","None","none","NO_ERROR","OK","ok","NA","0",""]:
            if _cand in _le_err.classes_:
                _none_err_str     = _cand
                _none_err_encoded = int(_le_err.transform([_cand])[0])
                _log(f"  OK error_type neutre : '{_cand}' => {_none_err_encoded}")
                break
        else:
            _mc = df_train[_err_col].fillna("NA").astype(str).mode()[0]
            _none_err_str = _mc
            if _mc in _le_err.classes_:
                _none_err_encoded = int(_le_err.transform([_mc])[0])
            _log(f"  WARN error_type neutre (mode) : '{_mc}' => {_none_err_encoded}")
    else:
        _log(f"  WARN : '{_err_col}' absent des label_encoders")


    # ============================================================
    # PHASE 4 — MODELING
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 4 — MODELING")
    _log("=" * 65)

    # 4.A Isolation Forest
    _log("\n  [4.A] Isolation Forest")
    iso = IsolationForest(n_estimators=400, contamination=IF_CONTAMINATION,
                          max_features=0.8, random_state=RANDOM_STATE, n_jobs=-1)
    iso.fit(X_train_std)
    if_raw     = -iso.decision_function(X_test_std)
    if_anomaly = (iso.predict(X_test_std) == -1).astype(int)
    if_scores  = (if_raw - if_raw.min()) / (if_raw.max() - if_raw.min() + 1e-9)
    _log(f"     Anomalies : {if_anomaly.sum():,} ({if_anomaly.mean()*100:.1f}%)")

    # 4.B Autoencoder Dense
    _log("\n  [4.B] Autoencoder Dense")
    def build_ae(n):
        inp = Input(shape=(n,))
        x   = Dense(128, activation="relu")(inp)
        x   = Dropout(0.1)(x)
        x   = Dense(32,  activation="relu")(x)
        x   = Dense(128, activation="relu")(x)
        out = Dense(n,   activation="linear")(x)
        m   = Model(inp, out, name="API_AE")
        m.compile(optimizer=Adam(2e-3), loss="mse")
        return m

    ae      = build_ae(n_feat)
    ae_hist = ae.fit(X_train_std, X_train_std, epochs=60, batch_size=512,
                     validation_split=0.1,
                     callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
                     verbose=0)
    _log(f"     Epochs : {len(ae_hist.history['loss'])}")

    ae_mse_tr  = np.mean((X_train_std - ae.predict(X_train_std, verbose=0))**2, axis=1)
    ae_thr     = ae_mse_tr.mean() + N_SIGMA_AE * ae_mse_tr.std()
    ae_mse_te  = np.mean((X_test_std  - ae.predict(X_test_std,  verbose=0))**2, axis=1)
    ae_anomaly = (ae_mse_te > ae_thr).astype(int)
    ae_scores  = (ae_mse_te - ae_mse_te.min()) / (ae_mse_te.max() - ae_mse_te.min() + 1e-9)
    _log(f"     Seuil : {ae_thr:.6f} | Anomalies : {ae_anomaly.sum():,}")

    # 4.C LSTM Autoencoder
    _log("\n  [4.C] LSTM Autoencoder")
    def make_sequences(X, w):
        n = len(X)
        shape   = (n - w + 1, w, X.shape[1])
        strides = (X.strides[0], X.strides[0], X.strides[1])
        return np.lib.stride_tricks.as_strided(X, shape=shape, strides=strides).copy()

    sample_size = min(LSTM_SAMPLE, len(X_train_mm) - LSTM_WINDOW)
    idx_s    = np.random.choice(len(X_train_mm) - LSTM_WINDOW, size=sample_size, replace=False)
    X_tr_seq = make_sequences(X_train_mm, LSTM_WINDOW)[idx_s]
    X_te_seq = make_sequences(X_test_mm,  LSTM_WINDOW)

    def build_lstm_ae(w, n):
        inp = Input(shape=(w, n))
        x   = LSTM(64, activation="tanh")(inp)
        x   = RepeatVector(w)(x)
        x   = LSTM(64, activation="tanh", return_sequences=True)(x)
        out = TimeDistributed(Dense(n))(x)
        m   = Model(inp, out, name="API_LSTM_AE")
        m.compile(optimizer=Adam(2e-3), loss="mse")
        return m

    lstm_ae   = build_lstm_ae(LSTM_WINDOW, n_feat)
    lstm_hist = lstm_ae.fit(X_tr_seq, X_tr_seq, epochs=40, batch_size=256,
                            validation_split=0.1,
                            callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
                            verbose=0)
    _log(f"     Epochs : {len(lstm_hist.history['loss'])}")

    lstm_mse_tr  = np.mean((X_tr_seq - lstm_ae.predict(X_tr_seq, verbose=0))**2, axis=(1,2))
    lstm_thr     = lstm_mse_tr.mean() + N_SIGMA_LSTM * lstm_mse_tr.std()
    lstm_mse_te  = np.mean((X_te_seq - lstm_ae.predict(X_te_seq, verbose=0))**2, axis=(1,2))
    lstm_mse_pad = np.concatenate([np.full(LSTM_WINDOW-1, np.median(lstm_mse_te)), lstm_mse_te])
    lstm_anomaly = (lstm_mse_pad > lstm_thr).astype(int)
    lstm_scores  = ((lstm_mse_pad - lstm_mse_pad.min())
                    / (lstm_mse_pad.max() - lstm_mse_pad.min() + 1e-9))
    _log(f"     Seuil : {lstm_thr:.6f} | Anomalies : {lstm_anomaly.sum():,}")

    # 4.D Vote
    _log("\n  [4.D] Vote d'ensemble")
    votes            = if_anomaly + ae_anomaly + lstm_anomaly
    ensemble_anomaly = (votes >= VOTE_THRESHOLD).astype(int)
    composite_score  = (if_scores + ae_scores + lstm_scores) / 3.0
    _log(f"     3/3={int((votes==3).sum())} | 2/3={int((votes==2).sum())} | 1/3={int((votes==1).sum())}")
    _log(f"     Retenues : {int(ensemble_anomaly.sum())} ({ensemble_anomaly.mean()*100:.1f}%)")

    # 4.E Classification
    _log("\n  [4.E] Classification du type d'anomalie")
    anomaly_idx = np.where(ensemble_anomaly == 1)[0]

    if len(anomaly_idx) == 0:
        _log("  WARN : aucune anomalie")
        anomaly_type_array = np.array([], dtype=str)
    else:
        df_anom_raw = df_test_raw.iloc[anomaly_idx].reset_index(drop=True)

        def classify_api_by_rules(row):
            r     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
            err   = str(r.get(_err_col, _none_err_str) or _none_err_str).strip().upper()
            stat  = safe_int(row_get(r, "http_status_code", 200))
            resp  = safe_float(row_get(r, "response_time_ms", 0))
            db_ms = safe_float(row_get(r, "db_query_time_ms", 0))
            rl    = safe_float(row_get(r, "rate_limit_triggered", 0))
            rpu   = safe_float(row_get(r, "requests_per_minute_user", 0))
            rpi   = safe_float(row_get(r, "requests_per_minute_ip", 0))
            conc  = safe_float(row_get(r, "concurrent_requests", 0))
            retry = safe_float(row_get(r, "retry_count", 0))
            night = safe_int(row_get(r, "is_night", 0))

            if "TIMEOUT" in err:                        return "Timeout"
            if "BACKEND" in err or stat >= 500:         return "Erreur backend"
            if "RATE" in err or "LIMIT" in err or rl==1:
                return "Abuse API" if (rpu > 200 or rpi > 500) \
                       else "Mauvaise configuration rate limit"
            if conc > 1500:                             return "Explosion trafic"
            if retry >= 5 and stat >= 400:              return "Endpoint defaillant"
            if resp > 2000 or db_ms > 1200:             return "Probleme performance"
            if stat in [401, 403] and rpu > 100:        return "Tentative acces non autorise"
            if night == 1 and rpu > 150:                return "Activite nocturne suspecte"
            return "Comportement anormal"

        rule_labels    = df_anom_raw.apply(classify_api_by_rules, axis=1).values
        ambiguous_mask = (rule_labels == "Comportement anormal")
        n_ambiguous    = int(ambiguous_mask.sum())
        _log(f"     Regles : {int((~ambiguous_mask).sum())} | KMeans : {n_ambiguous}")

        if n_ambiguous >= 4:
            _dc = [c for c in ["response_time_ms","db_query_time_ms",
                                "cpu_usage_server_pct","memory_usage_server_pct",
                                "requests_per_minute_ip","concurrent_requests","retry_count"]
                   if c in df_anom_raw.columns]
            X_a    = df_anom_raw[ambiguous_mask][_dc].fillna(0).values.astype(np.float32)
            sc_d   = StandardScaler()
            X_a_sc = sc_d.fit_transform(X_a)
            bk, bs = 2, -1
            for k in range(2, min(6, n_ambiguous)):
                lt = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit_predict(X_a_sc)
                if len(set(lt)) > 1:
                    s = silhouette_score(X_a_sc, lt)
                    if s > bs: bs, bk = s, k
            km  = KMeans(n_clusters=bk, random_state=RANDOM_STATE, n_init=15)
            cl  = km.fit_predict(X_a_sc)
            cen = pd.DataFrame(sc_d.inverse_transform(km.cluster_centers_), columns=_dc)

            def _ambig_label(c):
                cd = c.to_dict() if hasattr(c,"to_dict") else dict(c)
                if safe_float(cd.get("requests_per_minute_ip",0)) > 500: return "Abuse API"
                if safe_float(cd.get("concurrent_requests",0)) > 1500:   return "Explosion trafic"
                if safe_float(cd.get("response_time_ms",0)) > 2000:      return "Probleme performance"
                if safe_float(cd.get("cpu_usage_server_pct",0)) > 90:    return "Erreur backend"
                if safe_float(cd.get("retry_count",0)) >= 5:             return "Endpoint defaillant"
                return "Comportement anormal"

            km_map = {i: _ambig_label(cen.iloc[i]) for i in range(bk)}
            rule_labels[ambiguous_mask] = np.array([km_map[c] for c in cl])

        anomaly_type_array = rule_labels
        for t, c in pd.Series(anomaly_type_array).value_counts().items():
            _log(f"       {t:<40}: {c:>5}  ({c/len(anomaly_idx)*100:.1f}%)")

    # 4.F Risk score
    def compute_api_risk(row):
        r     = row.to_dict() if hasattr(row,"to_dict") else dict(row)
        stat  = safe_int(row_get(r,"http_status_code",200))
        resp  = safe_float(row_get(r,"response_time_ms",0))
        rpi   = safe_float(row_get(r,"requests_per_minute_ip",0))
        cpu   = safe_float(row_get(r,"cpu_usage_server_pct",0))
        mem   = safe_float(row_get(r,"memory_usage_server_pct",0))
        retry = safe_float(row_get(r,"retry_count",0))
        night = safe_int(row_get(r,"is_night",0))
        rpu   = safe_float(row_get(r,"requests_per_minute_user",0))
        risk  = 0
        if stat >= 500:               risk += 4
        if stat == 429:               risk += 3
        if resp > 3000:               risk += 3
        elif resp > 2000:             risk += 2
        if rpi > 1000:                risk += 3
        elif rpi > 500:               risk += 2
        if cpu > 95:                  risk += 3
        elif cpu > 85:                risk += 2
        if mem > 90:                  risk += 2
        if retry >= 5:                risk += 2
        if night == 1 and rpu > 150:  risk += 2
        return min(risk, 10)


    # ============================================================
    # PHASE 5 — EVALUATION + GRAPHIQUES
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 5 — EVALUATION")
    _log("=" * 65)

    df_result = df_test_raw.copy()
    df_result["IF_anomaly"]      = if_anomaly
    df_result["AE_anomaly"]      = ae_anomaly
    df_result["LSTM_anomaly"]    = lstm_anomaly
    df_result["ensemble_votes"]  = votes
    df_result["is_anomaly"]      = ensemble_anomaly
    df_result["composite_score"] = composite_score
    df_result["IF_score"]        = if_scores
    df_result["AE_score"]        = ae_scores
    df_result["LSTM_score"]      = lstm_scores
    df_result["Anomaly_type"]    = "Normal"
    df_result["Risk"]            = 0

    if len(anomaly_idx) > 0:
        df_result.loc[anomaly_idx, "Anomaly_type"] = anomaly_type_array
        df_result.loc[anomaly_idx, "Risk"] = (
            df_result.loc[anomaly_idx].apply(compute_api_risk, axis=1)
        )

    anomalies     = df_result[df_result["is_anomaly"] == 1].copy()
    total, n_anom = len(df_result), len(anomalies)
    rate          = n_anom / total * 100
    crit          = int((anomalies["Risk"] >= 8).sum())

    # Convergence
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    for ax, hist, title, c1, c2 in [
        (axes[0], ae_hist,   "Autoencoder API", "#0077b6", "orange"),
        (axes[1], lstm_hist, "LSTM AE API",     "#023e8a", "red")
    ]:
        ax.plot(hist.history["loss"],     label="Train", color=c1, linewidth=2)
        ax.plot(hist.history["val_loss"], label="Val",   color=c2, linewidth=2)
        ax.set_title(f"{title} - MSE"); ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout(); fig.savefig(PLOT_CONVERGENCE, dpi=100); plt.close(fig)

    # PCA 2D
    if n_anom > 5:
        pca   = PCA(n_components=2, random_state=RANDOM_STATE)
        X_pca = pca.fit_transform(X_test_std)
        fig2, ax2 = plt.subplots(figsize=(11, 7))
        mn = df_result["is_anomaly"] == 0
        ax2.scatter(X_pca[mn,0], X_pca[mn,1], c="lightgrey", s=4, alpha=0.3, label="Normal")
        pal = sns.color_palette("tab10", anomalies["Anomaly_type"].nunique())
        for i, atype in enumerate(anomalies["Anomaly_type"].unique()):
            ix = np.where((df_result["is_anomaly"]==1) & (df_result["Anomaly_type"]==atype))[0]
            ax2.scatter(X_pca[ix,0], X_pca[ix,1], c=[pal[i]], s=25, alpha=0.85, label=atype)
        ax2.set_title(f"PCA 2D API - PC1={pca.explained_variance_ratio_[0]*100:.1f}%"
                      f" PC2={pca.explained_variance_ratio_[1]*100:.1f}%")
        ax2.legend(fontsize=9); plt.tight_layout()
        fig2.savefig(PLOT_PCA, dpi=100); plt.close(fig2)

    _log(f"  OK {PLOT_CONVERGENCE}")
    _log(f"  OK {PLOT_PCA}")


    # ============================================================
    # PHASE 6 — EXPORT + MONGODB
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 6 — EXPORT")
    _log("=" * 65)

    exp_cols = list(dict.fromkeys(
        c for c in (list(df_test_raw.columns)
                    + ["is_anomaly","Anomaly_type","Risk","composite_score",
                       "IF_score","AE_score","LSTM_score",
                       "ensemble_votes","IF_anomaly","AE_anomaly","LSTM_anomaly"])
        if c in df_result.columns
    ))

    df_result[exp_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    anomalies[exp_cols].sort_values(["Risk","composite_score"], ascending=False
                                    ).to_csv(ANOM_PATH, index=False, encoding="utf-8-sig")
    _log(f"  OK {OUTPUT_PATH}")
    _log(f"  OK {ANOM_PATH}")

    # MongoDB
    def _to_native(v):
        if isinstance(v, (np.integer,)):  return int(v)
        if isinstance(v, (np.floating,)): return None if v!=v else float(v)
        if isinstance(v, (np.bool_,)):    return bool(v)
        return v

    run_ts  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _eid_c  = "event_id" if "event_id" in df_test_raw.columns else None

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
        client.server_info()
        col = client[MONGO_DB][MONGO_COL]
        df_c = df_result[exp_cols].copy()
        df_c.replace([float("inf"), float("-inf")], None, inplace=True)
        df_c = df_c.where(df_c.notna(), other=None)
        df_c["pipeline_run_at"] = run_ts
        docs = [{k: _to_native(v) for k,v in r.items()} for r in df_c.to_dict(orient="records")]
        if _eid_c:
            ops = [UpdateOne({_eid_c: d[_eid_c]}, {"$set": d}, upsert=True) for d in docs]
            res = col.bulk_write(ops, ordered=False)
            _log(f"  OK MongoDB upsert : {res.upserted_count}+{res.modified_count}")
        else:
            col.delete_many({"pipeline_run_at": run_ts})
            res = col.insert_many(docs, ordered=False)
            _log(f"  OK MongoDB insert : {len(res.inserted_ids)}")
        for idx in ["is_anomaly","Anomaly_type","Risk","pipeline_run_at"]:
            col.create_index(idx)
        client.close()
    except Exception as mongo_err:
        _log(f"  WARN MongoDB (non bloquant) : {mongo_err}")

    _log("\n" + "=" * 65)
    _log(f"  TERMINE — Anomalies : {n_anom:,} ({rate:.1f}%) | Critiques : {crit}")
    _log(f"  Run : {run_ts}")
    _log(f"  Fichiers : {OUTPUT_DIR}")
    _log("=" * 65)
    sys.stdout.flush()

# ================================================================
# CATCH GLOBAL — affiche traceback complète + exit(1)
# ================================================================
except Exception as _fatal:
    print("\n" + "=" * 65, flush=True)
    print("ERREUR FATALE DU PIPELINE API LOGS", flush=True)
    print("=" * 65, flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    sys.exit(1)