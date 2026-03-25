# ================================================================
# DETECTION D'ANOMALIES LOGS APPLICATIFS — PIPELINE CRISP-DM v2
# ================================================================
# Fichier : E:\backend\app\IA_anomaly_detection\LogsApplicatifs.py
# CSV attendus dans le meme dossier :
#   - LogsApplicatifs.csv          (train)
#   - Logs_Applicatifs_test.csv    (test)
# Sorties dans le sous-dossier App_info/ :
#   - Detected_App_Anomalies.csv
#   - Detected_App_Anomalies_anomalies_only.csv
#   - plot_app_distributions.png
#   - plot_app_convergence.png
#   - plot_app_pca.png
# ================================================================

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os
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


# ================================================================
# SECTION 0 — CONFIGURATION GLOBALE
# ================================================================
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(BASE_DIR, "App_info")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRAIN_PATH  = os.path.join(BASE_DIR, "LogsApplicatifs.csv")
TEST_PATH   = os.path.join(BASE_DIR, "Logs_Applicatifs_test.csv")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "Detected_App_Anomalies.csv")

PLOT_DISTRIBUTIONS = os.path.join(OUTPUT_DIR, "plot_app_distributions.png")
PLOT_CONVERGENCE   = os.path.join(OUTPUT_DIR, "plot_app_convergence.png")
PLOT_PCA           = os.path.join(OUTPUT_DIR, "plot_app_pca.png")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "APP_db")
MONGO_COL = "detected_app_anomalies"

# Noms de colonnes catégorielles — casse originale du CSV
CATEGORICAL_COLS = [
    "Application_name", "Server_instance", "Environment",
    "User_type", "Endpoint", "Http_method", "Error_code",
    "Config_version", "Deployment_version"
]

# Features numériques pures
NUMERIC_FEATURES = [
    "Response_time_ms", "Db_query_time_ms", "Cpu_usage_percent",
    "Memory_usage_percent", "Thread_pool_usage_percent",
    "Db_connection_pool_usage", "Retry_count", "Active_users_current",
    "Transactions_per_minute", "Cache_hit_ratio",
    "Payload_size_bytes", "Response_size_bytes"
]

IF_CONTAMINATION = "auto"
N_SIGMA_AE       = 1.5
N_SIGMA_LSTM     = 1.5
VOTE_THRESHOLD   = 1
LSTM_WINDOW      = 5
LSTM_SAMPLE      = 8_000
RANDOM_STATE     = 42


# ================================================================
# UTILITAIRE — accès robuste à une valeur dans une ligne pandas
# ================================================================
def _get(row, col, default=0):
    """
    Accès sécurisé à row[col] qu'il s'agisse d'un dict ou d'une Series pandas.
    Retourne default si la colonne est absente ou NaN.
    """
    try:
        v = row[col] if isinstance(row, dict) else row.get(col, default)
        return default if (v is None or (isinstance(v, float) and np.isnan(v))) else v
    except Exception:
        return default


# ================================================================
# PHASE 1 — BUSINESS UNDERSTANDING
# ================================================================
print("=" * 65)
print("PHASE 1 — BUSINESS UNDERSTANDING")
print("=" * 65)
print(f"""
Objectif : Detection automatique d'anomalies dans les logs applicatifs.
Sorties  : is_anomaly | Anomaly_type | Risk (0-10)
Modeles  : Isolation Forest + Autoencoder + LSTM Autoencoder
Vote     : anomalie si >= {VOTE_THRESHOLD} modele(s) detecte
MongoDB  : {MONGO_URI} / db={MONGO_DB} / col={MONGO_COL}
Dossier  : {OUTPUT_DIR}
""")


# ================================================================
# PHASE 2 — DATA UNDERSTANDING
# ================================================================
print("=" * 65)
print("PHASE 2 — DATA UNDERSTANDING")
print("=" * 65)

df_train = pd.read_csv(TRAIN_PATH)
df_test  = pd.read_csv(TEST_PATH)

# ── FIX 1 : normalisation des noms de colonnes ───────────────────
# On garde la casse d'origine mais on strip les espaces
df_train.columns = df_train.columns.str.strip()
df_test.columns  = df_test.columns.str.strip()

