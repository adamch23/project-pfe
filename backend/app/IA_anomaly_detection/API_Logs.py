# ================================================================
# DETECTION D'ANOMALIES API LOGS — PIPELINE CRISP-DM v10
# ================================================================
# Fichier : E:\backend\app\IA_anomaly_detection\API_Logs.py
# CSV attendus dans le meme dossier :
#   - APILogs.csv       (train)
#   - Testlogs.csv      (test)
# Sorties dans le sous-dossier API_info/
# Rapport global incremental dans E:\backend\app\Data_Analyst\
# =
# ================================================================

import sys
import os
import io
import traceback
import warnings

# ================================================================
# STDOUT — setup robuste
# ================================================================
def _setup_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace"); return
    except Exception:
        pass
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        ); return
    except Exception:
        pass

_setup_stdout()

def _log(msg=""):
    print(msg, flush=True)

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
    from sklearn.mixture import GaussianMixture       # ← NOUVEAU v10

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
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR       = os.path.join(BASE_DIR, "API_info")
DATA_ANALYST_DIR = os.path.join(os.path.dirname(BASE_DIR), "Data_Analyst")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_ANALYST_DIR, exist_ok=True)

TRAIN_PATH     = os.path.join(BASE_DIR, "APILogs.csv")
TEST_PATH      = os.path.join(BASE_DIR, "Testlogs.csv")
OUTPUT_PATH    = os.path.join(OUTPUT_DIR, "Detected_API_Anomalies.csv")
ANOM_PATH      = os.path.join(OUTPUT_DIR, "Detected_API_Anomalies_anomalies_only.csv")
DONE_FLAG_PATH = os.path.join(OUTPUT_DIR, ".pipeline_done")
DA_OUTPUT_PATH = os.path.join(DATA_ANALYST_DIR, "Detected_API_Anomalies.csv")

PLOT_DISTRIBUTIONS = os.path.join(OUTPUT_DIR, "plot_api_distributions.png")
PLOT_CONVERGENCE   = os.path.join(OUTPUT_DIR, "plot_api_convergence.png")
PLOT_PCA           = os.path.join(OUTPUT_DIR, "plot_api_pca.png")
PLOT_GMM_SCORES    = os.path.join(OUTPUT_DIR, "plot_api_gmm_scores.png")   # ← NOUVEAU v10

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

# ================================================================
# ★ PARAMETRES PRINCIPAUX — SEULS A MODIFIER ★
# ================================================================
#
#  TRAIN_CONTAMINATION = 0.20
#    Proportion d'anomalies ESTIMEE dans le TRAIN.
#    Utilise uniquement par l'Isolation Forest (contamination=).
#    Ne fixe PAS le seuil de detection final.
#
#  EXPECTED_TEST_RATE = 0.18   → MODE A (taux connu)
#    Detecte EXACTEMENT ce pourcentage dans le TEST.
#    A utiliser quand le taux reel est connu ou impose metier.
#
#  EXPECTED_TEST_RATE = None   → MODE B (taux inconnu)
#    GMM(2) auto-calibration : trouve le taux reel automatiquement
#    en separant les distributions normale/anomalie des SCORES TEST.
#    Fonctionne pour n'importe quel taux (5%, 18%, 22%, etc.)
#    sans connaissance prealable.
#
#  POIDS des modeles dans le score composite :
#    W_IF=1.0  W_AE=1.5  W_LSTM=1.0
#    Augmenter W_AE si anomalies = valeurs extremes isolees.
#    Augmenter W_LSTM si anomalies = sequences temporelles anormales.
#
#  GMM_N_INIT = 20
#    Nombre de restarts du GMM pour eviter les minima locaux.
#    Augmenter si Mode B donne des resultats instables.
# ================================================================
TRAIN_CONTAMINATION = 0.20   # % anomalies estimees dans le TRAIN
EXPECTED_TEST_RATE  = None   # None = auto GMM | float = taux connu (ex: 0.18)
W_IF                = 1.0
W_AE                = 1.5
W_LSTM              = 1.0
LSTM_WINDOW         = 5
LSTM_SAMPLE         = 8_000
RANDOM_STATE        = 42
GMM_N_INIT          = 20     # restarts GMM Mode B — ← NOUVEAU v10
GMM_RATE_MIN        = 0.01   # garde-fou : taux GMM minimal acceptable
GMM_RATE_MAX        = 0.50   # garde-fou : taux GMM maximal acceptable


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

def normalize_scores(arr: np.ndarray,
                     ref_min: float = None,
                     ref_max: float = None) -> np.ndarray:
    """
    Normalise arr vers [0,1].
    ref_min/ref_max : bornes de reference calculees sur le TRAIN.
    Le TEST est normalise avec les memes bornes → scores comparables.
    """
    lo = ref_min if ref_min is not None else float(arr.min())
    hi = ref_max if ref_max is not None else float(arr.max())
    rng = hi - lo
    if rng < 1e-12:
        return np.zeros(len(arr), dtype=np.float32)
    return np.clip((arr - lo) / rng, 0.0, 1.0).astype(np.float32)


