import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css"; // Réutilise le même CSS que le pipeline Firewall

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline Database
   Toutes les routes utilisent le préfixe /database/
═══════════════════════════════════════════════════════════ */
const DB_API = {
  UPLOAD_CSV : "/database/upload-test-csv",
  CSV_INFO   : "/database/test-csv-info",
  RUN        : "/database/run",
  STATUS     : "/database/status",
  RESULTS    : "/database/results",
  DOWNLOAD   : "/database/download",
  DOWNLOAD_A : "/database/download/anomalies",
};

/* ═══════════════════════════════════════════════════════════
   DONNÉES CRISP-DM — Pipeline Base de Données
═══════════════════════════════════════════════════════════ */
const CRISP_PHASES = [
  {
    num: "01",
    color: "#1e3a5f",
    bgLight: "#e8f0fb",
    title: "Business Understanding",
    sub: "Objectifs métier & contraintes DB",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Détecter automatiquement les comportements anormaux dans les journaux de base de données : requêtes lentes, deadlocks, extractions massives, saturation ressources — pour prévenir les incidents de performance et les fuites de données.",
    sections: [
      {
        label: "Objectif principal",
        type: "text",
        content:
          "Détection non supervisée d'anomalies DB — Isolation Forest + Autoencoder Dense + LSTM Autoencoder avec vote d'ensemble.",
      },
      {
        label: "Sorties attendues",
        type: "pills",
        items: [
          { label: "is_anomaly", cls: "crp-pill-blue" },
          { label: "Anomaly_type", cls: "crp-pill-blue" },
          { label: "Risk (0–10)", cls: "crp-pill-blue" },
          { label: "composite_score", cls: "crp-pill-blue" },
          { label: "ensemble_votes", cls: "crp-pill-blue" },
        ],
      },
      {
        label: "Seuils configurés",
        type: "pills",
        items: [
          { label: "VOTE_THRESHOLD = 1", cls: "crp-pill-gray" },
          { label: "N_SIGMA_AE = 1.5", cls: "crp-pill-gray" },
          { label: "N_SIGMA_LSTM = 1.5", cls: "crp-pill-gray" },
          { label: "IF contamination = auto", cls: "crp-pill-gray" },
          { label: "n_estimators = 300", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Persistance",
        type: "output",
        items: [
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_db_anomalies" },
          { icon: "📄", name: "CSV", desc: "DB_info/Detected_DB_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG", desc: "DB_info/plot_db_*.png" },
        ],
      },
    ],
  },
  {
    num: "02",
    color: "#065f46",
    bgLight: "#d1fae5",
    title: "Data Understanding",
    sub: "Exploration & distributions DB",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description:
      "Chargement des datasets train/test, vérification des valeurs nulles, visualisation des distributions des 17 features de monitoring de base de données.",
    sections: [
      {
        label: "Fichiers sources",
        type: "output",
        items: [
          { icon: "📂", name: "BasedeDonnees.csv", desc: "Entraînement" },
          { icon: "📂", name: "BasedeDonneestest.csv", desc: "Test (uploadable)" },
        ],
      },
      {
        label: "17 features analysées",
        type: "pills",
        items: [
          { label: "Rows_returned", cls: "crp-pill-teal" },
          { label: "Rows_modified", cls: "crp-pill-teal" },
          { label: "Execution_time_ms", cls: "crp-pill-teal" },
          { label: "Cpu_db_usage_percent", cls: "crp-pill-teal" },
          { label: "Memory_db_usage_percent", cls: "crp-pill-teal" },
          { label: "Lock_wait_time_ms", cls: "crp-pill-teal" },
          { label: "Deadlock_flag", cls: "crp-pill-teal" },
          { label: "Full_table_scan_flag", cls: "crp-pill-teal" },
          { label: "Index_usage_flag", cls: "crp-pill-teal" },
          { label: "Active_sessions", cls: "crp-pill-teal" },
          { label: "Connection_pool_usage_percent", cls: "crp-pill-teal" },
          { label: "Transaction_log_growth_mb", cls: "crp-pill-teal" },
          { label: "+ 5 autres", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Colonnes catégorielles",
        type: "pills",
        items: [
          { label: "Db_instance", cls: "crp-pill-purple" },
          { label: "Db_user", cls: "crp-pill-purple" },
          { label: "Query_type", cls: "crp-pill-purple" },
          { label: "Table_name", cls: "crp-pill-purple" },
        ],
      },
      {
        label: "Sortie graphique",
        type: "output",
        items: [
          { icon: "📊", name: "DB_info/plot_db_distributions.png", desc: "Histogrammes 3×4 features numériques" },
        ],
      },
    ],
  },
  {
    num: "03",
    color: "#5b21b6",
    bgLight: "#ede9fe",
    title: "Data Preparation",
    sub: "Encodage, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description:
      "LabelEncoder sur les 4 colonnes catégorielles avec gestion des valeurs inconnues en test. Double scaling : StandardScaler (IF/AE) et MinMaxScaler (LSTM). Séquences temporelles par fenêtre glissante.",
    sections: [
      {
        label: "Colonnes encodées (LabelEncoder)",
        type: "pills",
        items: [
          { label: "Db_instance", cls: "crp-pill-purple" },
          { label: "Db_user", cls: "crp-pill-purple" },
          { label: "Query_type", cls: "crp-pill-purple" },
          { label: "Table_name", cls: "crp-pill-purple" },
        ],
      },
      {
        label: "Scalers appliqués",
        type: "output",
        items: [
          { icon: "⚖️", name: "StandardScaler", desc: "→ Isolation Forest & Autoencoder Dense" },
          { icon: "📐", name: "MinMaxScaler", desc: "→ LSTM Autoencoder (séquences [0, 1])" },
        ],
      },
      {
        label: "Séquences LSTM",
        type: "text",
        content:
          "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires pour l'entraînement. Padding médian sur les 4 premiers points en inférence (pas de séquence complète disponible).",
      },
    ],
  },
  {
    num: "04",
    color: "#92400e",
    bgLight: "#fef3c7",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF", cls: "crp-badge-amber" },
      { label: "AE", cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description:
      "Trois modèles non supervisés entraînés indépendamment sur les logs DB, combinés par vote pour maximiser la robustesse. La classification du type est d'abord réglementaire, puis raffinée par KMeans sur les cas ambigus.",
    sections: [
      {
        label: "Modèles",
        type: "models",
        items: [
          {
            title: "Isolation Forest",
            dot: "#1e3a5f",
            lines: [
              "n_estimators=300, max_features=0.8",
              "contamination=auto, n_jobs=-1",
              "Score : −decision_function normalisé",
            ],
          },
          {
            title: "Autoencoder Dense DB",
            dot: "#5b21b6",
            lines: [
              "Input → 128 → 32 → 128 → Output",
              "Dropout 0.1, Adam lr=2e-3, batch=512",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
          {
            title: "LSTM Autoencoder DB",
            dot: "#065f46",
            lines: [
              "LSTM(64) → RepeatVector(5) → LSTM(64)",
              "TimeDistributed Dense, window=5",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
        ],
      },
      {
        label: "Vote d'ensemble",
        type: "vote",
        items: [
          { label: "3/3 — Critique", color: "#ef4444", pct: 33 },
          { label: "2/3 — Confirmé", color: "#f59e0b", pct: 55 },
          { label: "1/3 — Incertain", color: "#64748b", pct: 80 },
        ],
        note: "Anomalie retenue si votes ≥ VOTE_THRESHOLD (1)",
      },
      {
        label: "Types d'anomalies DB détectés",
        type: "pills",
        items: [
          { label: "Deadlock", cls: "crp-pill-red" },
          { label: "Slow Query", cls: "crp-pill-red" },
          { label: "Lock Contention", cls: "crp-pill-amber" },
          { label: "Mauvais Index", cls: "crp-pill-amber" },
          { label: "Extraction massive données", cls: "crp-pill-amber" },
          { label: "Suppression logs", cls: "crp-pill-blue" },
          { label: "Saturation DB", cls: "crp-pill-blue" },
          { label: "Saturation connexions", cls: "crp-pill-blue" },
          { label: "Comportement anormal", cls: "crp-pill-gray" },
        ],
      },
    ],
  },
  {
    num: "05",
    color: "#9f1239",
    bgLight: "#fee2e2",
    title: "Evaluation",
    sub: "Métriques & visualisations DB",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description:
      "Score de risque (0–10) calculé par règles métier pondérées. Génération des courbes de convergence MSE et d'une projection PCA 2D colorée par type d'anomalie.",
    sections: [
      {
        label: "Score de risque DB — règles pondérées",
        type: "pills",
        items: [
          { label: "Deadlock_flag = 1 → +9", cls: "crp-pill-red" },
          { label: "Rows_returned > 100k → +8", cls: "crp-pill-red" },
          { label: "Transaction_log_growth > 500 → +8", cls: "crp-pill-red" },
          { label: "Execution_time > 5000ms → +7", cls: "crp-pill-amber" },
          { label: "Connection_pool > 95% → +7", cls: "crp-pill-amber" },
          { label: "Lock_wait > 2000ms → +6", cls: "crp-pill-amber" },
          { label: "CPU DB > 90% → +6", cls: "crp-pill-amber" },
          { label: "Memory DB > 90% → +6", cls: "crp-pill-amber" },
          { label: "Index_usage = 0 → +4", cls: "crp-pill-gray" },
          { label: "Full_table_scan = 1 → +3", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Graphiques générés",
        type: "output",
        items: [
          { icon: "📈", name: "DB_info/plot_db_convergence.png", desc: "Courbes MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "DB_info/plot_db_pca.png", desc: "Projection PCA 2D par type d'anomalie DB" },
        ],
      },
    ],
  },
  {
    num: "06",
    color: "#0c4a6e",
    bgLight: "#e0f2fe",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI", cls: "crp-badge-blue" },
      { label: "MongoDB", cls: "crp-badge-green" },
    ],
    description:
      "Pipeline exposé via API REST FastAPI avec préfixe /database/. Upload asynchrone, polling d'état, téléchargement des résultats. Persistance MongoDB avec upsert par Event_id et indexation complète.",
    sections: [
      {
        label: "Endpoints API — préfixe /database/",
        type: "output",
        items: [
          { icon: "⬆️", name: "POST /database/upload-test-csv", desc: "Upload données test DB" },
          { icon: "🚀", name: "POST /database/run", desc: "Lancement asynchrone (202)" },
          { icon: "📡", name: "GET /database/status", desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /database/results", desc: "Top 20 + stats DB" },
          { icon: "💾", name: "GET /database/download", desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /database/download/anomalies", desc: "Export anomalies uniquement" },
        ],
      },
      {
        label: "Dossier de sortie",
        type: "output",
        items: [
          { icon: "📁", name: "DB_info/", desc: "Isolé de Firewall_info/ — aucun conflit de fichiers" },
        ],
      },
      {
        label: "Stratégie MongoDB",
        type: "text",
        content:
          "Collection dédiée : detected_db_anomalies (séparée de detected_anomalies du pipeline Firewall). Upsert par Event_id, index sur is_anomaly / Anomaly_type / Risk / pipeline_run_at. Horodatage UTC par run.",
      },
    ],
  },
];

/* ═══════════════════════════════════════════════════════════
   COMPOSANT CRISP-DM PHASES
═══════════════════════════════════════════════════════════ */
const CrispDmSection = () => {
  const [openIndex, setOpenIndex] = useState(null);
  const toggle = (i) => setOpenIndex(openIndex === i ? null : i);

  const renderSection = (sec, idx) => {
    switch (sec.type) {
      case "text":
        return <p key={idx} className="crp-content-text">{sec.content}</p>;

      case "pills":
        return (
          <div key={idx} className="crp-items-list">
            {sec.items.map((it, j) => (
              <span key={j} className={`crp-pill ${it.cls}`}>{it.label}</span>
            ))}
          </div>
        );

      case "output":
        return (
          <div key={idx} className="crp-output-list">
            {sec.items.map((it, j) => (
              <div key={j} className="crp-output-row">
                <span className="crp-output-icon">{it.icon}</span>
                <span className="crp-output-name">{it.name}</span>
                <span className="crp-output-desc">{it.desc}</span>
              </div>
            ))}
          </div>
        );

      case "models":
        return (
          <div key={idx} className="crp-model-cards">
            {sec.items.map((m, j) => (
              <div key={j} className="crp-model-card">
                <div className="crp-model-title">
                  <span className="crp-model-dot" style={{ background: m.dot }} />
                  {m.title}
                </div>
                {m.lines.map((l, k) => (
                  <div key={k} className="crp-model-detail">{l}</div>
                ))}
              </div>
            ))}
          </div>
        );

      case "vote":
        return (
          <div key={idx} className="crp-vote-box">
            {sec.items.map((v, j) => (
              <div key={j} className="crp-vote-row">
                <span className="crp-vote-label">{v.label}</span>
                <div className="crp-vote-track">
                  <div className="crp-vote-fill"
                    style={{ width: `${v.pct}%`, background: v.color }} />
                </div>
              </div>
            ))}
            {sec.note && <p className="crp-vote-note">{sec.note}</p>}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <section className="crp-wrap">
      <div className="crp-section-header">
        <div className="crp-section-icon" style={{ background: "#1e3a5f" }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">
            Pipeline CRISP-DM — Détection d'Anomalies Base de Données
          </h3>
          <p className="crp-section-sub">
            6 phases · 3 modèles IA · Vote d'ensemble · MongoDB · Sorties dans DB_info/
          </p>
        </div>
      </div>

      <div className="crp-phases">
        {CRISP_PHASES.map((ph, i) => {
          const isOpen = openIndex === i;
          return (
            <div key={i} className={`crp-phase-card ${isOpen ? "crp-open" : ""}`}
              style={{ "--ph-color": ph.color, "--ph-bg": ph.bgLight }}>
              <div className="crp-phase-header" onClick={() => toggle(i)}
                role="button" aria-expanded={isOpen}>
                <span className="crp-phase-num"
                  style={{ background: ph.color, color: "#fff" }}>
                  {ph.num}
                </span>
                <div className="crp-phase-title-block">
                  <div className="crp-phase-title">{ph.title}</div>
                  <div className="crp-phase-sub">{ph.sub}</div>
                </div>
                <div className="crp-badges">
                  {ph.badges.map((b, j) => (
                    <span key={j} className={`crp-badge ${b.cls}`}>{b.label}</span>
                  ))}
                </div>
                <svg className="crp-chevron" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round" width="16" height="16">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
              <div className="crp-phase-body">
                <div className="crp-phase-content">
                  <p className="crp-description">{ph.description}</p>
                  {ph.sections.map((sec, si) => (
                    <div key={si} className="crp-content-section">
                      <div className="crp-content-label">{sec.label}</div>
                      {renderSection(sec, si)}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT UPLOAD — Pipeline Database
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader }) => {
  const [uploading, setUploading] = useState(false);
  const [fileInfo,  setFileInfo]  = useState(null);
  const inputRef = useRef();

  useEffect(() => { checkFileInfo(); }, []);

  const checkFileInfo = () => {
    API.get(DB_API.CSV_INFO, authHeader)
      .then((r) => { if (r.data.exists) setFileInfo(r.data); })
      .catch(() => {});
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await API.post(DB_API.UPLOAD_CSV, formData, authHeader);
      checkFileInfo();
      if (onUploaded) onUploaded();
    } catch {
      alert("Erreur lors de l'importation du fichier Database.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="pd-upload-zone" onClick={() => inputRef.current.click()}>
      <input type="file" ref={inputRef} hidden onChange={handleUpload} />
      {uploading ? (
        <div className="flex-center">
          <div className="pd-spinner" />
          <p>Chargement...</p>
        </div>
      ) : fileInfo ? (
        <p>
          ✅ Fichier détecté : <strong>{fileInfo.filename}</strong> ({fileInfo.rows} lignes)
        </p>
      ) : (
        <p>🗄️ Cliquez pour importer les journaux Base de Données (.csv)</p>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   MAPPING COULEURS — Types d'anomalies DB
═══════════════════════════════════════════════════════════ */
const DB_TYPE_COLOR_MAP = {
  "Deadlock"                    : "pd-type-red",
  "Slow Query"                  : "pd-type-red",
  "Lock Contention"             : "pd-type-amber",
  "Mauvais Index"               : "pd-type-amber",
  "Extraction massive données"  : "pd-type-amber",
  "Suppression logs"            : "pd-type-blue",
  "Saturation DB"               : "pd-type-blue",
  "Saturation connexions"       : "pd-type-blue",
  "Comportement anormal"        : "pd-type-gray",
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT PRINCIPAL — DatabasePipelineDashboard
═══════════════════════════════════════════════════════════ */
export default function DatabasePipelineDashboard() {
  const { user } = useContext(AuthContext);

  const [status,      setStatus]      = useState({ state: "idle", message: "Système prêt" });
  const [results,     setResults]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [csvReady,    setCsvReady]    = useState(false);
  const [showResults, setShowResults] = useState(false);
  const pollRef = useRef(null);

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  // Vérification initiale du CSV de test Database
  useEffect(() => {
    if (user) {
      API.get(DB_API.CSV_INFO, authHeader)
        .then((r) => setCsvReady(r.data.exists))
        .catch(() =>
          setStatus({ state: "error", message: "Service d'analyse Database hors ligne" })
        );
    }
    return () => clearTimeout(pollRef.current);
  }, [user]);

  const runPipeline = async () => {
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes Database..." });
    try {
      await API.post(DB_API.RUN, {}, authHeader);
      pollStatus();
    } catch {
      setStatus({ state: "error", message: "Échec du lancement de l'audit Database" });
      setLoading(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await API.get(DB_API.STATUS, authHeader);
      setStatus(res.data);
      if (res.data.state === "running" || res.data.state === "pending") {
        pollRef.current = setTimeout(pollStatus, 3000);
      } else if (res.data.state === "done") {
        fetchResults();
        setLoading(false);
      } else if (res.data.state === "error") {
        setLoading(false);
      }
    } catch {
      setStatus({ state: "error", message: "Perte de connexion avec le serveur" });
      setLoading(false);
    }
  };

  const fetchResults = async () => {
    try {
      const res = await API.get(DB_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats Database:", err);
    }
  };

  const downloadCSV = async (url, filename) => {
    try {
      const res = await API.get(url, { ...authHeader, responseType: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([res.data]));
      link.download = filename;
      link.click();
    } catch {
      alert("Erreur lors du téléchargement du rapport Database.");
    }
  };

  return (
    <DashboardLayout user={user}>
      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">
            Attijari <span>Audit</span> Database
          </h2>
          <p>Analyse IA des journaux de base de données — Détection d'anomalies</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "Audit Database en cours..." : "🚀 Lancer l'Analyse Database"}
          </button>
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline Database :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
      </div>

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs Base de Données</h4>
        <UploadZone onUploaded={() => setCsvReady(true)} authHeader={authHeader} />
      </section>

      {/* ── CRISP-DM ── */}
      <section className="pd-section-glass pd-section-mb">
        <CrispDmSection />
      </section>

      {/* ── Bouton Afficher les Résultats ── */}
      {results && (
        <div className="pd-results-toggle-wrap">
          <button
            className={`pd-results-toggle-btn ${showResults ? "pd-results-toggle-btn--active" : ""}`}
            onClick={() => setShowResults((prev) => !prev)}
          >
            {showResults ? "🙈 Masquer les Résultats" : "📊 Afficher les Résultats Database"}
          </button>
        </div>
      )}

      {/* ── Résultats ── */}
      {results && showResults && (
        <div className="results-animate-fade">

          {/* KPI Cards */}
          <div className="pd-stats">
            <div className="pd-stat-card">
              <div className="pd-stat-label">Requêtes Analysées</div>
              <div className="pd-stat-value">
                {results.stats?.total_processed?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card gold">
              <div className="pd-stat-label">Anomalies DB Détectées</div>
              <div className="pd-stat-value">
                {results.stats?.total_anomalies?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card red">
              <div className="pd-stat-label">Incidents Critiques</div>
              <div className="pd-stat-value">
                {results.stats?.critical_alerts?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card">
              <div className="pd-stat-label">Taux d'Anomalies</div>
              <div className="pd-stat-value">
                {results.stats?.anomaly_rate != null
                  ? `${results.stats.anomaly_rate}%`
                  : "---"}
              </div>
            </div>
          </div>

          {/* Distribution par vote */}
          {results.distributions?.by_vote && (
            <section className="pd-section-glass pd-section-mb">
              <h4 className="pd-dist-title">Distribution par vote d'ensemble</h4>
              <div className="pd-dist-grid">
                {Object.entries(results.distributions.by_vote).map(([label, count]) => (
                  <div key={label} className="pd-dist-card">
                    <div className="pd-dist-count">{count}</div>
                    <div className="pd-dist-label">{label}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Distribution par type */}
          {results.distributions?.by_type && (
            <section className="pd-section-glass pd-section-mb">
              <h4 className="pd-dist-title">Distribution par type d'anomalie DB</h4>
              <div className="pd-type-list">
                {Object.entries(results.distributions.by_type).map(([type, count]) => {
                  const cls = DB_TYPE_COLOR_MAP[type] || "pd-type-gray";
                  return (
                    <div key={type} className={`pd-type-pill ${cls}`}>
                      {type} — {count}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Top 20 */}
          <div className="table-container-glass">
            <div className="pd-panel-head">TOP 20 DES INCIDENTS DATABASE IDENTIFIÉS</div>
            <table className="attijari-table-modern">
              <thead>
                <tr>
                  <th>INSTANCE DB</th>
                  <th>UTILISATEUR</th>
                  <th>TYPE D'ANOMALIE</th>
                  <th className="text-center">VOTES</th>
                  <th className="text-center">SCORE DE RISQUE</th>
                </tr>
              </thead>
              <tbody>
                {results.top20.map((row, i) => (
                  <tr key={i}>
                    <td className="pd-td-src">{row.Db_instance ?? "—"}</td>
                    <td>{row.Db_user ?? "—"}</td>
                    <td>
                      <span className="pd-anomaly-tag">{row.Anomaly_type}</span>
                    </td>
                    <td className="text-center">
                      <span className="pd-votes">{row.ensemble_votes}/3</span>
                    </td>
                    <td className="text-center">
                      <span className={`status-dot-pill ${row.Risk >= 8 ? "pd-risk-high" : "active"}`}>
                        {row.Risk}/10
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Téléchargements */}
          <div className="pd-download-row">
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(DB_API.DOWNLOAD, "Rapport_Audit_Database_Attijari.csv")}
            >
              📥 Télécharger le rapport complet (.CSV)
            </button>
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(DB_API.DOWNLOAD_A, "Anomalies_Database_Attijari.csv")}
            >
              ⚠️ Télécharger les anomalies uniquement (.CSV)
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}