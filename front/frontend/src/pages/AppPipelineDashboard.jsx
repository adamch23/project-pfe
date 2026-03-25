import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css";

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline Logs Applicatifs
   Toutes les routes utilisent le préfixe /app/
═══════════════════════════════════════════════════════════ */
const APP_API = {
  UPLOAD_CSV : "/app/upload-test-csv",
  CSV_INFO   : "/app/test-csv-info",
  RUN        : "/app/run",
  STATUS     : "/app/status",
  RESULTS    : "/app/results",
  DOWNLOAD   : "/app/download",
  DOWNLOAD_A : "/app/download/anomalies",
};

/* ═══════════════════════════════════════════════════════════
   DONNÉES CRISP-DM — Pipeline Logs Applicatifs
═══════════════════════════════════════════════════════════ */
const CRISP_PHASES = [
  {
    num: "01",
    color: "#3a0ca3",
    bgLight: "#ede9fe",
    title: "Business Understanding",
    sub: "Objectifs métier & contraintes applicatives",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Détecter automatiquement les comportements anormaux dans les logs applicatifs : dégradations de performance, timeouts, pics de transactions, erreurs applicatives et comportements utilisateurs suspects — pour assurer la disponibilité et la qualité de service.",
    sections: [
      {
        label: "Objectif principal",
        type: "text",
        content:
          "Détection non supervisée d'anomalies applicatives — Isolation Forest + Autoencoder Dense + LSTM Autoencoder avec vote d'ensemble sur 21 features (12 numériques + 9 catégorielles encodées).",
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
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_app_anomalies" },
          { icon: "📄", name: "CSV", desc: "App_info/Detected_App_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG", desc: "App_info/plot_app_*.png" },
        ],
      },
    ],
  },
  {
    num: "02",
    color: "#480ca8",
    bgLight: "#f3e8ff",
    title: "Data Understanding",
    sub: "Exploration & distributions applicatives",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description:
      "Chargement des datasets train/test, analyse des valeurs nulles et visualisation des distributions des 12 métriques de performance applicative clés.",
    sections: [
      {
        label: "Fichiers sources",
        type: "output",
        items: [
          { icon: "📂", name: "LogsApplicatifs.csv", desc: "Entraînement" },
          { icon: "📂", name: "Logs_Applicatifs_test.csv", desc: "Test (uploadable)" },
        ],
      },
      {
        label: "Features numériques (12)",
        type: "pills",
        items: [
          { label: "Response_time_ms", cls: "crp-pill-purple" },
          { label: "Db_query_time_ms", cls: "crp-pill-purple" },
          { label: "Cpu_usage_percent", cls: "crp-pill-purple" },
          { label: "Memory_usage_percent", cls: "crp-pill-purple" },
          { label: "Thread_pool_usage_percent", cls: "crp-pill-purple" },
          { label: "Db_connection_pool_usage", cls: "crp-pill-purple" },
          { label: "Retry_count", cls: "crp-pill-purple" },
          { label: "Active_users_current", cls: "crp-pill-purple" },
          { label: "Transactions_per_minute", cls: "crp-pill-purple" },
          { label: "Cache_hit_ratio", cls: "crp-pill-purple" },
          { label: "Payload_size_bytes", cls: "crp-pill-purple" },
          { label: "Response_size_bytes", cls: "crp-pill-purple" },
        ],
      },
      {
        label: "Colonnes catégorielles (9)",
        type: "pills",
        items: [
          { label: "Application_name", cls: "crp-pill-teal" },
          { label: "Server_instance", cls: "crp-pill-teal" },
          { label: "Environment", cls: "crp-pill-teal" },
          { label: "User_type", cls: "crp-pill-teal" },
          { label: "Endpoint", cls: "crp-pill-teal" },
          { label: "Http_method", cls: "crp-pill-teal" },
          { label: "Error_code", cls: "crp-pill-teal" },
          { label: "Config_version", cls: "crp-pill-teal" },
          { label: "Deployment_version", cls: "crp-pill-teal" },
        ],
      },
      {
        label: "Sortie graphique",
        type: "output",
        items: [
          { icon: "📊", name: "App_info/plot_app_distributions.png", desc: "Histogrammes 3×4 features numériques" },
        ],
      },
    ],
  },
  {
    num: "03",
    color: "#560bad",
    bgLight: "#ede9fe",
    title: "Data Preparation",
    sub: "Encodage, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description:
      "LabelEncoder sur les 9 colonnes catégorielles avec gestion des valeurs inconnues en test (classe 'NA' ajoutée dynamiquement). Double scaling adapté à chaque modèle.",
    sections: [
      {
        label: "Encodage LabelEncoder (9 colonnes)",
        type: "pills",
        items: [
          { label: "Application_name", cls: "crp-pill-purple" },
          { label: "Server_instance", cls: "crp-pill-purple" },
          { label: "Environment", cls: "crp-pill-purple" },
          { label: "User_type", cls: "crp-pill-purple" },
          { label: "Endpoint", cls: "crp-pill-purple" },
          { label: "Http_method", cls: "crp-pill-purple" },
          { label: "Error_code", cls: "crp-pill-purple" },
          { label: "Config_version", cls: "crp-pill-purple" },
          { label: "Deployment_version", cls: "crp-pill-purple" },
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
          "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires pour l'entraînement. Padding médian sur les 4 premiers points en inférence. Total features en entrée : 21 (12 numériques + 9 catégorielles encodées).",
      },
    ],
  },
  {
    num: "04",
    color: "#7209b7",
    bgLight: "#f3e8ff",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF", cls: "crp-badge-amber" },
      { label: "AE", cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description:
      "Trois modèles non supervisés entraînés sur les logs applicatifs. L'Autoencoder utilise une architecture 128→32→128 adaptée aux 21 features. La classification du type utilise les règles métier puis KMeans pour les cas ambigus.",
    sections: [
      {
        label: "Modèles",
        type: "models",
        items: [
          {
            title: "Isolation Forest",
            dot: "#3a0ca3",
            lines: [
              "n_estimators=300, max_features=0.8",
              "contamination=auto, n_jobs=-1",
              "Score : −decision_function normalisé",
            ],
          },
          {
            title: "Autoencoder Dense App",
            dot: "#7209b7",
            lines: [
              "Input(21) → 128 → 32 → 128 → Output(21)",
              "Dropout 0.1, Adam lr=2e-3, batch=512",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
          {
            title: "LSTM Autoencoder App",
            dot: "#560bad",
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
        label: "Types d'anomalies applicatives",
        type: "pills",
        items: [
          { label: "Pic d'erreurs applicatives", cls: "crp-pill-red" },
          { label: "Pic transaction / incohérence", cls: "crp-pill-red" },
          { label: "Timeout / lenteur DB", cls: "crp-pill-amber" },
          { label: "Dégradation performance", cls: "crp-pill-amber" },
          { label: "Mauvaise configuration pool", cls: "crp-pill-amber" },
          { label: "Comportement utilisateur anormal", cls: "crp-pill-blue" },
          { label: "Rejeux excessifs", cls: "crp-pill-blue" },
          { label: "Comportement anormal", cls: "crp-pill-gray" },
        ],
      },
    ],
  },
  {
    num: "05",
    color: "#b5179e",
    bgLight: "#fce7f3",
    title: "Evaluation",
    sub: "Métriques & visualisations applicatives",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description:
      "Score de risque (0–10) calculé par règles métier pondérées : erreur applicative et pic de transactions au plus haut. Courbes MSE de convergence et projection PCA 2D par type d'anomalie.",
    sections: [
      {
        label: "Score de risque App — règles pondérées",
        type: "pills",
        items: [
          { label: "Error_code ≠ NONE → +9", cls: "crp-pill-red" },
          { label: "Transactions_per_minute > 5000 → +8", cls: "crp-pill-red" },
          { label: "Response_time > 2000ms → +7", cls: "crp-pill-amber" },
          { label: "Db_query_time > 1000ms → +7", cls: "crp-pill-amber" },
          { label: "Thread_pool > 90% → +6", cls: "crp-pill-amber" },
          { label: "Db_connection_pool > 90% → +6", cls: "crp-pill-amber" },
          { label: "CPU > 90% → +6", cls: "crp-pill-amber" },
          { label: "Memory > 90% → +6", cls: "crp-pill-amber" },
          { label: "Active_users > 10 000 → +5", cls: "crp-pill-gray" },
          { label: "Retry_count > 5 → +4", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Graphiques générés",
        type: "output",
        items: [
          { icon: "📈", name: "App_info/plot_app_convergence.png", desc: "Courbes MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "App_info/plot_app_pca.png", desc: "Projection PCA 2D par type d'anomalie App" },
        ],
      },
    ],
  },
  {
    num: "06",
    color: "#3a0ca3",
    bgLight: "#ede9fe",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI", cls: "crp-badge-blue" },
      { label: "MongoDB", cls: "crp-badge-green" },
    ],
    description:
      "Pipeline exposé via API REST FastAPI avec préfixe /app/. Dossier de sortie App_info/ isolé des 3 autres pipelines. Collection MongoDB dédiée detected_app_anomalies.",
    sections: [
      {
        label: "Endpoints API — préfixe /app/",
        type: "output",
        items: [
          { icon: "⬆️", name: "POST /app/upload-test-csv", desc: "Upload données test applicatif" },
          { icon: "🚀", name: "POST /app/run", desc: "Lancement asynchrone (202)" },
          { icon: "📡", name: "GET /app/status", desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /app/results", desc: "Top 20 + stats applicatives" },
          { icon: "💾", name: "GET /app/download", desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /app/download/anomalies", desc: "Export anomalies uniquement" },
        ],
      },
      {
        label: "Dossier de sortie",
        type: "output",
        items: [
          { icon: "📁", name: "App_info/", desc: "Isolé de Firewall_info/, DB_info/, OS_info/" },
        ],
      },
      {
        label: "Stratégie MongoDB",
        type: "text",
        content:
          "Collection dédiée detected_app_anomalies (4ème collection, séparée des 3 autres pipelines). Upsert par Event_id si présent, index sur is_anomaly / Anomaly_type / Risk / pipeline_run_at. Horodatage UTC unique par run.",
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
        <div className="crp-section-icon" style={{ background: "#3a0ca3" }}>
          {/* Icône "code / application" */}
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">
            Pipeline CRISP-DM — Détection d'Anomalies Logs Applicatifs
          </h3>
          <p className="crp-section-sub">
            6 phases · 21 features · 3 modèles IA · Vote d'ensemble · App_info/
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
   COMPOSANT UPLOAD — Pipeline Applicatif
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader }) => {
  const [uploading, setUploading] = useState(false);
  const [fileInfo,  setFileInfo]  = useState(null);
  const inputRef = useRef();

  useEffect(() => { checkFileInfo(); }, []);

  const checkFileInfo = () => {
    API.get(APP_API.CSV_INFO, authHeader)
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
      await API.post(APP_API.UPLOAD_CSV, formData, authHeader);
      checkFileInfo();
      if (onUploaded) onUploaded();
    } catch {
      alert("Erreur lors de l'importation du fichier Logs Applicatifs.");
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
        <p>📱 Cliquez pour importer les Logs Applicatifs (.csv)</p>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   MAPPING COULEURS — Types d'anomalies applicatives
═══════════════════════════════════════════════════════════ */
const APP_TYPE_COLOR_MAP = {
  "Pic d'erreurs applicatives"        : "pd-type-red",
  "Pic transaction / incohérence"     : "pd-type-red",
  "Timeout / lenteur DB"              : "pd-type-amber",
  "Dégradation performance"           : "pd-type-amber",
  "Mauvaise configuration pool"       : "pd-type-amber",
  "Comportement utilisateur anormal"  : "pd-type-blue",
  "Rejeux excessifs"                  : "pd-type-blue",
  "Comportement anormal"              : "pd-type-gray",
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT PRINCIPAL — AppPipelineDashboard
═══════════════════════════════════════════════════════════ */
export default function AppPipelineDashboard() {
  const { user } = useContext(AuthContext);

  const [status,      setStatus]      = useState({ state: "idle", message: "Système prêt" });
  const [results,     setResults]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [csvReady,    setCsvReady]    = useState(false);
  const [showResults, setShowResults] = useState(false);
  const pollRef = useRef(null);

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  useEffect(() => {
    if (user) {
      API.get(APP_API.CSV_INFO, authHeader)
        .then((r) => setCsvReady(r.data.exists))
        .catch(() =>
          setStatus({ state: "error", message: "Service d'analyse Applicatif hors ligne" })
        );
    }
    return () => clearTimeout(pollRef.current);
  }, [user]);

  const runPipeline = async () => {
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes Applicatif..." });
    try {
      await API.post(APP_API.RUN, {}, authHeader);
      pollStatus();
    } catch {
      setStatus({ state: "error", message: "Échec du lancement de l'audit Applicatif" });
      setLoading(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await API.get(APP_API.STATUS, authHeader);
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
      const res = await API.get(APP_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats Applicatif:", err);
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
      alert("Erreur lors du téléchargement du rapport Applicatif.");
    }
  };

  return (
    <DashboardLayout user={user}>
      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">
            Attijari <span>Audit</span> Applicatif
          </h2>
          <p>Analyse IA des logs applicatifs — Détection d'anomalies de performance et d'erreurs</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "Audit Applicatif en cours..." : "🚀 Lancer l'Analyse Applicative"}
          </button>
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline Applicatif :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
      </div>

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs Applicatifs</h4>
        <UploadZone onUploaded={() => setCsvReady(true)} authHeader={authHeader} />
      </section>

      {/* ── CRISP-DM ── */}
      <section className="pd-section-glass pd-section-mb">
        <CrispDmSection />
      </section>

      {/* ── Bouton résultats ── */}
      {results && (
        <div className="pd-results-toggle-wrap">
          <button
            className={`pd-results-toggle-btn ${showResults ? "pd-results-toggle-btn--active" : ""}`}
            onClick={() => setShowResults((prev) => !prev)}
          >
            {showResults ? "🙈 Masquer les Résultats" : "📊 Afficher les Résultats Applicatifs"}
          </button>
        </div>
      )}

      {/* ── Résultats ── */}
      {results && showResults && (
        <div className="results-animate-fade">

          {/* KPI Cards */}
          <div className="pd-stats">
            <div className="pd-stat-card">
              <div className="pd-stat-label">Logs Analysés</div>
              <div className="pd-stat-value">
                {results.stats?.total_processed?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card gold">
              <div className="pd-stat-label">Anomalies Applicatives</div>
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
              <h4 className="pd-dist-title">Distribution par type d'anomalie applicative</h4>
              <div className="pd-type-list">
                {Object.entries(results.distributions.by_type).map(([type, count]) => {
                  const cls = APP_TYPE_COLOR_MAP[type] || "pd-type-gray";
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
            <div className="pd-panel-head">TOP 20 DES INCIDENTS APPLICATIFS IDENTIFIÉS</div>
            <table className="attijari-table-modern">
              <thead>
                <tr>
                  <th>APPLICATION</th>
                  <th>ENDPOINT</th>
                  <th>TYPE D'ANOMALIE</th>
                  <th className="text-center">VOTES</th>
                  <th className="text-center">SCORE DE RISQUE</th>
                </tr>
              </thead>
              <tbody>
                {results.top20.map((row, i) => (
                  <tr key={i}>
                    <td className="pd-td-src">{row.Application_name ?? "—"}</td>
                    <td>{row.Endpoint ?? "—"}</td>
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
              onClick={() => downloadCSV(APP_API.DOWNLOAD, "Rapport_Audit_Applicatif_Attijari.csv")}
            >
              📥 Télécharger le rapport complet (.CSV)
            </button>
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(APP_API.DOWNLOAD_A, "Anomalies_Applicatif_Attijari.csv")}
            >
              ⚠️ Télécharger les anomalies uniquement (.CSV)
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}