# ================================================================
# ★ FONCTION GMM AUTO-CALIBRATION — NOUVEAU v10 ★
# ================================================================
def gmm_threshold(composite_test: np.ndarray,
                  n_init: int = 20,
                  rate_min: float = 0.01,
                  rate_max: float = 0.50,
                  random_state: int = 42) -> tuple:
    """
    Trouve le seuil de detection et le masque d'anomalies via un GMM(2).

    Principe :
      - Ajuste un melange de 2 gaussiennes sur les scores composites TEST.
      - La composante de plus haute moyenne = anomalies.
      - Attribue chaque point a la composante la plus probable (Bayes optimal).
      - Garde-fous : si le taux resultant est hors [rate_min, rate_max],
        retourne None pour signaler un echec (fallback declenche).

    Retourne :
      (threshold, anomaly_mask, detected_rate, gmm_object)
      ou (None, None, None, None) si echec.
    """
    try:
        scores_2d = composite_test.reshape(-1, 1).astype(np.float64)
        gmm = GaussianMixture(
            n_components=2,
            covariance_type="full",
            n_init=n_init,
            max_iter=300,
            tol=1e-4,
            random_state=random_state
        )
        gmm.fit(scores_2d)

        # Composante anomalie = celle de plus haute moyenne
        means     = gmm.means_.flatten()
        anom_comp = int(np.argmax(means))
        norm_comp = 1 - anom_comp

        # Probabilite d'appartenir a la composante anomalie
        proba_anom = gmm.predict_proba(scores_2d)[:, anom_comp]

        # Classification Bayes : P(anomalie) > P(normale) <=> proba_anom > 0.5
        anom_mask     = (proba_anom >= 0.5)
        detected_rate = float(anom_mask.sum()) / len(composite_test)

        # Garde-fou : le taux doit etre raisonnable
        if not (rate_min <= detected_rate <= rate_max):
            _log(f"     GMM hors garde-fous : {detected_rate*100:.1f}% "
                 f"(attendu {rate_min*100:.0f}%–{rate_max*100:.0f}%) → fallback")
            return None, None, None, None

        # Seuil = score minimal de la composante anomalie
        anom_scores = composite_test[anom_mask]
        threshold   = float(anom_scores.min()) if len(anom_scores) > 0 else 0.5

        _log(f"     GMM mu_normal={means[norm_comp]:.4f}  "
             f"mu_anomalie={means[anom_comp]:.4f}")
        _log(f"     GMM taux auto-detecte : {detected_rate*100:.2f}%  "
             f"| seuil Bayes : {threshold:.6f}")

        return threshold, anom_mask, detected_rate, gmm

    except Exception as e:
        _log(f"     GMM echec : {e} → fallback")
        return None, None, None, None


# ================================================================
# FONCTION INCREMENTATION DATA_ANALYST
# ================================================================
def incremental_save_to_data_analyst(df_new, da_path, id_col=None, run_ts=""):
    df_new = df_new.copy()
    df_new["pipeline_run_at"] = run_ts
    df_new["pipeline_source"] = "API_Logs"

    if not os.path.exists(da_path):
        df_new.to_csv(da_path, index=False, encoding="utf-8-sig")
        _log(f"  OK Data_Analyst cree : {da_path} ({len(df_new):,} lignes)")
        return

    df_existing = pd.read_csv(da_path, low_memory=False)

    if id_col and id_col in df_existing.columns and id_col in df_new.columns:
        existing_ids = set(df_existing[id_col].astype(str).tolist())
        def _make_unique_id(row):
            orig = str(row[id_col])
            if orig not in existing_ids:
                return orig
            v = 2
            cand = f"{orig}_v{v}"
            while cand in existing_ids:
                v += 1; cand = f"{orig}_v{v}"
            existing_ids.add(cand)
            return cand
        df_new[id_col] = df_new.apply(_make_unique_id, axis=1)
        _log(f"  OK Deduplication id sur '{id_col}'")

    all_cols    = list(dict.fromkeys(list(df_existing.columns) + list(df_new.columns)))
    df_existing = df_existing.reindex(columns=all_cols)
    df_new      = df_new.reindex(columns=all_cols)
    df_merged   = pd.concat([df_existing, df_new], ignore_index=True)
    df_merged.to_csv(da_path, index=False, encoding="utf-8-sig")
    _log(f"  OK Data_Analyst mis a jour : {da_path}")
    _log(f"     Avant={len(df_existing):,} | Nouveaux={len(df_new):,} | Total={len(df_merged):,}")