# Construire un mapping insensible à la casse pour retrouver les colonnes réelles
def _find_col(df, name):
    """Retourne le nom réel de la colonne dans df (insensible à la casse), ou name."""
    mapping = {c.lower(): c for c in df.columns}
    return mapping.get(name.lower(), name)

# Reconstruire les listes avec les vrais noms de colonnes du CSV
CATEGORICAL_COLS  = [_find_col(df_train, c) for c in CATEGORICAL_COLS]
NUMERIC_FEATURES  = [_find_col(df_train, c) for c in NUMERIC_FEATURES]
CATEGORICAL_COLS  = [c for c in CATEGORICAL_COLS if c in df_train.columns]
NUMERIC_FEATURES  = [c for c in NUMERIC_FEATURES if c in df_train.columns]

print(f"  Catégorielles détectées : {CATEGORICAL_COLS}")
print(f"  Numériques détectées    : {NUMERIC_FEATURES}")

for name, df in [("TRAIN", df_train), ("TEST", df_test)]:
    print(f"  [{name}] shape={df.shape} | nulls={df.isnull().sum().sum()}")

# ── Distributions numériques ─────────────────────────────────────
n_plots = min(12, len(NUMERIC_FEATURES))
fig, axes = plt.subplots(3, 4, figsize=(18, 10))
for ax, feat in zip(axes.flatten(), NUMERIC_FEATURES[:n_plots]):
    v = df_train[feat].dropna()
    v.clip(lower=v.quantile(0.01), upper=v.quantile(0.99)).plot(
        kind='hist', bins=40, ax=ax, color='#7209b7', edgecolor='white')
    ax.set_title(feat, fontsize=9)
    ax.set_xlabel("")
for ax in axes.flatten()[n_plots:]:
    ax.set_visible(False)
plt.suptitle("Phase 2 — Distributions Logs Applicatifs (TRAIN)", fontsize=13, fontweight='bold')
plt.tight_layout()
fig.savefig(PLOT_DISTRIBUTIONS, dpi=100)
plt.close(fig)
print(f"  OK {PLOT_DISTRIBUTIONS} sauvegarde")


# ================================================================
# PHASE 3 — DATA PREPARATION
# ================================================================
print("\n" + "=" * 65)
print("PHASE 3 — DATA PREPARATION")
print("=" * 65)

# ── FIX 2 : FEATURES = numériques + catégorielles (dans l'ordre stable)
FEATURES = NUMERIC_FEATURES + CATEGORICAL_COLS

def prepare_data(df_tr_in, df_te_in, features, cat_cols):
    df_tr = df_tr_in.copy()
    df_te = df_te_in.copy()
    label_encoders = {}

    for col in cat_cols:
        if col not in df_tr.columns:
            continue
        le = LabelEncoder()
        df_tr[col] = df_tr[col].fillna("NA").astype(str)
        df_te[col] = df_te[col].fillna("NA").astype(str)
        le.fit(df_tr[col])
        unk = set(df_te[col]) - set(le.classes_)
        if unk:
            le.classes_ = np.append(le.classes_, list(unk))
        df_tr[col] = le.transform(df_tr[col])
        df_te[col] = le.transform(df_te[col])
        label_encoders[col] = le

    avail    = [f for f in features if f in df_tr.columns]
    X_tr_raw = df_tr[avail].fillna(0).values.astype(np.float32)
    X_te_raw = df_te[avail].fillna(0).values.astype(np.float32)

    sc_std   = StandardScaler()
    X_tr_std = sc_std.fit_transform(X_tr_raw)
    X_te_std = sc_std.transform(X_te_raw)

    sc_mm   = MinMaxScaler()
    X_tr_mm = sc_mm.fit_transform(X_tr_raw)
    X_te_mm = sc_mm.transform(X_te_raw)

    print(f"  OK Features : {len(avail)} | Train : {X_tr_std.shape} | Test : {X_te_std.shape}")
    return X_tr_std, X_te_std, X_tr_mm, X_te_mm, avail, label_encoders, sc_std, sc_mm

(X_train_std, X_test_std, X_train_mm, X_test_mm,
 avail_features, label_encoders, scaler_std, scaler_mm) = prepare_data(
    df_train, df_test, FEATURES, CATEGORICAL_COLS)

n_feat = X_train_std.shape[1]

# ── FIX 3 : résoudre Error_code="NONE" de façon robuste ──────────
# Plusieurs variantes possibles : "NONE", "None", "none", "0", "OK"…
_err_col = _find_col(df_train, "Error_code")
_none_encoded = -1   # valeur sentinelle par défaut

