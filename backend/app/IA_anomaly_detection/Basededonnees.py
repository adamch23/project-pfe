# ================================================================
# DETECTION D'ANOMALIES BASE DE DONNEES — PIPELINE CRISP-DM v1
# ================================================================
# Fichier : E:\backend\app\IA_anomaly_detection\BaseDeDonnees.py
# CSV attendus dans le meme dossier :
#   - BasedeDonnees.csv        (train)
#   - BasedeDonneestest.csv    (test)
# Sorties dans le sous-dossier DB_info/ :
#   - Detected_DB_Anomalies.csv
#   - Detected_DB_Anomalies_anomalies_only.csv
#   - plot_db_distributions.png
#   - plot_db_convergence.png
#   - plot_db_pca.png
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

# ── Dossier de sortie dédié au pipeline DB ───────────────────────
OUTPUT_DIR = os.path.join(BASE_DIR, "DB_info")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRAIN_PATH  = os.path.join(BASE_DIR, "BasedeDonnees.csv")
TEST_PATH   = os.path.join(BASE_DIR, "BasedeDonneestest.csv")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "Detected_DB_Anomalies.csv")

PLOT_DISTRIBUTIONS = os.path.join(OUTPUT_DIR, "plot_db_distributions.png")
PLOT_CONVERGENCE   = os.path.join(OUTPUT_DIR, "plot_db_convergence.png")
PLOT_PCA           = os.path.join(OUTPUT_DIR, "plot_db_pca.png")

# ── MongoDB ──────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "basededonne_db")
MONGO_COL = "detected_db_anomalies"
# ─────────────────────────────────────────────────────────────────

FEATURES = [
    "Rows_returned",
    "Rows_modified",
    "Execution_time_ms",
    "Cpu_db_usage_percent",
    "Memory_db_usage_percent",
    "Lock_wait_time_ms",
    "Deadlock_flag",
    "Full_table_scan_flag",
    "Index_usage_flag",
    "Active_sessions",
    "Connection_pool_usage_percent",
    "Transaction_log_growth_mb",
    "Backup_running_flag",
    "Db_instance",
    "Db_user",
    "Query_type",
    "Table_name"
]

CATEGORICAL_COLS = [
    "Db_instance",
    "Db_user",
    "Query_type",
    "Table_name"
]

IF_CONTAMINATION = "auto"
N_SIGMA_AE       = 1.5
N_SIGMA_LSTM     = 1.5
VOTE_THRESHOLD   = 1
LSTM_WINDOW      = 5
LSTM_SAMPLE      = 8_000
RANDOM_STATE     = 42