# ================================================================
# SCRIPT PRINCIPAL
# ================================================================
try:
    if os.path.exists(DONE_FLAG_PATH):
        os.remove(DONE_FLAG_PATH)

    # ============================================================
    # PHASE 1 — BUSINESS UNDERSTANDING
    # ============================================================
    _log("=" * 65)
    _log("PHASE 1 — BUSINESS UNDERSTANDING")
    _log("=" * 65)

    _mode_str = (f"MODE A : taux test connu = {EXPECTED_TEST_RATE*100:.1f}%"
                 if EXPECTED_TEST_RATE is not None
                 else f"MODE B : taux test inconnu → GMM auto-calibration")
    _log(f"  Objectif     : Detection anomalies API Logs")
    _log(f"  Mode seuil   : {_mode_str}")
    _log(f"  Train contam : {TRAIN_CONTAMINATION*100:.0f}%  |  Poids IF={W_IF} AE={W_AE} LSTM={W_LSTM}")
    _log(f"  GMM n_init   : {GMM_N_INIT}  |  garde-fous [{GMM_RATE_MIN*100:.0f}%-{GMM_RATE_MAX*100:.0f}%]")
    _log(f"  MongoDB      : {MONGO_URI} / {MONGO_DB} / {MONGO_COL}")
    _log(f"  Dossier      : {OUTPUT_DIR}")

    # ============================================================
    # PHASE 2 — DATA UNDERSTANDING
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 2 — DATA UNDERSTANDING")
    _log("=" * 65)

    df_train    = pd.read_csv(TRAIN_PATH)
    df_test_raw = pd.read_csv(TEST_PATH)
    df_train.columns    = df_train.columns.str.lower().str.strip()
    df_test_raw.columns = df_test_raw.columns.str.lower().str.strip()

    _log(f"  [TRAIN] {df_train.shape}  colonnes: {list(df_train.columns)}")
    _log(f"  [TEST]  {df_test_raw.shape}  colonnes: {list(df_test_raw.columns)}")

    df_test = df_test_raw.copy()
    n_test  = len(df_test)
    n_train = len(df_train)

    _ts_col = next((c for c in ["timestamp", "time", "date", "datetime"]
                    if c in df_train.columns), None)
    _log(f"  Timestamp : {_ts_col}")

    for df in [df_train, df_test, df_test_raw]:
        if _ts_col and _ts_col in df.columns:
            df[_ts_col]       = pd.to_datetime(df[_ts_col], errors="coerce")
            df["hour"]        = df[_ts_col].dt.hour.fillna(0).astype(int)
            df["day_of_week"] = df[_ts_col].dt.dayofweek.fillna(0).astype(int)
            df["is_weekend"]  = (df["day_of_week"] >= 5).astype(int)
            df["is_night"]    = ((df["hour"] < 6) | (df["hour"] > 22)).astype(int)
        else:
            for c in ["hour", "day_of_week", "is_weekend", "is_night"]:
                if c not in df.columns: df[c] = 0

    CATEGORICAL_COLS = [c for c in CATEGORICAL_COLS_EXPECTED if c in df_train.columns]
    NUMERIC_FEATURES = [c for c in NUMERIC_FEATURES_EXPECTED if c in df_train.columns]
    FEATURES         = NUMERIC_FEATURES + CATEGORICAL_COLS

    _log(f"  Categories ({len(CATEGORICAL_COLS)}): {CATEGORICAL_COLS}")
    _log(f"  Numeriques ({len(NUMERIC_FEATURES)}): {NUMERIC_FEATURES}")

    if not NUMERIC_FEATURES:
        raise ValueError(
            f"Aucune feature numerique disponible. "
            f"Colonnes attendues: {NUMERIC_FEATURES_EXPECTED}. "
            f"Colonnes presentes: {list(df_train.columns)}"
        )

    n_plots = min(12, len(NUMERIC_FEATURES))
    fig, axes = plt.subplots(3, 4, figsize=(18, 10))
    for ax, feat in zip(axes.flatten(), NUMERIC_FEATURES[:n_plots]):
        v = df_train[feat].dropna().astype(float)
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
        df_tr = df_tr_in.copy(); df_te = df_te_in.copy()
        les = {}
        for col in cat_cols:
            if col not in df_tr.columns:
                _log(f"  WARN col absente: {col}"); continue
            le = LabelEncoder()
            df_tr[col] = df_tr[col].fillna("NA").astype(str)
            df_te[col] = df_te[col].fillna("NA").astype(str)
            le.fit(df_tr[col])
            unk = set(df_te[col]) - set(le.classes_)
            if unk: le.classes_ = np.append(le.classes_, sorted(list(unk)))
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

    _err_col = "error_type"; _none_err_str = "NONE"; _none_err_encoded = -1
    if _err_col in label_encoders:
        _le_err = label_encoders[_err_col]
        for _cand in ["NONE","None","none","NO_ERROR","OK","ok","NA","0",""]:
            if _cand in _le_err.classes_:
                _none_err_str     = _cand
                _none_err_encoded = int(_le_err.transform([_cand])[0])
                _log(f"  OK error_type neutre : '{_cand}' => {_none_err_encoded}"); break
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

    # ── 4.A  ISOLATION FOREST ────────────────────────────────────
    _log("\n  [4.A] Isolation Forest")
    iso = IsolationForest(
        n_estimators=400, contamination=TRAIN_CONTAMINATION,
        max_features=0.8, random_state=RANDOM_STATE, n_jobs=-1
    )
    iso.fit(X_train_std)

    if_raw_train = -iso.decision_function(X_train_std)
    if_raw_test  = -iso.decision_function(X_test_std)
    if_min = float(if_raw_train.min()); if_max = float(if_raw_train.max())
    if_scores_train = normalize_scores(if_raw_train, if_min, if_max)
    if_scores_test  = normalize_scores(if_raw_test,  if_min, if_max)
    _log(f"     IF train score — mean:{if_scores_train.mean():.4f} std:{if_scores_train.std():.4f}")
    _log(f"     IF test  score — mean:{if_scores_test.mean():.4f}  std:{if_scores_test.std():.4f}")

    # ── 4.B  AUTOENCODER DENSE ───────────────────────────────────
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
    ae_hist = ae.fit(
        X_train_std, X_train_std, epochs=60, batch_size=512,
        validation_split=0.1,
        callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
        verbose=0
    )
    _log(f"     Epochs : {len(ae_hist.history['loss'])}")

    ae_mse_train = np.mean((X_train_std - ae.predict(X_train_std, verbose=0))**2, axis=1)
    ae_mse_test  = np.mean((X_test_std  - ae.predict(X_test_std,  verbose=0))**2, axis=1)
    ae_min = float(ae_mse_train.min()); ae_max = float(ae_mse_train.max())
    ae_scores_train = normalize_scores(ae_mse_train, ae_min, ae_max)
    ae_scores_test  = normalize_scores(ae_mse_test,  ae_min, ae_max)
    _log(f"     AE MSE train — mean:{ae_mse_train.mean():.6f} std:{ae_mse_train.std():.6f}")
    _log(f"     AE MSE test  — mean:{ae_mse_test.mean():.6f}  std:{ae_mse_test.std():.6f}")

    # ── 4.C  LSTM AUTOENCODER ────────────────────────────────────
    _log("\n  [4.C] LSTM Autoencoder")
    def make_sequences(X, w):
        n_seq = len(X) - w + 1
        if n_seq <= 0:
            return np.zeros((1, w, X.shape[1]), dtype=np.float32)
        seqs = np.empty((n_seq, w, X.shape[1]), dtype=np.float32)
        for i in range(n_seq): seqs[i] = X[i:i + w]
        return seqs

    sample_size     = min(LSTM_SAMPLE, max(1, n_train - LSTM_WINDOW))
    idx_s           = np.random.choice(max(1, n_train - LSTM_WINDOW),
                                       size=sample_size, replace=False)
    X_tr_seq_sample = make_sequences(X_train_mm, LSTM_WINDOW)[idx_s]
    X_tr_seq_full   = make_sequences(X_train_mm, LSTM_WINDOW)
    X_te_seq        = make_sequences(X_test_mm,  LSTM_WINDOW)

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
    lstm_hist = lstm_ae.fit(
        X_tr_seq_sample, X_tr_seq_sample, epochs=40, batch_size=256,
        validation_split=0.1,
        callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
        verbose=0
    )
    _log(f"     Epochs : {len(lstm_hist.history['loss'])}")

    lstm_mse_tr_seq = np.mean(
        (X_tr_seq_full - lstm_ae.predict(X_tr_seq_full, verbose=0))**2, axis=(1, 2))
    lstm_mse_te_seq = np.mean(
        (X_te_seq      - lstm_ae.predict(X_te_seq,      verbose=0))**2, axis=(1, 2))

    def _align(mse_seq, n_target):
        n_pad = n_target - len(mse_seq)
        if n_pad > 0:
            return np.concatenate([
                np.full(n_pad, float(np.median(mse_seq))), mse_seq])
        return mse_seq[-n_target:] if n_pad < 0 else mse_seq

    lstm_mse_train_full = _align(lstm_mse_tr_seq, n_train)
    lstm_mse_test_full  = _align(lstm_mse_te_seq, n_test)
    assert len(lstm_mse_train_full) == n_train
    assert len(lstm_mse_test_full)  == n_test

    lstm_min = float(lstm_mse_train_full.min())
    lstm_max = float(lstm_mse_train_full.max())
    lstm_scores_train = normalize_scores(lstm_mse_train_full, lstm_min, lstm_max)
    lstm_scores_test  = normalize_scores(lstm_mse_test_full,  lstm_min, lstm_max)
    _log(f"     LSTM MSE train — mean:{lstm_mse_train_full.mean():.6f} std:{lstm_mse_train_full.std():.6f}")
    _log(f"     LSTM MSE test  — mean:{lstm_mse_test_full.mean():.6f}  std:{lstm_mse_test_full.std():.6f}")

    # ── 4.D  SCORE COMPOSITE + SEUIL ADAPTATIF v10 ───────────────
    # ╔═══════════════════════════════════════════════════════════╗
    # ║  LOGIQUE DE SEUIL v10                                     ║
    # ║                                                           ║
    # ║  MODE A — EXPECTED_TEST_RATE renseigne (ex: 0.18)        ║
    # ║    Taux reel connu → top-K garantit exactement ce taux.  ║
    # ║    Independant de la distribution des scores.             ║
    # ║    Toujours exact quel que soit le covariate shift.       ║
    # ║                                                           ║
    # ║  MODE B — EXPECTED_TEST_RATE = None (v10)                ║
    # ║    GMM(2) ajuste sur composite_TEST.                      ║
    # ║    Composante haute-moyenne = anomalies.                  ║
    # ║    Frontiere de Bayes = seuil optimal.                    ║
    # ║    Adaptatif : fonctionne pour 5%, 18%, 22%...            ║
    # ║    Garde-fous [GMM_RATE_MIN, GMM_RATE_MAX].               ║
    # ║    Fallback si GMM hors-limites : percentile TRAIN.       ║
    # ╚═══════════════════════════════════════════════════════════╝
    _log("\n  [4.D] Score composite + seuil adaptatif v10")
    W_TOTAL = W_IF + W_AE + W_LSTM

    composite_train = (W_IF * if_scores_train +
                       W_AE * ae_scores_train +
                       W_LSTM * lstm_scores_train) / W_TOTAL

    composite_test  = (W_IF * if_scores_test +
                       W_AE * ae_scores_test +
                       W_LSTM * lstm_scores_test) / W_TOTAL

    _log(f"     Composite TEST  — mean:{composite_test.mean():.4f} "
         f"std:{composite_test.std():.4f} "
         f"p80:{np.percentile(composite_test,80):.4f} "
         f"p90:{np.percentile(composite_test,90):.4f}")
    _log(f"     Composite TRAIN — mean:{composite_train.mean():.4f} "
         f"std:{composite_train.std():.4f} "
         f"p80:{np.percentile(composite_train,80):.4f} "
         f"p90:{np.percentile(composite_train,90):.4f}")

    if EXPECTED_TEST_RATE is not None:
        # ── MODE A : taux connu → top-K exact ────────────────────
        _log(f"\n     MODE A : taux connu = {EXPECTED_TEST_RATE*100:.1f}%")
        n_target = int(round(n_test * EXPECTED_TEST_RATE))

        # top-K direct : plus robuste que percentile + correction
        top_idx          = np.argsort(composite_test)[-n_target:]
        ensemble_anomaly = np.zeros(n_test, dtype=int)
        ensemble_anomaly[top_idx] = 1

        composite_threshold = float(composite_test[top_idx].min())
        threshold_source    = (f"MODE A top-{n_target} "
                               f"(taux connu={EXPECTED_TEST_RATE*100:.1f}%)")

    else:
        # ── MODE B : taux inconnu → GMM auto-calibration ─────────
        _log(f"\n     MODE B : taux inconnu → GMM auto-calibration")
        gmm_thr, gmm_mask, gmm_rate, gmm_obj = gmm_threshold(
            composite_test,
            n_init=GMM_N_INIT,
            rate_min=GMM_RATE_MIN,
            rate_max=GMM_RATE_MAX,
            random_state=RANDOM_STATE
        )

        if gmm_mask is not None:
            # ── Mode B success : GMM dans les garde-fous ─────────
            ensemble_anomaly    = gmm_mask.astype(int)
            composite_threshold = gmm_thr
            n_target            = int(ensemble_anomaly.sum())
            threshold_source    = (f"MODE B GMM auto "
                                   f"(taux auto={gmm_rate*100:.2f}%)")

            # Graphique GMM
            try:
                fig_g, ax_g = plt.subplots(figsize=(11, 5))
                ax_g.hist(composite_test[~gmm_mask], bins=80, alpha=0.6,
                          color="#0077b6", label="Normal (GMM)", density=True)
                ax_g.hist(composite_test[gmm_mask],  bins=80, alpha=0.6,
                          color="#e63946", label="Anomalie (GMM)", density=True)
                ax_g.axvline(composite_threshold, color="black", linewidth=2,
                             linestyle="--", label=f"Seuil Bayes = {composite_threshold:.4f}")
                ax_g.set_title(
                    f"MODE B v10 — GMM(2) auto-calibration\n"
                    f"Taux auto-detecte : {gmm_rate*100:.2f}%  |  "
                    f"Seuil : {composite_threshold:.6f}",
                    fontsize=12)
                ax_g.set_xlabel("Score composite"); ax_g.set_ylabel("Densite")
                ax_g.legend(); plt.tight_layout()
                fig_g.savefig(PLOT_GMM_SCORES, dpi=100); plt.close(fig_g)
                _log(f"     OK {PLOT_GMM_SCORES}")
            except Exception as _eg:
                _log(f"     WARN graphique GMM : {_eg}")

        else:
            # ── Mode B fallback : percentile TRAIN ───────────────
            _log(f"     MODE B fallback → percentile TRAIN "
                 f"(contamination={TRAIN_CONTAMINATION*100:.0f}%)")
            pct_level           = (1.0 - TRAIN_CONTAMINATION) * 100.0
            composite_threshold = float(np.percentile(composite_train, pct_level))

            # top-K depuis seuil TRAIN (evite les ex-aequo)
            n_target = int(round(n_test * TRAIN_CONTAMINATION))
            top_idx  = np.argsort(composite_test)[-n_target:]
            ensemble_anomaly = np.zeros(n_test, dtype=int)
            ensemble_anomaly[top_idx] = 1
            composite_threshold = float(composite_test[top_idx].min())
            threshold_source    = (f"MODE B fallback TRAIN P{pct_level:.1f} "
                                   f"(contam={TRAIN_CONTAMINATION*100:.1f}%)")

    _log(f"\n     Seuil composite : {composite_threshold:.6f}  [{threshold_source}]")

    n_detected    = int(ensemble_anomaly.sum())
    rate_detected = n_detected / n_test * 100 if n_test > 0 else 0.0
    _log(f"     Detectees : {n_detected:,} / {n_test:,} ({rate_detected:.2f}%)")

    # Votes indicatifs (tracabilite CSV)
    pct_ind      = (1.0 - TRAIN_CONTAMINATION) * 100.0
    if_thr_ind   = float(np.percentile(if_scores_train,   pct_ind))
    ae_thr_ind   = float(np.percentile(ae_scores_train,   pct_ind))
    lstm_thr_ind = float(np.percentile(lstm_scores_train, pct_ind))

    if_anomaly_ind   = (if_scores_test   >= if_thr_ind).astype(int)
    ae_anomaly_ind   = (ae_scores_test   >= ae_thr_ind).astype(int)
    lstm_anomaly_ind = (lstm_scores_test >= lstm_thr_ind).astype(int)
    votes_ind        = if_anomaly_ind + ae_anomaly_ind + lstm_anomaly_ind

    _log(f"     Votes indicatifs 3/3 : {int((votes_ind==3).sum()):,}")
    _log(f"     Votes indicatifs 2/3 : {int((votes_ind==2).sum()):,}")
    _log(f"     Votes indicatifs 1/3 : {int((votes_ind==1).sum()):,}")

    # ── 4.E  CLASSIFICATION DU TYPE D'ANOMALIE ───────────────────
    _log("\n  [4.E] Classification du type d'anomalie API")
    anomaly_idx = np.where(ensemble_anomaly == 1)[0]

    if len(anomaly_idx) == 0:
        _log("  WARN : aucune anomalie detectee.")
        anomaly_type_array = np.array([], dtype=str)
    else:
        df_anom_raw = df_test_raw.iloc[anomaly_idx].reset_index(drop=True)

        def classify_api_by_rules(row):
            r     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
            err   = str(r.get(_err_col, _none_err_str) or _none_err_str).strip().upper()
            stat  = safe_int(row_get(r,   "http_status_code",          200))
            resp  = safe_float(row_get(r, "response_time_ms",          0))
            db_ms = safe_float(row_get(r, "db_query_time_ms",          0))
            rl    = safe_float(row_get(r, "rate_limit_triggered",      0))
            rpu   = safe_float(row_get(r, "requests_per_minute_user",  0))
            rpi   = safe_float(row_get(r, "requests_per_minute_ip",    0))
            conc  = safe_float(row_get(r, "concurrent_requests",       0))
            retry = safe_float(row_get(r, "retry_count",               0))
            night = safe_int(row_get(r,   "is_night",                  0))

            if "TIMEOUT" in err:                        return "Timeout"
            if "BACKEND" in err or stat >= 500:         return "Erreur backend"
            if "RATE" in err or "LIMIT" in err or rl == 1:
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
            _dc = [c for c in ["response_time_ms", "db_query_time_ms",
                                "cpu_usage_server_pct", "memory_usage_server_pct",
                                "requests_per_minute_ip", "concurrent_requests", "retry_count"]
                   if c in df_anom_raw.columns]
            X_a    = df_anom_raw[ambiguous_mask][_dc].fillna(0).values.astype(np.float32)
            sc_d   = StandardScaler(); X_a_sc = sc_d.fit_transform(X_a)
            bk, bs = 2, -1.0
            for k in range(2, min(6, n_ambiguous)):
                try:
                    lt = KMeans(n_clusters=k, random_state=RANDOM_STATE,
                                n_init=10).fit_predict(X_a_sc)
                    if len(set(lt)) > 1:
                        s = silhouette_score(X_a_sc, lt)
                        if s > bs: bs, bk = s, k
                except Exception:
                    pass
            km  = KMeans(n_clusters=bk, random_state=RANDOM_STATE, n_init=15)
            cl  = km.fit_predict(X_a_sc)
            cen = pd.DataFrame(sc_d.inverse_transform(km.cluster_centers_), columns=_dc)

            def _ambig_label(c):
                cd = c.to_dict() if hasattr(c, "to_dict") else dict(c)
                if safe_float(cd.get("requests_per_minute_ip",  0)) > 500: return "Abuse API"
                if safe_float(cd.get("concurrent_requests",     0)) > 1500: return "Explosion trafic"
                if safe_float(cd.get("response_time_ms",        0)) > 2000: return "Probleme performance"
                if safe_float(cd.get("cpu_usage_server_pct",    0)) > 90:   return "Erreur backend"
                if safe_float(cd.get("retry_count",             0)) >= 5:   return "Endpoint defaillant"
                return "Comportement anormal"

            km_map = {i: _ambig_label(cen.iloc[i]) for i in range(bk)}
            rule_labels[ambiguous_mask] = np.array([km_map[c] for c in cl])

        anomaly_type_array = rule_labels
        for t, c in pd.Series(anomaly_type_array).value_counts().items():
            _log(f"       {t:<40}: {c:>5}  ({c/len(anomaly_idx)*100:.1f}%)")

    # ── 4.F  SCORE DE RISQUE ─────────────────────────────────────
    def compute_api_risk(row):
        r     = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        stat  = safe_int(row_get(r,   "http_status_code",         200))
        resp  = safe_float(row_get(r, "response_time_ms",         0))
        rpi   = safe_float(row_get(r, "requests_per_minute_ip",   0))
        cpu   = safe_float(row_get(r, "cpu_usage_server_pct",     0))
        mem   = safe_float(row_get(r, "memory_usage_server_pct",  0))
        retry = safe_float(row_get(r, "retry_count",              0))
        night = safe_int(row_get(r,   "is_night",                 0))
        rpu   = safe_float(row_get(r, "requests_per_minute_user", 0))
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
    df_result["IF_anomaly"]      = if_anomaly_ind
    df_result["AE_anomaly"]      = ae_anomaly_ind
    df_result["LSTM_anomaly"]    = lstm_anomaly_ind
    df_result["ensemble_votes"]  = votes_ind
    df_result["is_anomaly"]      = ensemble_anomaly
    df_result["composite_score"] = composite_test
    df_result["IF_score"]        = if_scores_test
    df_result["AE_score"]        = ae_scores_test
    df_result["LSTM_score"]      = lstm_scores_test
    df_result["Anomaly_type"]    = "Normal"
    df_result["Risk"]            = 0

    if len(anomaly_idx) > 0:
        df_result.loc[anomaly_idx, "Anomaly_type"] = anomaly_type_array
        df_result.loc[anomaly_idx, "Risk"] = (
            df_result.loc[anomaly_idx].apply(compute_api_risk, axis=1)
        )

    anomalies     = df_result[df_result["is_anomaly"] == 1].copy()
    total, n_anom = len(df_result), len(anomalies)
    rate          = n_anom / total * 100 if total > 0 else 0.0
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
        ax2.scatter(X_pca[mn, 0], X_pca[mn, 1], c="lightgrey", s=4, alpha=0.3, label="Normal")
        pal = sns.color_palette("tab10", anomalies["Anomaly_type"].nunique())
        for i, atype in enumerate(anomalies["Anomaly_type"].unique()):
            ix = np.where(
                (df_result["is_anomaly"].values == 1) &
                (df_result["Anomaly_type"].values == atype)
            )[0]
            if len(ix) > 0:
                ax2.scatter(X_pca[ix, 0], X_pca[ix, 1],
                            c=[pal[i]], s=25, alpha=0.85, label=str(atype))
        ax2.set_title(
            f"PCA 2D API — {rate:.2f}% detectees  |  seuil: {composite_threshold:.4f}\n"
            f"PC1={pca.explained_variance_ratio_[0]*100:.1f}%  "
            f"PC2={pca.explained_variance_ratio_[1]*100:.1f}%")
        ax2.legend(fontsize=9); plt.tight_layout()
        fig2.savefig(PLOT_PCA, dpi=100); plt.close(fig2)

    _log(f"  OK {PLOT_CONVERGENCE}")
    _log(f"  OK {PLOT_PCA}")

    # ============================================================
    # PHASE 6 — DEPLOYMENT & TOP 20
    # ============================================================
    _log("\n" + "=" * 65)
    _log("PHASE 6 — DEPLOYMENT & MONITORING")
    _log("=" * 65)

    top_cols = [c for c in ["event_id", "timestamp", "api_name",
                             "http_method", "client_type"] if c in anomalies.columns]
    top_cols += ["Anomaly_type", "Risk", "composite_score", "ensemble_votes"]
    top20 = anomalies.sort_values(["Risk", "composite_score"], ascending=False).head(20)
    _log("\n  TOP 20 ANOMALIES API :")
    _log(top20[[c for c in top_cols if c in top20.columns]].to_string(index=False)
         if len(top20) > 0 else "  (aucune anomalie detectee)")

    # ============================================================
    # EXPORT CSV
    # ============================================================
    _log("\n" + "=" * 65)
    _log("EXPORT DES RESULTATS — CSV  →  API_info/")
    _log("=" * 65)

    exp_cols = list(dict.fromkeys(
        c for c in (list(df_test_raw.columns)
                    + ["is_anomaly", "Anomaly_type", "Risk", "composite_score",
                       "IF_score", "AE_score", "LSTM_score",
                       "ensemble_votes", "IF_anomaly", "AE_anomaly", "LSTM_anomaly"])
        if c in df_result.columns
    ))

    df_result[exp_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    if n_anom > 0:
        (anomalies[[c for c in exp_cols if c in anomalies.columns]]
         .sort_values(["Risk", "composite_score"], ascending=False)
         .to_csv(ANOM_PATH, index=False, encoding="utf-8-sig"))
    else:
        pd.DataFrame(columns=exp_cols).to_csv(ANOM_PATH, index=False, encoding="utf-8-sig")

    _log(f"  OK {OUTPUT_PATH}")
    _log(f"  OK {ANOM_PATH}")

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _eid_c = next((c for c in ["event_id", "Event_id"] if c in df_result.columns), None)

    _log("\n" + "=" * 65)
    _log("EXPORT INCREMENTAL — Data_Analyst/")
    _log("=" * 65)
    incremental_save_to_data_analyst(df_result[exp_cols], DA_OUTPUT_PATH,
                                     id_col=_eid_c, run_ts=run_ts)

    _log("\n" + "=" * 65)
    _log("EXPORT MONGODB")
    _log("=" * 65)

    def _to_native(v):
        if isinstance(v, (np.integer,)):  return int(v)
        if isinstance(v, (np.floating,)): return None if v != v else float(v)
        if isinstance(v, (np.bool_,)):    return bool(v)
        return v

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
        client.server_info()
        col  = client[MONGO_DB][MONGO_COL]
        df_c = df_result[exp_cols].copy()
        df_c.replace([float("inf"), float("-inf")], None, inplace=True)
        df_c = df_c.where(df_c.notna(), other=None)
        df_c["pipeline_run_at"] = run_ts
        docs = [{k: _to_native(v) for k, v in r.items()}
                for r in df_c.to_dict(orient="records")]
        if _eid_c:
            ops = [UpdateOne({_eid_c: d[_eid_c]}, {"$set": d}, upsert=True) for d in docs]
            res = col.bulk_write(ops, ordered=False)
            _log(f"  OK upsert : {res.upserted_count} inseres | {res.modified_count} mis a jour")
        else:
            deleted = col.delete_many({"pipeline_run_at": run_ts}).deleted_count
            if deleted: _log(f"  Anciens docs supprimes : {deleted}")
            res = col.insert_many(docs, ordered=False)
            _log(f"  OK insert : {len(res.inserted_ids):,} documents")
        for idx in ["is_anomaly", "Anomaly_type", "Risk", "pipeline_run_at"]:
            col.create_index(idx)
        if _eid_c: col.create_index(_eid_c, unique=True, sparse=True)
        client.close()
        _log("  OK index crees / verifies")
    except Exception as mongo_err:
        _log(f"  ERREUR MongoDB (non bloquant) : {mongo_err}")
        _log("  Pipeline continue — CSV sauvegardes.")

    with open(DONE_FLAG_PATH, "w", encoding="utf-8") as _f:
        _f.write(run_ts)

    _log("\n" + "=" * 65)
    _log(f"  TERMINE — Anomalies : {n_anom:,} ({rate:.2f}%) | Critiques : {crit}")
    _log(f"  Seuil : {composite_threshold:.6f}  [{threshold_source}]")
    _log(f"  Run   : {run_ts}")
    _log(f"  Dossier : {OUTPUT_DIR}")
    _log("=" * 65)
    sys.stdout.flush()

except Exception as _fatal:
    print("\n" + "=" * 65, flush=True)
    print("ERREUR FATALE DU PIPELINE API LOGS", flush=True)
    print("=" * 65, flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    sys.exit(1)