if _err_col in label_encoders:
    _le_err = label_encoders[_err_col]
    # Essayer plusieurs variantes du "pas d'erreur"
    for _candidate in ["NONE", "None", "none", "OK", "ok", "0", "200", "NA"]:
        if _candidate in _le_err.classes_:
            _none_encoded = int(_le_err.transform([_candidate])[0])
            print(f"  OK Error_code sans erreur détecté : '{_candidate}' → encodé {_none_encoded}")
            break
    else:
        # Aucune valeur "neutre" trouvée : utiliser la valeur la plus fréquente du train
        _most_common = df_train[_err_col].fillna("NA").astype(str).mode()[0]
        if _most_common in _le_err.classes_:
            _none_encoded = int(_le_err.transform([_most_common])[0])
        print(f"  WARN Error_code : pas de valeur NONE trouvée, "
              f"utilisation de la plus fréquente '{_most_common}' → {_none_encoded}")


# ================================================================
# PHASE 4 — MODELING
# ================================================================
print("\n" + "=" * 65)
print("PHASE 4 — MODELING")
print("=" * 65)

# ── 4.A  ISOLATION FOREST ────────────────────────────────────────
print("\n  [4.A] Isolation Forest")
iso = IsolationForest(
    n_estimators=300,
    contamination=IF_CONTAMINATION,
    max_features=0.8,
    random_state=RANDOM_STATE,
    n_jobs=-1
)
iso.fit(X_train_std)
if_raw     = -iso.decision_function(X_test_std)
if_anomaly = (iso.predict(X_test_std) == -1).astype(int)
if_scores  = (if_raw - if_raw.min()) / (if_raw.max() - if_raw.min() + 1e-9)
print(f"     Anomalies : {if_anomaly.sum():,} ({if_anomaly.mean()*100:.1f}%)")


# ── 4.B  AUTOENCODER DENSE ───────────────────────────────────────
print("\n  [4.B] Autoencoder Dense")

def build_ae(n):
    inp = Input(shape=(n,))
    x   = Dense(128, activation='relu')(inp)
    x   = Dropout(0.1)(x)
    x   = Dense(32, activation='relu')(x)
    x   = Dense(128, activation='relu')(x)
    out = Dense(n, activation='linear')(x)
    m   = Model(inp, out, name="App_AE")
    m.compile(optimizer=Adam(2e-3), loss='mse')
    return m

ae      = build_ae(n_feat)
ae_hist = ae.fit(
    X_train_std, X_train_std,
    epochs=60, batch_size=512, validation_split=0.1,
    callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
    verbose=0
)
print(f"     Epochs : {len(ae_hist.history['loss'])}")

ae_mse_tr  = np.mean((X_train_std - ae.predict(X_train_std, verbose=0))**2, axis=1)
ae_thr     = ae_mse_tr.mean() + N_SIGMA_AE * ae_mse_tr.std()
ae_mse_te  = np.mean((X_test_std  - ae.predict(X_test_std,  verbose=0))**2, axis=1)
ae_anomaly = (ae_mse_te > ae_thr).astype(int)
ae_scores  = (ae_mse_te - ae_mse_te.min()) / (ae_mse_te.max() - ae_mse_te.min() + 1e-9)
print(f"     Seuil : {ae_thr:.6f} | Anomalies : {ae_anomaly.sum():,} ({ae_anomaly.mean()*100:.1f}%)")


# ── 4.C  LSTM AUTOENCODER ────────────────────────────────────────
print("\n  [4.C] LSTM Autoencoder")

def make_sequences(X, w):
    n       = len(X)
    shape   = (n - w + 1, w, X.shape[1])
    strides = (X.strides[0], X.strides[0], X.strides[1])
    return np.lib.stride_tricks.as_strided(X, shape=shape, strides=strides).copy()

sample_size = min(LSTM_SAMPLE, len(X_train_mm) - LSTM_WINDOW)
idx_s    = np.random.choice(len(X_train_mm) - LSTM_WINDOW, size=sample_size, replace=False)
X_tr_seq = make_sequences(X_train_mm, LSTM_WINDOW)[idx_s]
X_te_seq = make_sequences(X_test_mm,  LSTM_WINDOW)