# ================================================================
# PHASE 1 — BUSINESS UNDERSTANDING
# ================================================================
print("=" * 65)
print("PHASE 1 — BUSINESS UNDERSTANDING")
print("=" * 65)
print(f"""
Objectif : Detection automatique d'anomalies dans les logs base de donnees.
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

for name, df in [("TRAIN", df_train), ("TEST", df_test)]:
    print(f"  [{name}] shape={df.shape} | nulls={df.isnull().sum().sum()}")

# Distributions des features numériques
numeric_feats = [f for f in FEATURES if f not in CATEGORICAL_COLS and f in df_train.columns]
n_plots = min(12, len(numeric_feats))
fig, axes = plt.subplots(3, 4, figsize=(18, 10))
for ax, feat in zip(axes.flatten(), numeric_feats[:n_plots]):
    v = df_train[feat].dropna()
    v.clip(lower=v.quantile(0.01), upper=v.quantile(0.99)).plot(
        kind='hist', bins=40, ax=ax, color='teal', edgecolor='white')
    ax.set_title(feat, fontsize=9)
    ax.set_xlabel("")
for ax in axes.flatten()[n_plots:]:
    ax.set_visible(False)
plt.suptitle("Phase 2 — Distributions des features DB (TRAIN)", fontsize=13, fontweight='bold')
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
        # Gestion des valeurs inconnues en test
        unk = set(df_te[col]) - set(le.classes_)
        if unk:
            le.classes_ = np.append(le.classes_, list(unk))
        df_tr[col] = le.transform(df_tr[col])
        df_te[col] = le.transform(df_te[col])
        label_encoders[col] = le

    avail    = [f for f in features if f in df_tr.columns]
    X_tr_raw = df_tr[avail].fillna(0).values.astype(np.float32)
    X_te_raw = df_te[avail].fillna(0).values.astype(np.float32)

    # StandardScaler → Isolation Forest & Autoencoder
    sc_std   = StandardScaler()
    X_tr_std = sc_std.fit_transform(X_tr_raw)
    X_te_std = sc_std.transform(X_te_raw)

    # MinMaxScaler → LSTM Autoencoder (séquences temporelles)
    sc_mm   = MinMaxScaler()
    X_tr_mm = sc_mm.fit_transform(X_tr_raw)
    X_te_mm = sc_mm.transform(X_te_raw)

    print(f"  OK Features : {len(avail)} | Train : {X_tr_std.shape} | Test : {X_te_std.shape}")
    return X_tr_std, X_te_std, X_tr_mm, X_te_mm, avail, label_encoders, sc_std, sc_mm

(X_train_std, X_test_std, X_train_mm, X_test_mm,
 avail_features, label_encoders, scaler_std, scaler_mm) = prepare_data(
    df_train, df_test, FEATURES, CATEGORICAL_COLS)

n_feat = X_train_std.shape[1]


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
    out = Dense(n,   activation='linear')(x)
    m   = Model(inp, out, name="DB_AE")
    m.compile(optimizer=Adam(2e-3), loss='mse')
    return m

ae      = build_ae(n_feat)
ae_hist = ae.fit(
    X_train_std, X_train_std,
    epochs=60,
    batch_size=512,
    validation_split=0.1,
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

# Echantillon aléatoire pour l'entraînement LSTM
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
    m   = Model(inp, out, name="DB_LSTM_AE")
    m.compile(optimizer=Adam(2e-3), loss='mse')
    return m

lstm_ae   = build_lstm_ae(LSTM_WINDOW, n_feat)
lstm_hist = lstm_ae.fit(
    X_tr_seq, X_tr_seq,
    epochs=40,
    batch_size=256,
    validation_split=0.1,
    callbacks=[EarlyStopping(patience=6, restore_best_weights=True)],
    verbose=0
)
print(f"     Epochs : {len(lstm_hist.history['loss'])}")

lstm_mse_tr  = np.mean((X_tr_seq - lstm_ae.predict(X_tr_seq, verbose=0))**2, axis=(1, 2))
lstm_thr     = lstm_mse_tr.mean() + N_SIGMA_LSTM * lstm_mse_tr.std()
lstm_mse_te  = np.mean((X_te_seq - lstm_ae.predict(X_te_seq, verbose=0))**2, axis=(1, 2))

# Padding médian pour les (W-1) premiers points sans séquence complète
lstm_mse_pad = np.concatenate([
    np.full(LSTM_WINDOW - 1, np.median(lstm_mse_te)),
    lstm_mse_te
])
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
print("\n  [4.E] Classification du type d'anomalie DB")
anomaly_idx = np.where(ensemble_anomaly == 1)[0]
df_anom     = df_test.iloc[anomaly_idx].copy()

def classify_db_by_rules(row):
    exec_ms  = row.get("Execution_time_ms", 0)
    lock_ms  = row.get("Lock_wait_time_ms", 0)
    deadlock = row.get("Deadlock_flag", 0)
    idx_use  = row.get("Index_usage_flag", 1)
    full_sc  = row.get("Full_table_scan_flag", 0)
    rows_ret = row.get("Rows_returned", 0)
    log_grow = row.get("Transaction_log_growth_mb", 0)
    cpu      = row.get("Cpu_db_usage_percent", 0)
    mem      = row.get("Memory_db_usage_percent", 0)
    conn     = row.get("Connection_pool_usage_percent", 0)

    if deadlock == 1:
        return "Deadlock"
    if exec_ms > 5000:
        return "Slow Query"
    if lock_ms > 2000:
        return "Lock Contention"
    if idx_use == 0 and full_sc == 1:
        return "Mauvais Index"
    if rows_ret > 100_000:
        return "Extraction massive données"
    if log_grow > 500:
        return "Suppression logs"
    if cpu > 90 or mem > 90:
        return "Saturation DB"
    if conn > 95:
        return "Saturation connexions"
    return "Comportement anormal"

rule_labels    = df_anom.apply(classify_db_by_rules, axis=1).values
ambiguous_mask = (rule_labels == "Comportement anormal")
n_ambiguous    = ambiguous_mask.sum()
print(f"     Regles : {(~ambiguous_mask).sum()} | KMeans : {n_ambiguous}")

if n_ambiguous >= 4:
    DISC       = ["Execution_time_ms", "Lock_wait_time_ms", "Rows_returned",
                  "Cpu_db_usage_percent", "Memory_db_usage_percent",
                  "Transaction_log_growth_mb", "Connection_pool_usage_percent"]
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

    def name_db_ambig(c):
        if c.get("Execution_time_ms", 0) > 5000:         return "Slow Query"
        if c.get("Lock_wait_time_ms", 0) > 2000:         return "Lock Contention"
        if c.get("Rows_returned", 0) > 100_000:          return "Extraction massive données"
        if c.get("Transaction_log_growth_mb", 0) > 500:  return "Suppression logs"
        if c.get("Cpu_db_usage_percent", 0) > 90:        return "Saturation DB"
        if c.get("Connection_pool_usage_percent", 0) > 95: return "Saturation connexions"
        return "Comportement anormal"

    km_map = {i: name_db_ambig(cen.iloc[i]) for i in range(best_k)}
    rule_labels[ambiguous_mask] = np.array([km_map[c] for c in cl])

anomaly_type_array = rule_labels
for t, c in pd.Series(anomaly_type_array).value_counts().items():
    print(f"       {t:<35}: {c:>5}  ({c/len(anomaly_idx)*100:.1f}%)")


# ── 4.F  SCORE DE RISQUE ─────────────────────────────────────────
def compute_db_risk(row):
    risk = 0
    if row.get("Deadlock_flag", 0) == 1:                        risk += 9
    if row.get("Rows_returned", 0) > 100_000:                   risk += 8
    if row.get("Transaction_log_growth_mb", 0) > 500:           risk += 8
    if row.get("Execution_time_ms", 0) > 5000:                  risk += 7
    if row.get("Connection_pool_usage_percent", 0) > 95:        risk += 7
    if row.get("Lock_wait_time_ms", 0) > 2000:                  risk += 6
    if row.get("Cpu_db_usage_percent", 0) > 90:                 risk += 6
    if row.get("Memory_db_usage_percent", 0) > 90:              risk += 6
    if row.get("Index_usage_flag", 1) == 0:                     risk += 4
    if row.get("Full_table_scan_flag", 0) == 1:                 risk += 3
    if row.get("Backup_running_flag", 0) == 1:                  risk += 2
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
        df_result.loc[anomaly_idx].apply(compute_db_risk, axis=1)
    )

anomalies     = df_result[df_result["is_anomaly"] == 1].copy()
total, n_anom = len(df_result), len(anomalies)
rate          = n_anom / total * 100
crit          = (anomalies["Risk"] >= 8).sum()

# ── Graphique convergence ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 4))
for ax, hist, title, c1, c2 in [
    (axes[0], ae_hist,   "Autoencoder Dense DB", 'teal',   'orange'),
    (axes[1], lstm_hist, "LSTM AE DB",           'purple', 'red')
]:
    ax.plot(hist.history['loss'],     label='Train', color=c1, linewidth=2)
    ax.plot(hist.history['val_loss'], label='Val',   color=c2, linewidth=2)
    ax.set_title(f"{title} — Loss MSE")
    ax.legend()
    ax.grid(alpha=0.3)
plt.tight_layout()
fig.savefig(PLOT_CONVERGENCE, dpi=100)
plt.close(fig)

# ── Graphique PCA 2D ─────────────────────────────────────────────
if n_anom > 5:
    pca   = PCA(n_components=2, random_state=RANDOM_STATE)
    X_pca = pca.fit_transform(X_test_std)
    fig2, ax2 = plt.subplots(figsize=(11, 7))
    mn = df_result["is_anomaly"] == 0
    ax2.scatter(X_pca[mn, 0], X_pca[mn, 1],
                c='lightgrey', s=4, alpha=0.3, label='Normal')
    pal = sns.color_palette("tab10", anomalies["Anomaly_type"].nunique())
    for i, atype in enumerate(anomalies["Anomaly_type"].unique()):
        ix = np.where(
            (df_result["is_anomaly"] == 1) &
            (df_result["Anomaly_type"] == atype)
        )[0]
        ax2.scatter(X_pca[ix, 0], X_pca[ix, 1],
                    c=[pal[i]], s=25, alpha=0.85, label=atype)
    ax2.set_title(
        f"PCA 2D DB — PC1={pca.explained_variance_ratio_[0]*100:.1f}% "
        f"| PC2={pca.explained_variance_ratio_[1]*100:.1f}%"
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
top_cols = [c for c in ["Event_id", "Timestamp", "Db_instance", "Db_user"] if c in anomalies.columns]
top_cols += ["Query_type", "Anomaly_type", "Risk", "composite_score", "ensemble_votes"]
top20 = anomalies.sort_values(["Risk", "composite_score"], ascending=False).head(20)
print("\n  TOP 20 ANOMALIES DB :")
print(top20[[c for c in top_cols if c in top20.columns]].to_string(index=False))


# ================================================================
# EXPORT CSV  →  DB_info/
# ================================================================
print("\n" + "=" * 65)
print("EXPORT DES RESULTATS — CSV  →  DB_info/")
print("=" * 65)

exp_cols = (list(df_test.columns)
            + ["is_anomaly", "Anomaly_type", "Risk", "composite_score",
               "IF_score", "AE_score", "LSTM_score",
               "ensemble_votes", "IF_anomaly", "AE_anomaly", "LSTM_anomaly"])
exp_cols = [c for c in exp_cols if c in df_result.columns]

# ── Detected_DB_Anomalies.csv  (tous les logs annotes)
df_result[exp_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

# ── Detected_DB_Anomalies_anomalies_only.csv  (anomalies uniquement)
anom_path = os.path.join(OUTPUT_DIR, "Detected_DB_Anomalies_anomalies_only.csv")
anomalies[exp_cols].sort_values(
    ["Risk", "composite_score"], ascending=False
).to_csv(anom_path, index=False, encoding="utf-8-sig")

print(f"  OK {OUTPUT_PATH}")
print(f"  OK {anom_path}")


# ================================================================
# EXPORT MONGODB
# ================================================================
print("\n" + "=" * 65)
print("EXPORT MONGODB — Detected_DB_Anomalies.csv")
print("=" * 65)

def _to_native(v):
    if isinstance(v, (np.integer,)):  return int(v)
    if isinstance(v, (np.floating,)): return None if (v != v) else float(v)
    if isinstance(v, (np.bool_,)):    return bool(v)
    return v


def save_db_anomalies_to_mongo(df: pd.DataFrame, run_ts: str) -> None:
    """
    Enregistre dans MongoDB le contenu de Detected_DB_Anomalies.csv.
    Upsert par Event_id si la colonne existe, insert sinon.
    Non bloquant — une erreur MongoDB n'arrête pas le pipeline.
    """
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

        docs = [
            {k: _to_native(v) for k, v in row.items()}
            for row in df_clean.to_dict(orient="records")
        ]

        has_event_id = "Event_id" in df.columns

        if has_event_id:
            operations = [
                UpdateOne({"Event_id": doc["Event_id"]}, {"$set": doc}, upsert=True)
                for doc in docs
            ]
            res = col.bulk_write(operations, ordered=False)
            print(f"  OK upsert  : {res.upserted_count} inseres | {res.modified_count} mis a jour")
        else:
            deleted = col.delete_many({"pipeline_run_at": run_ts}).deleted_count
            if deleted:
                print(f"  Anciens docs du meme run supprimes : {deleted}")
            res = col.insert_many(docs, ordered=False)
            print(f"  OK insert  : {len(res.inserted_ids):,} documents inseres")

        col.create_index("is_anomaly")
        col.create_index("Anomaly_type")
        col.create_index("Risk")
        col.create_index("pipeline_run_at")
        if has_event_id:
            col.create_index("Event_id", unique=True, sparse=True)

        client.close()
        print("  OK index crees / verifies")

    except Exception as exc:
        print(f"  ERREUR MongoDB : {exc}")
        print("  Le pipeline continue — les CSV ont bien ete sauvegardes.")


run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
save_db_anomalies_to_mongo(df_result[exp_cols], run_timestamp)


# ================================================================
# RESUME FINAL
# ================================================================
print("\n" + "=" * 65)
print(f"  TERMINE — Anomalies : {n_anom:,} ({rate:.1f}%) | Critiques : {crit}")
print(f"  Run timestamp       : {run_timestamp}")
print(f"  Fichiers dans       : {OUTPUT_DIR}")
print("=" * 65)