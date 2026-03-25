import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css";

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline API Logs
   Toutes les routes utilisent le préfixe /apilogs/
═══════════════════════════════════════════════════════════ */
const APILOGS_API = {
  UPLOAD_CSV : "/apilogs/upload-test-csv",
  CSV_INFO   : "/apilogs/test-csv-info",
  RUN        : "/apilogs/run",
  STATUS     : "/apilogs/status",
  RESULTS    : "/apilogs/results",
  DOWNLOAD   : "/apilogs/download",
  DOWNLOAD_A : "/apilogs/download/anomalies",
};

/* ═══════════════════════════════════════════════════════════
   DONNÉES CRISP-DM — Pipeline API Logs
═══════════════════════════════════════════════════════════ */
const CRISP_PHASES = [
  {
    num: "01",
    color: "#03045e",
    bgLight: "#caf0f8",
    title: "Business Understanding",
    sub: "Objectifs métier & surveillance API",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Détecter automatiquement les comportements anormaux dans les logs API : abus de rate limiting, erreurs backend, timeouts, explosions de trafic, endpoints défaillants et accès non autorisés — pour garantir la disponibilité et la sécurité des APIs.",
    sections: [
      {
        label: "Objectif principal",
        type: "text",
        content:
          "Détection non supervisée d'anomalies API — Isolation Forest + Autoencoder Dense + LSTM Autoencoder avec feature engineering temporel (hour, day_of_week, is_weekend, is_night) et vote d'ensemble.",
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
          { label: "n_estimators = 400", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Persistance",
        type: "output",
        items: [
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_api_anomalies" },
          { icon: "📄", name: "CSV", desc: "API_info/Detected_API_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG", desc: "API_info/plot_api_*.png" },
        ],
      },
    ],
  },
  {
    num: "02",
    color: "#0077b6",
    bgLight: "#ade8f4",
    title: "Data Understanding",
    sub: "Exploration & feature engineering temporel",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description:
      "Chargement des datasets train/test, normalisation des colonnes (strip espaces), feature engineering temporel automatique depuis le timestamp, visualisation des distributions.",
    sections: [
      {
        label: "Fichiers sources",
        type: "output",
        items: [
          { icon: "📂", name: "APILogs.csv", desc: "Entraînement" },
          { icon: "📂", name: "Testlogs.csv", desc: "Test (uploadable)" },
        ],
      },
      {
        label: "Feature engineering temporel (auto)",
        type: "pills",
        items: [
          { label: "hour (0–23)", cls: "crp-pill-teal" },
          { label: "day_of_week (0–6)", cls: "crp-pill-teal" },
          { label: "is_weekend (0/1)", cls: "crp-pill-teal" },
          { label: "is_night (0/1)", cls: "crp-pill-teal" },
        ],
      },
      {
        label: "Features numériques (16)",
        type: "pills",
        items: [
          { label: "request_size_bytes", cls: "crp-pill-blue" },
          { label: "response_size_bytes", cls: "crp-pill-blue" },
          { label: "response_time_ms", cls: "crp-pill-blue" },
          { label: "http_status_code", cls: "crp-pill-blue" },
          { label: "requests_per_minute_user", cls: "crp-pill-blue" },
          { label: "requests_per_minute_ip", cls: "crp-pill-blue" },
          { label: "concurrent_requests", cls: "crp-pill-blue" },
          { label: "cpu_usage_server_pct", cls: "crp-pill-blue" },
          { label: "memory_usage_server_pct", cls: "crp-pill-blue" },
          { label: "db_query_time_ms", cls: "crp-pill-blue" },
          { label: "rate_limit_triggered", cls: "crp-pill-blue" },
          { label: "retry_count", cls: "crp-pill-blue" },
          { label: "+ 4 temporelles", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Features catégorielles (5)",
        type: "pills",
        items: [
          { label: "api_name", cls: "crp-pill-teal" },
          { label: "http_method", cls: "crp-pill-teal" },
          { label: "client_type", cls: "crp-pill-teal" },
          { label: "error_type", cls: "crp-pill-teal" },
          { label: "authentication_type", cls: "crp-pill-teal" },
        ],
      },
      {
        label: "Sortie graphique",
        type: "output",
        items: [
          { icon: "📊", name: "API_info/plot_api_distributions.png", desc: "Histogrammes 3×4 features numériques" },
        ],
      },
    ],
  },
  {
    num: "03",
    color: "#0096c7",
    bgLight: "#caf0f8",
    title: "Data Preparation",
    sub: "Encodage robuste, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description:
      "LabelEncoder sur 5 colonnes catégorielles avec détection automatique de la valeur 'sans erreur' (NONE, NO_ERROR, OK…). Double scaling StandardScaler/MinMaxScaler. Résolution insensible à la casse pour tous les noms de colonnes.",
    sections: [
      {
        label: "Colonnes encodées (LabelEncoder)",
        type: "pills",
        items: [
          { label: "api_name", cls: "crp-pill-purple" },
          { label: "http_method", cls: "crp-pill-purple" },
          { label: "client_type", cls: "crp-pill-purple" },
          { label: "error_type", cls: "crp-pill-purple" },
          { label: "authentication_type", cls: "crp-pill-purple" },
        ],
      },
      {
        label: "Robustesse colonnes",
        type: "text",
        content:
          "Résolution insensible à la casse (_find_col) + strip espaces sur tous les noms. Valeur 'sans erreur' de error_type détectée automatiquement parmi : NONE, None, NO_ERROR, OK, NA. Fallback sur la valeur la plus fréquente du train.",
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
          "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires. Padding médian sur les 4 premiers points en inférence. Total features : 21 (16 numériques + 4 temporelles + 5 catégorielles encodées → selon colonnes disponibles).",
      },
    ],
  },
  {
    num: "04",
    color: "#0077b6",
    bgLight: "#ade8f4",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF", cls: "crp-badge-amber" },
      { label: "AE", cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description:
      "Trois modèles non supervisés entraînés sur les logs API. La classification utilise en priorité error_type décodé (TIMEOUT, BACKEND_ERROR, RATE_LIMIT) puis les seuils métriques, avec KMeans pour les cas ambigus.",
    sections: [
      {
        label: "Modèles",
        type: "models",
        items: [
          {
            title: "Isolation Forest",
            dot: "#03045e",
            lines: [
              "n_estimators=400, max_features=0.8",
              "contamination=auto, n_jobs=-1",
              "Score : −decision_function normalisé",
            ],
          },
          {
            title: "Autoencoder Dense API",
            dot: "#0077b6",
            lines: [
              "Input → 128 → 32 → 128 → Output",
              "Dropout 0.1, Adam lr=2e-3, batch=512",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
          {
            title: "LSTM Autoencoder API",
            dot: "#0096c7",
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
        label: "Types d'anomalies API détectés",
        type: "pills",
        items: [
          { label: "Erreur backend", cls: "crp-pill-red" },
          { label: "Abuse API", cls: "crp-pill-red" },
          { label: "Timeout", cls: "crp-pill-red" },
          { label: "Explosion trafic", cls: "crp-pill-amber" },
          { label: "Endpoint défaillant", cls: "crp-pill-amber" },
          { label: "Mauvaise configuration rate limit", cls: "crp-pill-amber" },
          { label: "Problème performance", cls: "crp-pill-blue" },
          { label: "Tentative accès non autorisé", cls: "crp-pill-blue" },
          { label: "Activité nocturne suspecte", cls: "crp-pill-blue" },
          { label: "Comportement anormal", cls: "crp-pill-gray" },
        ],
      },
    ],
  },
  {
    num: "05",
    color: "#023e8a",
    bgLight: "#caf0f8",
    title: "Evaluation",
    sub: "Métriques & visualisations API",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description:
      "Score de risque (0–10) calculé par règles métier pondérées sur http_status_code, response_time_ms, requests_per_minute_ip, CPU, retry_count et activité nocturne. Courbes MSE et PCA 2D.",
    sections: [
      {
        label: "Score de risque API — règles pondérées",
        type: "pills",
        items: [
          { label: "http_status_code ≥ 500 → +4", cls: "crp-pill-red" },
          { label: "http_status_code = 429 → +3", cls: "crp-pill-red" },
          { label: "response_time_ms > 3000 → +3", cls: "crp-pill-red" },
          { label: "requests_per_minute_ip > 1000 → +3", cls: "crp-pill-amber" },
          { label: "cpu_usage_server_pct > 95% → +3", cls: "crp-pill-amber" },
          { label: "response_time_ms > 2000 → +2", cls: "crp-pill-amber" },
          { label: "requests_per_minute_ip > 500 → +2", cls: "crp-pill-amber" },
          { label: "cpu_usage_server_pct > 85% → +2", cls: "crp-pill-amber" },
          { label: "memory_usage_server_pct > 90% → +2", cls: "crp-pill-gray" },
          { label: "retry_count ≥ 5 → +2", cls: "crp-pill-gray" },
          { label: "is_night + rpm_user > 150 → +2", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Graphiques générés",
        type: "output",
        items: [
          { icon: "📈", name: "API_info/plot_api_convergence.png", desc: "Courbes MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "API_info/plot_api_pca.png", desc: "Projection PCA 2D par type d'anomalie API" },
        ],
      },
    ],
  },
  {
    num: "06",
    color: "#0077b6",
    bgLight: "#ade8f4",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI", cls: "crp-badge-blue" },
      { label: "MongoDB", cls: "crp-badge-green" },
    ],
    description:
      "Pipeline exposé via API REST FastAPI avec préfixe /apilogs/. Dossier API_info/ isolé des 4 autres pipelines. Collection MongoDB dédiée detected_api_anomalies.",
    sections: [
      {
        label: "Endpoints API — préfixe /apilogs/",
        type: "output",
        items: [
          { icon: "⬆️", name: "POST /apilogs/upload-test-csv", desc: "Upload Testlogs.csv" },
          { icon: "🚀", name: "POST /apilogs/run", desc: "Lancement asynchrone (202)" },
          { icon: "📡", name: "GET /apilogs/status", desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /apilogs/results", desc: "Top 20 + stats API" },
          { icon: "💾", name: "GET /apilogs/download", desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /apilogs/download/anomalies", desc: "Export anomalies uniquement" },
        ],
      },
      {
        label: "Dossier de sortie",
        type: "output",
        items: [
          { icon: "📁", name: "API_info/", desc: "Isolé de Firewall_info/, DB_info/, OS_info/, App_info/" },
        ],
      },
      {
        label: "Stratégie MongoDB",
        type: "text",
        content:
          "Collection dédiée detected_api_anomalies (5ème collection, séparée des 4 autres). Upsert par event_id, index sur is_anomaly / Anomaly_type / Risk / pipeline_run_at. Horodatage UTC unique par run.",
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
        <div className="crp-section-icon" style={{ background: "#03045e" }}>
          {/* Icône API / réseau */}
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <path d="M21 2H3v16h5v4l4-4h9V2z" />
            <line x1="8" y1="10" x2="16" y2="10" />
            <line x1="8" y1="6" x2="16" y2="6" />
            <line x1="8" y1="14" x2="12" y2="14" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">
            Pipeline CRISP-DM — Détection d'Anomalies API Logs
          </h3>
          <p className="crp-section-sub">
            6 phases · Feature engineering temporel · 3 modèles IA · Vote d'ensemble · API_info/
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
                <span className="crp-phase-num" style={{ background: ph.color, color: "#fff" }}>
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
   COMPOSANT UPLOAD — Pipeline API Logs
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader }) => {
  const [uploading, setUploading] = useState(false);
  const [fileInfo,  setFileInfo]  = useState(null);
  const inputRef = useRef();

  useEffect(() => { checkFileInfo(); }, []);

  const checkFileInfo = () => {
    API.get(APILOGS_API.CSV_INFO, authHeader)
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
      await API.post(APILOGS_API.UPLOAD_CSV, formData, authHeader);
      checkFileInfo();
      if (onUploaded) onUploaded();
    } catch {
      alert("Erreur lors de l'importation du fichier API Logs.");
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
        <p>🔌 Cliquez pour importer les logs API (.csv)</p>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   MAPPING COULEURS — Types d'anomalies API
═══════════════════════════════════════════════════════════ */
const API_TYPE_COLOR_MAP = {
  "Erreur backend"                    : "pd-type-red",
  "Abuse API"                         : "pd-type-red",
  "Timeout"                           : "pd-type-red",
  "Explosion trafic"                  : "pd-type-amber",
  "Endpoint défaillant"               : "pd-type-amber",
  "Mauvaise configuration rate limit" : "pd-type-amber",
  "Problème performance"              : "pd-type-blue",
  "Tentative accès non autorisé"      : "pd-type-blue",
  "Activité nocturne suspecte"        : "pd-type-blue",
  "Comportement anormal"              : "pd-type-gray",
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT PRINCIPAL — APILogsPipelineDashboard
═══════════════════════════════════════════════════════════ */
export default function APILogsPipelineDashboard() {
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
      API.get(APILOGS_API.CSV_INFO, authHeader)
        .then((r) => setCsvReady(r.data.exists))
        .catch(() =>
          setStatus({ state: "error", message: "Service d'analyse API Logs hors ligne" })
        );
    }
    return () => clearTimeout(pollRef.current);
  }, [user]);

  const runPipeline = async () => {
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes API Logs..." });
    try {
      await API.post(APILOGS_API.RUN, {}, authHeader);
      pollStatus();
    } catch {
      setStatus({ state: "error", message: "Échec du lancement de l'audit API Logs" });
      setLoading(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await API.get(APILOGS_API.STATUS, authHeader);
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
      const res = await API.get(APILOGS_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats API Logs:", err);
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
      alert("Erreur lors du téléchargement du rapport API Logs.");
    }
  };

  return (
    <DashboardLayout user={user}>
      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">
            Attijari <span>Audit</span> API Logs
          </h2>
          <p>Analyse IA des journaux API — Détection d'abus, timeouts et anomalies de trafic</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "Audit API en cours..." : "🚀 Lancer l'Analyse API Logs"}
          </button>
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline API Logs :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
      </div>

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs API</h4>
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
            {showResults ? "🙈 Masquer les Résultats" : "📊 Afficher les Résultats API Logs"}
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
              <div className="pd-stat-label">Anomalies API Détectées</div>
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
              <h4 className="pd-dist-title">Distribution par type d'anomalie API</h4>
              <div className="pd-type-list">
                {Object.entries(results.distributions.by_type).map(([type, count]) => {
                  const cls = API_TYPE_COLOR_MAP[type] || "pd-type-gray";
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
            <div className="pd-panel-head">TOP 20 DES INCIDENTS API IDENTIFIÉS</div>
            <table className="attijari-table-modern">
              <thead>
                <tr>
                  <th>API NAME</th>
                  <th>ENDPOINT</th>
                  <th>TYPE D'ANOMALIE</th>
                  <th className="text-center">VOTES</th>
                  <th className="text-center">SCORE DE RISQUE</th>
                </tr>
              </thead>
              <tbody>
                {results.top20.map((row, i) => (
                  <tr key={i}>
                    <td className="pd-td-src">{row.api_name ?? "—"}</td>
                    <td>{row.endpoint ?? "—"}</td>
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
              onClick={() => downloadCSV(APILOGS_API.DOWNLOAD, "Rapport_Audit_API_Logs_Attijari.csv")}
            >
              📥 Télécharger le rapport complet (.CSV)
            </button>
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(APILOGS_API.DOWNLOAD_A, "Anomalies_API_Logs_Attijari.csv")}
            >
              ⚠️ Télécharger les anomalies uniquement (.CSV)
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}