def build_lstm_ae(w, n):
    inp = Input(shape=(w, n))
    x   = LSTM(64, activation='tanh')(inp)
    x   = RepeatVector(w)(x)
    x   = LSTM(64, activation='tanh', return_sequences=True)(x)
    out = TimeDistributed(Dense(n))(x)
    m   = Model(inp, out, name="App_LSTM_AE")
    m.compile(optimizer=Adam(2e-3), loss='mse')
    return m

lstm_ae   = build_lstm_ae(LSTM_WINDOW, n_feat)
lstm_hist = lstm_ae.fit(
    X_tr_seq, X_tr_seq,
    epochs=40, batch_size=256, validation_split=0.1,
    callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
    verbose=0
)
print(f"     Epochs : {len(lstm_hist.history['loss'])}")

lstm_mse_tr  = np.mean((X_tr_seq - lstm_ae.predict(X_tr_seq, verbose=0))**2, axis=(1, 2))
lstm_thr     = lstm_mse_tr.mean() + N_SIGMA_LSTM * lstm_mse_tr.std()
lstm_mse_te  = np.mean((X_te_seq - lstm_ae.predict(X_te_seq, verbose=0))**2, axis=(1, 2))
lstm_mse_pad = np.concatenate([np.full(LSTM_WINDOW - 1, np.median(lstm_mse_te)), lstm_mse_te])
lstm_anomaly = (lstm_mse_pad > lstm_thr).astype(int)
lstm_scores  = ((lstm_mse_pad - lstm_mse_pad.min())
                / (lstm_mse_pad.max() - lstm_mse_pad.min() + 1e-9))
print(f"     Seuil : {lstm_thr:.6f} | Anomalies : {lstm_anomaly.sum():,} ({lstm_anomaly.mean()*100:.1f}%)")


# ── 4.D  VOTE D'ENSEMBLE ─────────────────────────────────────────
print("\n  [4.D] Vote d'ensemble (IF + AE + LSTM)")
votes            = if_anomaly + ae_anomaly + lstm_anomaly
ensemble_anomaly = (votes >= VOTE_THRESHOLD).astype(int)
composite_score  = (if_scores + ae_scores + lstm_scores) / 3.0

print(f"     3/3 Critique  : {(votes==3).sum():,}")
print(f"     2/3 Confirme  : {(votes==2).sum():,}")
print(f"     1/3 Incertain : {(votes==1).sum():,}")
print(f"     Anomalies retenues : {ensemble_anomaly.sum():,} ({ensemble_anomaly.mean()*100:.1f}%)")


# ── 4.E  CLASSIFICATION DU TYPE D'ANOMALIE ───────────────────────
print("\n  [4.E] Classification du type d'anomalie Applicatif")
anomaly_idx = np.where(ensemble_anomaly == 1)[0]

# ── FIX 4 : guard si aucune anomalie détectée ────────────────────
if len(anomaly_idx) == 0:
    print("  WARN : aucune anomalie détectée — vérifier VOTE_THRESHOLD ou le fichier test.")
    anomaly_type_array = np.array([], dtype=str)
else:
    df_anom = df_test.iloc[anomaly_idx].copy()

    # ── FIX 5 : classify_app_by_rules utilise .get() sur une Series
    # → on convertit chaque ligne en dict avant l'appel
    def classify_app_by_rules(row):
        # row peut être une Series pandas — conversion sécurisée
        r = row.to_dict() if hasattr(row, 'to_dict') else row

        cpu      = float(_get(r, _find_col(df_test, "Cpu_usage_percent"), 0))
        mem      = float(_get(r, _find_col(df_test, "Memory_usage_percent"), 0))
        thread   = float(_get(r, _find_col(df_test, "Thread_pool_usage_percent"), 0))
        db_conn  = float(_get(r, _find_col(df_test, "Db_connection_pool_usage"), 0))
        resp_ms  = float(_get(r, _find_col(df_test, "Response_time_ms"), 0))
        db_ms    = float(_get(r, _find_col(df_test, "Db_query_time_ms"), 0))
        tpm      = float(_get(r, _find_col(df_test, "Transactions_per_minute"), 0))
        users    = float(_get(r, _find_col(df_test, "Active_users_current"), 0))
        retry    = float(_get(r, _find_col(df_test, "Retry_count"), 0))
        err_val  = _get(r, _err_col, _none_encoded)
        try:
            err = int(float(err_val))
        except Exception:
            err = _none_encoded

        if cpu > 85 or mem > 85:
            return "Dégradation performance"
        if thread > 90 or db_conn > 90:
            return "Mauvaise configuration pool"
        if resp_ms > 2000 or db_ms > 1000:
            return "Timeout / lenteur DB"
        if tpm > 5000 or tpm < 0:
            return "Pic transaction / incohérence"
        if users > 5000:
            return "Comportement utilisateur anormal"
        if err != _none_encoded:
            return "Pic d'erreurs applicatives"
        if retry > 3:
            return "Rejeux excessifs"
        return "Comportement anormal"

    rule_labels    = df_anom.apply(classify_app_by_rules, axis=1).values
    ambiguous_mask = (rule_labels == "Comportement anormal")
    n_ambiguous    = ambiguous_mask.sum()
    print(f"     Regles : {(~ambiguous_mask).sum()} | KMeans : {n_ambiguous}")

    if n_ambiguous >= 4:
        DISC       = [_find_col(df_test, c) for c in [
                         "Response_time_ms", "Db_query_time_ms", "Cpu_usage_percent",
                         "Memory_usage_percent", "Thread_pool_usage_percent",
                         "Transactions_per_minute", "Active_users_current"]]
        disc_avail = [f for f in DISC if f in df_anom.columns]
        X_ambig    = df_anom[ambiguous_mask][disc_avail].fillna(0).values.astype(np.float32)
        sc_d       = StandardScaler()
        X_ambig_sc = sc_d.fit_transform(X_ambig)
        best_k, best_sil = 2, -1
        for k in range(2, min(6, len(X_ambig))):
            lab_t = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit_predict(X_ambig_sc)
            if len(set(lab_t)) > 1:
                s = silhouette_score(X_ambig_sc, lab_t)
                if s > best_sil:
                    best_sil, best_k = s, k
        km  = KMeans(n_clusters=best_k, random_state=RANDOM_STATE, n_init=15)
        cl  = km.fit_predict(X_ambig_sc)
        cen = pd.DataFrame(sc_d.inverse_transform(km.cluster_centers_), columns=disc_avail)

        _cpu_c  = _find_col(df_test, "Cpu_usage_percent")
        _mem_c  = _find_col(df_test, "Memory_usage_percent")
        _thr_c  = _find_col(df_test, "Thread_pool_usage_percent")
        _rms_c  = _find_col(df_test, "Response_time_ms")
        _dms_c  = _find_col(df_test, "Db_query_time_ms")
        _tpm_c  = _find_col(df_test, "Transactions_per_minute")
        _usr_c  = _find_col(df_test, "Active_users_current")

        def name_app_ambig(c):
            cd = c.to_dict() if hasattr(c, 'to_dict') else c
            if _get(cd, _cpu_c, 0) > 85 or _get(cd, _mem_c, 0) > 85:
                return "Dégradation performance"
            if _get(cd, _thr_c, 0) > 90:
                return "Mauvaise configuration pool"
            if _get(cd, _rms_c, 0) > 2000 or _get(cd, _dms_c, 0) > 1000:
                return "Timeout / lenteur DB"
            if _get(cd, _tpm_c, 0) > 5000:
                return "Pic transaction / incohérence"
            if _get(cd, _usr_c, 0) > 5000:
                return "Comportement utilisateur anormal"
            return "Comportement anormal"

        km_map = {i: name_app_ambig(cen.iloc[i]) for i in range(best_k)}
        rule_labels[ambiguous_mask] = np.array([km_map[c] for c in cl])

    anomaly_type_array = rule_labels
    for t, c in pd.Series(anomaly_type_array).value_counts().items():
        print(f"       {t:<45}: {c:>5}  ({c/len(anomaly_idx)*100:.1f}%)")


# ── FIX 6 : compute_app_risk utilise aussi .to_dict() ────────────
_resp_c = _find_col(df_test, "Response_time_ms")
_dbms_c = _find_col(df_test, "Db_query_time_ms")
_thr_c2 = _find_col(df_test, "Thread_pool_usage_percent")
_dbc_c  = _find_col(df_test, "Db_connection_pool_usage")
_tpm_c2 = _find_col(df_test, "Transactions_per_minute")
_cpu_c2 = _find_col(df_test, "Cpu_usage_percent")
_mem_c2 = _find_col(df_test, "Memory_usage_percent")
_usr_c2 = _find_col(df_test, "Active_users_current")
_rtr_c  = _find_col(df_test, "Retry_count")

def compute_app_risk(row):
    r = row.to_dict() if hasattr(row, 'to_dict') else row
    risk = 0
    err_val = _get(r, _err_col, _none_encoded)
    try:
        err = int(float(err_val))
    except Exception:
        err = _none_encoded

    if err != _none_encoded:                                        risk += 9
    if float(_get(r, _tpm_c2, 0)) > 5000:                         risk += 8
    if float(_get(r, _resp_c, 0)) > 2000 or \
       float(_get(r, _dbms_c, 0)) > 1000:                         risk += 7
    if float(_get(r, _thr_c2, 0)) > 90 or \
       float(_get(r, _dbc_c, 0)) > 90:                            risk += 6
    if float(_get(r, _cpu_c2, 0)) > 90 or \
       float(_get(r, _mem_c2, 0)) > 90:                           risk += 6
    if float(_get(r, _usr_c2, 0)) > 10_000:                       risk += 5
    if float(_get(r, _rtr_c, 0)) > 5:                             risk += 4
    return min(risk, 10)


# ================================================================
# PHASE 5 — EVALUATION + GRAPHIQUES
# ================================================================
print("\n" + "=" * 65)
print("PHASE 5 — EVALUATION")
print("=" * 65)

df_result = df_test.copy()
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
        df_result.loc[anomaly_idx].apply(compute_app_risk, axis=1)
    )

anomalies     = df_result[df_result["is_anomaly"] == 1].copy()
total, n_anom = len(df_result), len(anomalies)
rate          = n_anom / total * 100
crit          = (anomalies["Risk"] >= 8).sum()

# ── Courbes de convergence ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, hist, title, c1, c2 in [
    (axes[0], ae_hist,   "Autoencoder Dense App", '#7209b7', 'orange'),
    (axes[1], lstm_hist, "LSTM AE App",           '#480ca8', 'red')
]:
    ax.plot(hist.history['loss'],     label='Train', color=c1, linewidth=2)
    ax.plot(hist.history['val_loss'], label='Val',   color=c2, linewidth=2)
    ax.set_title(f"{title} — Loss MSE")
    ax.legend()
    ax.grid(alpha=0.3)
plt.tight_layout()
fig.savefig(PLOT_CONVERGENCE, dpi=100)
plt.close(fig)

# ── PCA 2D ───────────────────────────────────────────────────────
if n_anom > 5:
    pca   = PCA(n_components=2, random_state=RANDOM_STATE)
    X_pca = pca.fit_transform(X_test_std)
    fig2, ax2 = plt.subplots(figsize=(11, 7))
    mn = df_result["is_anomaly"] == 0
    ax2.scatter(X_pca[mn, 0], X_pca[mn, 1], c='lightgrey', s=4, alpha=0.3, label='Normal')
    pal = sns.color_palette("tab10", anomalies["Anomaly_type"].nunique())
    for i, atype in enumerate(anomalies["Anomaly_type"].unique()):
        ix = np.where(
            (df_result["is_anomaly"] == 1) &
            (df_result["Anomaly_type"] == atype)
        )[0]
        ax2.scatter(X_pca[ix, 0], X_pca[ix, 1], c=[pal[i]], s=25, alpha=0.85, label=atype)
    ax2.set_title(
        f"PCA 2D App — PC1={pca.explained_variance_ratio_[0]*100:.1f}%"
        f" | PC2={pca.explained_variance_ratio_[1]*100:.1f}%"
    )
    ax2.legend(fontsize=9)
    plt.tight_layout()
    fig2.savefig(PLOT_PCA, dpi=100)
    plt.close(fig2)

print(f"  OK {PLOT_CONVERGENCE}")
print(f"  OK {PLOT_PCA}")


# ================================================================
# PHASE 6 — DEPLOYMENT & TOP 20
# ================================================================
print("\n" + "=" * 65)
print("PHASE 6 — DEPLOYMENT & MONITORING")
print("=" * 65)

_app_col  = _find_col(df_test, "Application_name")
_srv_col  = _find_col(df_test, "Server_instance")
_end_col  = _find_col(df_test, "Endpoint")
_evt_col  = _find_col(df_test, "Event_id")
_ts_col   = _find_col(df_test, "Timestamp")

id_cols  = [c for c in [_evt_col, _ts_col, _app_col, _srv_col, _end_col] if c in anomalies.columns]
top_cols = id_cols + ["Anomaly_type", "Risk", "composite_score", "ensemble_votes"]
top20    = anomalies.sort_values(["Risk", "composite_score"], ascending=False).head(20)
print("\n  TOP 20 ANOMALIES APPLICATIFS :")
print(top20[[c for c in top_cols if c in top20.columns]].to_string(index=False))


# ================================================================
# EXPORT CSV  →  App_info/
# ================================================================
print("\n" + "=" * 65)
print("EXPORT DES RESULTATS — CSV  →  App_info/")
print("=" * 65)

exp_cols = (list(df_test.columns)
            + ["is_anomaly", "Anomaly_type", "Risk", "composite_score",
               "IF_score", "AE_score", "LSTM_score",
               "ensemble_votes", "IF_anomaly", "AE_anomaly", "LSTM_anomaly"])
exp_cols = [c for c in exp_cols if c in df_result.columns]

df_result[exp_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

anom_path = os.path.join(OUTPUT_DIR, "Detected_App_Anomalies_anomalies_only.csv")
anomalies[exp_cols].sort_values(
    ["Risk", "composite_score"], ascending=False
).to_csv(anom_path, index=False, encoding="utf-8-sig")

print(f"  OK {OUTPUT_PATH}")
print(f"  OK {anom_path}")


# ================================================================
# EXPORT MONGODB
# ================================================================
print("\n" + "=" * 65)
print("EXPORT MONGODB — Detected_App_Anomalies.csv")
print("=" * 65)

def _to_native(v):
    if isinstance(v, (np.integer,)):  return int(v)
    if isinstance(v, (np.floating,)): return None if (v != v) else float(v)
    if isinstance(v, (np.bool_,)):    return bool(v)
    return v


def save_app_anomalies_to_mongo(df: pd.DataFrame, run_ts: str) -> None:
    print(f"  URI        : {MONGO_URI}")
    print(f"  Base       : {MONGO_DB}  |  Collection : {MONGO_COL}")
    print(f"  Documents  : {len(df):,}")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5_000)
        client.server_info()
        col = client[MONGO_DB][MONGO_COL]

        df_clean = df.copy()
        df_clean.replace([float("inf"), float("-inf")], None, inplace=True)
        df_clean = df_clean.where(df_clean.notna(), other=None)
        df_clean["pipeline_run_at"] = run_ts

        docs = [{k: _to_native(v) for k, v in row.items()}
                for row in df_clean.to_dict(orient="records")]

        # Chercher Event_id ou event_id
        _eid = _find_col(df, "Event_id")
        has_event_id = _eid in df.columns

        if has_event_id:
            operations = [
                UpdateOne({_eid: doc[_eid]}, {"$set": doc}, upsert=True)
                for doc in docs
            ]
            res = col.bulk_write(operations, ordered=False)
            print(f"  OK upsert  : {res.upserted_count} inseres | {res.modified_count} mis a jour")
        else:
            deleted = col.delete_many({"pipeline_run_at": run_ts}).deleted_count
            if deleted:
                print(f"  Anciens docs supprimes : {deleted}")
            res = col.insert_many(docs, ordered=False)
            print(f"  OK insert  : {len(res.inserted_ids):,} documents inseres")

        col.create_index("is_anomaly")
        col.create_index("Anomaly_type")
        col.create_index("Risk")
        col.create_index("pipeline_run_at")
        if has_event_id:
            col.create_index(_eid, unique=True, sparse=True)

        client.close()
        print("  OK index crees / verifies")

    except Exception as exc:
        print(f"  ERREUR MongoDB : {exc}")
        print("  Le pipeline continue — les CSV ont bien ete sauvegardes.")


run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
save_app_anomalies_to_mongo(df_result[exp_cols], run_timestamp)


# ================================================================
# RESUME FINAL
# ================================================================
print("\n" + "=" * 65)
print(f"  TERMINE — Anomalies : {n_anom:,} ({rate:.1f}%) | Critiques : {crit}")
print(f"  Run timestamp       : {run_timestamp}")
print(f"  Fichiers dans       : {OUTPUT_DIR}")
print("=" * 65)