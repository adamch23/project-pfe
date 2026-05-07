import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css";

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline API Logs
═══════════════════════════════════════════════════════════ */
const APILOGS_API = {
  UPLOAD_CSV : "/apilogs/upload-test-csv",
  CSV_INFO   : "/apilogs/test-csv-info",
  RUN        : "/apilogs/run",
  RESET      : "/apilogs/reset",
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
    num: "01", color: "#03045e", bgLight: "#caf0f8",
    title: "Business Understanding",
    sub: "Objectifs métier & surveillance API",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Détecter automatiquement les comportements anormaux dans les logs API : abus de rate limiting, erreurs backend, timeouts, explosions de trafic, endpoints défaillants et accès non autorisés — pour garantir la disponibilité et la sécurité des APIs.",
    sections: [
      { label: "Objectif principal", type: "text",
        content: "Détection non supervisée d'anomalies API — Isolation Forest + Autoencoder Dense + LSTM Autoencoder avec feature engineering temporel (hour, day_of_week, is_weekend, is_night) et vote d'ensemble." },
      { label: "Sorties attendues", type: "pills",
        items: [
          { label: "is_anomaly",      cls: "crp-pill-blue" },
          { label: "Anomaly_type",    cls: "crp-pill-blue" },
          { label: "Risk (0–10)",     cls: "crp-pill-blue" },
          { label: "composite_score", cls: "crp-pill-blue" },
          { label: "ensemble_votes",  cls: "crp-pill-blue" },
        ] },
      { label: "Seuils configurés", type: "pills",
        items: [
          { label: "VOTE_THRESHOLD = 1",      cls: "crp-pill-gray" },
          { label: "N_SIGMA_AE = 1.5",        cls: "crp-pill-gray" },
          { label: "N_SIGMA_LSTM = 1.5",      cls: "crp-pill-gray" },
          { label: "IF contamination = auto", cls: "crp-pill-gray" },
          { label: "n_estimators = 400",      cls: "crp-pill-gray" },
        ] },
      { label: "Persistance", type: "output",
        items: [
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_api_anomalies" },
          { icon: "📄", name: "CSV",     desc: "API_info/Detected_API_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG",     desc: "API_info/plot_api_*.png" },
        ] },
    ],
  },
  {
    num: "02", color: "#0077b6", bgLight: "#ade8f4",
    title: "Data Understanding",
    sub: "Exploration & feature engineering temporel",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description: "Chargement des datasets train/test, normalisation des colonnes (strip espaces), feature engineering temporel automatique depuis le timestamp, visualisation des distributions.",
    sections: [
      { label: "Fichiers sources", type: "output",
        items: [
          { icon: "📂", name: "APILogs.csv",  desc: "Entraînement" },
          { icon: "📂", name: "Testlogs.csv", desc: "Test (uploadable)" },
        ] },
      { label: "Feature engineering temporel (auto)", type: "pills",
        items: [
          { label: "hour (0–23)",       cls: "crp-pill-teal" },
          { label: "day_of_week (0–6)", cls: "crp-pill-teal" },
          { label: "is_weekend (0/1)",  cls: "crp-pill-teal" },
          { label: "is_night (0/1)",    cls: "crp-pill-teal" },
        ] },
      { label: "Features numériques (16)", type: "pills",
        items: [
          { label: "request_size_bytes",       cls: "crp-pill-blue" },
          { label: "response_size_bytes",      cls: "crp-pill-blue" },
          { label: "response_time_ms",         cls: "crp-pill-blue" },
          { label: "http_status_code",         cls: "crp-pill-blue" },
          { label: "requests_per_minute_user", cls: "crp-pill-blue" },
          { label: "requests_per_minute_ip",   cls: "crp-pill-blue" },
          { label: "concurrent_requests",      cls: "crp-pill-blue" },
          { label: "cpu_usage_server_pct",     cls: "crp-pill-blue" },
          { label: "memory_usage_server_pct",  cls: "crp-pill-blue" },
          { label: "db_query_time_ms",         cls: "crp-pill-blue" },
          { label: "rate_limit_triggered",     cls: "crp-pill-blue" },
          { label: "retry_count",              cls: "crp-pill-blue" },
          { label: "+ 4 temporelles",          cls: "crp-pill-gray" },
        ] },
      { label: "Features catégorielles (5)", type: "pills",
        items: [
          { label: "api_name",            cls: "crp-pill-teal" },
          { label: "http_method",         cls: "crp-pill-teal" },
          { label: "client_type",         cls: "crp-pill-teal" },
          { label: "error_type",          cls: "crp-pill-teal" },
          { label: "authentication_type", cls: "crp-pill-teal" },
        ] },
      { label: "Sortie graphique", type: "output",
        items: [{ icon: "📊", name: "API_info/plot_api_distributions.png", desc: "Histogrammes 3×4 features numériques" }] },
    ],
  },
  {
    num: "03", color: "#0096c7", bgLight: "#caf0f8",
    title: "Data Preparation",
    sub: "Encodage robuste, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description: "LabelEncoder sur 5 colonnes catégorielles avec détection automatique de la valeur 'sans erreur' (NONE, NO_ERROR, OK…). Double scaling StandardScaler/MinMaxScaler. Résolution insensible à la casse pour tous les noms de colonnes.",
    sections: [
      { label: "Colonnes encodées (LabelEncoder)", type: "pills",
        items: [
          { label: "api_name",            cls: "crp-pill-purple" },
          { label: "http_method",         cls: "crp-pill-purple" },
          { label: "client_type",         cls: "crp-pill-purple" },
          { label: "error_type",          cls: "crp-pill-purple" },
          { label: "authentication_type", cls: "crp-pill-purple" },
        ] },
      { label: "Robustesse colonnes", type: "text",
        content: "Résolution insensible à la casse (_find_col) + strip espaces sur tous les noms. Valeur 'sans erreur' de error_type détectée automatiquement parmi : NONE, None, NO_ERROR, OK, NA. Fallback sur la valeur la plus fréquente du train." },
      { label: "Scalers appliqués", type: "output",
        items: [
          { icon: "⚖️", name: "StandardScaler", desc: "→ Isolation Forest & Autoencoder Dense" },
          { icon: "📐", name: "MinMaxScaler",    desc: "→ LSTM Autoencoder (séquences [0, 1])" },
        ] },
      { label: "Séquences LSTM", type: "text",
        content: "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires. Padding médian sur les 4 premiers points en inférence." },
    ],
  },
  {
    num: "04", color: "#0077b6", bgLight: "#ade8f4",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF",   cls: "crp-badge-amber" },
      { label: "AE",   cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description: "Trois modèles non supervisés entraînés sur les logs API. La classification utilise en priorité error_type décodé puis les seuils métriques, avec KMeans pour les cas ambigus.",
    sections: [
      { label: "Modèles", type: "models",
        items: [
          { title: "Isolation Forest",     dot: "#03045e", lines: ["n_estimators=400, max_features=0.8", "contamination=auto, n_jobs=-1", "Score : −decision_function normalisé"] },
          { title: "Autoencoder Dense API",dot: "#0077b6", lines: ["Input → 128 → 32 → 128 → Output", "Dropout 0.1, Adam lr=2e-3, batch=512", "Seuil : μ + 1.5σ sur MSE train"] },
          { title: "LSTM Autoencoder API", dot: "#0096c7", lines: ["LSTM(64) → RepeatVector(5) → LSTM(64)", "TimeDistributed Dense, window=5", "Seuil : μ + 1.5σ sur MSE train"] },
        ] },
      { label: "Vote d'ensemble", type: "vote",
        items: [
          { label: "3/3 — Critique",  color: "#ef4444", pct: 33 },
          { label: "2/3 — Confirmé",  color: "#f59e0b", pct: 55 },
          { label: "1/3 — Incertain", color: "#64748b", pct: 80 },
        ],
        note: "Anomalie retenue si votes ≥ VOTE_THRESHOLD (1)" },
      { label: "Types d'anomalies API détectés", type: "pills",
        items: [
          { label: "Erreur backend",                    cls: "crp-pill-red"   },
          { label: "Abuse API",                         cls: "crp-pill-red"   },
          { label: "Timeout",                           cls: "crp-pill-red"   },
          { label: "Explosion trafic",                  cls: "crp-pill-amber" },
          { label: "Endpoint défaillant",               cls: "crp-pill-amber" },
          { label: "Mauvaise configuration rate limit", cls: "crp-pill-amber" },
          { label: "Problème performance",              cls: "crp-pill-blue"  },
          { label: "Tentative accès non autorisé",      cls: "crp-pill-blue"  },
          { label: "Activité nocturne suspecte",        cls: "crp-pill-blue"  },
          { label: "Comportement anormal",              cls: "crp-pill-gray"  },
        ] },
    ],
  },
  {
    num: "05", color: "#023e8a", bgLight: "#caf0f8",
    title: "Evaluation",
    sub: "Métriques & visualisations API",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description: "Score de risque (0–10) calculé par règles métier pondérées sur http_status_code, response_time_ms, requests_per_minute_ip, CPU, retry_count et activité nocturne.",
    sections: [
      { label: "Score de risque API — règles pondérées", type: "pills",
        items: [
          { label: "http_status_code ≥ 500 → +4",       cls: "crp-pill-red"   },
          { label: "http_status_code = 429 → +3",        cls: "crp-pill-red"   },
          { label: "response_time_ms > 3000 → +3",       cls: "crp-pill-red"   },
          { label: "requests_per_minute_ip > 1000 → +3", cls: "crp-pill-amber" },
          { label: "cpu_usage_server_pct > 95% → +3",    cls: "crp-pill-amber" },
          { label: "response_time_ms > 2000 → +2",       cls: "crp-pill-amber" },
          { label: "requests_per_minute_ip > 500 → +2",  cls: "crp-pill-amber" },
          { label: "cpu_usage_server_pct > 85% → +2",    cls: "crp-pill-amber" },
          { label: "memory_usage_server_pct > 90% → +2", cls: "crp-pill-gray"  },
          { label: "retry_count ≥ 5 → +2",               cls: "crp-pill-gray"  },
          { label: "is_night + rpm_user > 150 → +2",     cls: "crp-pill-gray"  },
        ] },
      { label: "Graphiques générés", type: "output",
        items: [
          { icon: "📈", name: "API_info/plot_api_convergence.png", desc: "Courbes MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "API_info/plot_api_pca.png",         desc: "Projection PCA 2D par type d'anomalie API" },
        ] },
    ],
  },
  {
    num: "06", color: "#0077b6", bgLight: "#ade8f4",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI",  cls: "crp-badge-blue"  },
      { label: "MongoDB",  cls: "crp-badge-green" },
    ],
    description: "Pipeline exposé via API REST FastAPI avec préfixe /apilogs/. Dossier API_info/ isolé des 4 autres pipelines. Collection MongoDB dédiée detected_api_anomalies.",
    sections: [
      { label: "Endpoints API — préfixe /apilogs/", type: "output",
        items: [
          { icon: "⬆️", name: "POST /apilogs/upload-test-csv",   desc: "Upload Testlogs.csv" },
          { icon: "🚀", name: "POST /apilogs/run",               desc: "Lancement asynchrone (202)" },
          { icon: "🔄", name: "POST /apilogs/reset",             desc: "Réinitialiser si bloqué" },
          { icon: "📡", name: "GET /apilogs/status",             desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /apilogs/results",            desc: "Top 20 + stats API" },
          { icon: "💾", name: "GET /apilogs/download",           desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /apilogs/download/anomalies", desc: "Export anomalies uniquement" },
        ] },
      { label: "Dossier de sortie", type: "output",
        items: [{ icon: "📁", name: "API_info/", desc: "Isolé de Firewall_info/, DB_info/, OS_info/, App_info/" }] },
      { label: "Stratégie MongoDB", type: "text",
        content: "Collection dédiée detected_api_anomalies (5ème collection, séparée des 4 autres). Upsert par event_id, index sur is_anomaly / Anomaly_type / Risk / pipeline_run_at." },
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
                  <div className="crp-vote-fill" style={{ width: `${v.pct}%`, background: v.color }} />
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
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <path d="M21 2H3v16h5v4l4-4h9V2z" />
            <line x1="8" y1="10" x2="16" y2="10" />
            <line x1="8" y1="6"  x2="16" y2="6"  />
            <line x1="8" y1="14" x2="12" y2="14" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">Pipeline CRISP-DM — Détection d'Anomalies API Logs</h3>
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
   COMPOSANT UPLOAD — AVEC DÉCOMPTE 1 SECONDE
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader, onFileInfoUpdate }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [estimatedTimeDisplay, setEstimatedTimeDisplay] = useState(null);
  const [fileInfo, setFileInfo] = useState(null);
  const [fileRows, setFileRows] = useState(0);
  const inputRef = useRef();
  const progressIntervalRef = useRef(null);
  const countdownIntervalRef = useRef(null);

  // Estimation du temps basée sur le nombre de lignes
  const ESTIMATED_TIME_PER_10000_ROWS = 60; // 60 secondes = 1 minute pour 10 000 lignes

  useEffect(() => {
    checkFileInfo();
    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, []);

  const checkFileInfo = () => {
    API.get(APILOGS_API.CSV_INFO, authHeader)
      .then((r) => {
        if (r.data.exists) {
          setFileInfo(r.data);
          const rows = r.data.rows || 0;
          setFileRows(rows);
          if (onFileInfoUpdate) {
            onFileInfoUpdate(rows);
          }
        }
      })
      .catch(() => {});
  };

  const calculateEstimatedTime = (rows) => {
    const seconds = Math.ceil((rows / 10000) * ESTIMATED_TIME_PER_10000_ROWS);
    return seconds;
  };

  const formatTime = (seconds) => {
    if (seconds < 0) seconds = 0;
    if (seconds < 60) {
      return `${seconds} seconde${seconds !== 1 ? 's' : ''}`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      if (secs === 0) {
        return `${minutes} minute${minutes > 1 ? 's' : ''}`;
      }
      return `${minutes} min ${secs} s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours} h ${minutes} min`;
    }
  };

  const startCountdown = (totalSeconds) => {
    let remaining = totalSeconds;
    setEstimatedTimeDisplay(formatTime(remaining));
    
    countdownIntervalRef.current = setInterval(() => {
      remaining -= 1;
      
      if (remaining <= 0) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
        setEstimatedTimeDisplay("Rafraîchissement imminent...");
      } else {
        setEstimatedTimeDisplay(formatTime(remaining));
      }
    }, 1000);
  };

  const cancelCountdown = () => {
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    setEstimatedTimeDisplay(null);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    cancelCountdown();
    
    setUploading(true);
    setUploadProgress(0);
    setEstimatedTimeDisplay(null);
    
    progressIntervalRef.current = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 10;
      });
    }, 200);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await API.post(APILOGS_API.UPLOAD_CSV, formData, authHeader);
      
      clearInterval(progressIntervalRef.current);
      setUploadProgress(100);
      
      const rowsUploaded = response.data?.rows || 0;
      setFileRows(rowsUploaded);
      
      if (rowsUploaded > 0) {
        const seconds = calculateEstimatedTime(rowsUploaded);
        startCountdown(seconds);
        
        if (onFileInfoUpdate) {
          onFileInfoUpdate(rowsUploaded, seconds);
        }
      }
      
      checkFileInfo();
      if (onUploaded) onUploaded();
      
      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
      }, 2000);
      
    } catch (error) {
      clearInterval(progressIntervalRef.current);
      setUploading(false);
      setUploadProgress(0);
      alert("Erreur lors de l'importation du fichier API Logs.");
    } finally {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    }
  };

  const getStaticEstimatedTime = () => {
    if (fileRows > 0) {
      return formatTime(calculateEstimatedTime(fileRows));
    }
    return null;
  };

  return (
    <div className="pd-upload-zone" onClick={() => !uploading && inputRef.current.click()}>
      <input type="file" ref={inputRef} hidden onChange={handleUpload} accept=".csv" />
      
      {uploading ? (
        <div className="flex-center" style={{ flexDirection: 'column', gap: '12px' }}>
          <div className="pd-spinner" />
          <p>Chargement en cours...</p>
          <div className="pd-progress-bar">
            <div 
              className="pd-progress-fill" 
              style={{ width: `${Math.min(uploadProgress, 100)}%` }}
            />
          </div>
          <p className="pd-progress-text">{Math.round(uploadProgress)}%</p>
        </div>
      ) : fileInfo ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
          <p>
            ✅ Fichier détecté : <strong>{fileInfo.filename}</strong> ({fileInfo.rows?.toLocaleString() || 0} lignes)
          </p>
          {fileRows > 0 && (
            <p className="pd-estimate-time">
              ⏱️ Temps estimé de traitement : <strong>{getStaticEstimatedTime()}</strong>
            </p>
          )}
          {estimatedTimeDisplay && (
            <div className="pd-auto-refresh-badge">
              <span>🔄 Rafraîchissement auto dans : <strong>{estimatedTimeDisplay}</strong></span>
              <button 
                className="pd-cancel-refresh-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  cancelCountdown();
                }}
              >
                ✕ Annuler
              </button>
            </div>
          )}
          <p className="pd-upload-hint">📊 10 000 lignes = ~1 minute de traitement</p>
        </div>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <p>🔌 Cliquez pour importer les logs API (.csv)</p>
          <p className="pd-upload-hint">📊 10 000 lignes = ~1 minute de traitement</p>
        </div>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   MAPPING COULEURS
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
   COMPOSANT PRINCIPAL
═══════════════════════════════════════════════════════════ */
export default function APILogsPipelineDashboard() {
  const { user } = useContext(AuthContext);

  const [status,      setStatus]      = useState({ state: "idle", message: "Système prêt" });
  const [results,     setResults]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [csvReady,    setCsvReady]    = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [resetting,   setResetting]   = useState(false);
  
  // État pour le rafraîchissement automatique
  const [autoRefreshInfo, setAutoRefreshInfo] = useState({
    active: false,
    totalSeconds: 0,
    displayTime: null,
    fileRows: 0
  });

  const pollRef          = useRef(null);
  const pollCountRef     = useRef(0);
  const refreshTimerRef  = useRef(null);
  const countdownRef     = useRef(null);
  const totalTimeRef     = useRef(0);

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  // Estimation du temps basée sur le nombre de lignes
  const ESTIMATED_TIME_PER_10000_ROWS = 60;

  const calculateEstimatedTime = (rows) => {
    return Math.ceil((rows / 10000) * ESTIMATED_TIME_PER_10000_ROWS);
  };

  const formatTime = (seconds) => {
    if (seconds < 0) seconds = 0;
    if (seconds < 60) {
      return `${seconds} s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs > 0 ? `${minutes} min ${secs} s` : `${minutes} min`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours} h ${minutes} min`;
    }
  };

  // Nettoyer les timers
  const clearAllTimers = () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  };

  // Démarrer le compte à rebours et le rafraîchissement automatique
  const startAutoRefresh = (totalSeconds, rows) => {
    clearAllTimers();
    
    totalTimeRef.current = totalSeconds;
    let remaining = totalSeconds;
    
    setAutoRefreshInfo({
      active: true,
      totalSeconds: totalSeconds,
      displayTime: formatTime(remaining),
      fileRows: rows
    });
    
    // Compte à rebours chaque seconde
    countdownRef.current = setInterval(() => {
      remaining -= 1;
      
      if (remaining <= 0) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
        setAutoRefreshInfo(prev => ({ 
          ...prev, 
          displayTime: "Rafraîchissement imminent..." 
        }));
      } else {
        setAutoRefreshInfo(prev => ({ 
          ...prev, 
          displayTime: formatTime(remaining) 
        }));
      }
    }, 1000);
    
    // Programmer le rafraîchissement
    refreshTimerRef.current = setTimeout(() => {
      window.location.reload();
    }, totalSeconds * 1000);
  };

  // Annuler le rafraîchissement automatique
  const cancelAutoRefresh = () => {
    clearAllTimers();
    setAutoRefreshInfo({
      active: false,
      totalSeconds: 0,
      displayTime: null,
      fileRows: 0
    });
  };

  // Mise à jour des infos du fichier
  const handleFileInfoUpdate = (rows, estimatedSeconds = null) => {
    if (rows > 0) {
      const seconds = estimatedSeconds || calculateEstimatedTime(rows);
      startAutoRefresh(seconds, rows);
    }
  };

  /* ── Montage : charger CSV info + résultats existants ── */
  useEffect(() => {
    if (!user) return;

    API.get(APILOGS_API.CSV_INFO, authHeader)
      .then((r) => {
        setCsvReady(r.data.exists);
        if (r.data.exists && r.data.rows) {
          const seconds = calculateEstimatedTime(r.data.rows);
          startAutoRefresh(seconds, r.data.rows);
        }
      })
      .catch(() => setStatus({ state: "error", message: "Service API Logs hors ligne" }));

    API.get(APILOGS_API.RESULTS, authHeader)
      .then((r) => {
        if (r.data?.top20?.length > 0) {
          setResults(r.data);
          setStatus({ state: "done", message: "Résultats précédents chargés automatiquement" });
        }
      })
      .catch(() => {});

    return () => {
      clearTimeout(pollRef.current);
      clearAllTimers();
    };
  }, [user]);

  /* ── Lancer le pipeline ── */
  const runPipeline = async () => {
    clearTimeout(pollRef.current);
    pollCountRef.current = 0;
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes API Logs..." });

    try {
      await API.post(APILOGS_API.RUN, {}, authHeader);
      pollStatus();
    } catch (err) {
      if (err?.response?.status === 409) {
        setStatus({ state: "running", message: "Pipeline déjà en cours — synchronisation..." });
        pollStatus();
      } else {
        setStatus({ state: "error", message: "Échec du lancement de l'audit API Logs" });
        setLoading(false);
      }
    }
  };

  /* ── Polling du statut ── */
  const pollStatus = async () => {
    pollCountRef.current += 1;

    if (pollCountRef.current > 400) {
      setStatus({
        state:   "error",
        message: "Timeout — pipeline trop long. Cliquez Réinitialiser puis relancez.",
      });
      setLoading(false);
      return;
    }

    try {
      const res = await API.get(APILOGS_API.STATUS, authHeader);
      const st  = res.data;
      setStatus(st);

      if (st.state === "running" || st.state === "pending") {
        pollRef.current = setTimeout(pollStatus, 3000);
      } else if (st.state === "done") {
        pollCountRef.current = 0;
        setLoading(false);
        await fetchResults();
        // Annuler le rafraîchissement auto une fois terminé
        cancelAutoRefresh();
      } else {
        setLoading(false);
      }
    } catch {
      setStatus({ state: "error", message: "Perte de connexion avec le serveur" });
      setLoading(false);
    }
  };

  /* ── Récupérer les résultats ── */
  const fetchResults = async () => {
    try {
      const res = await API.get(APILOGS_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats API Logs:", err);
    }
  };

  /* ── Réinitialiser ── */
  const resetPipeline = async () => {
    setResetting(true);
    clearTimeout(pollRef.current);
    pollCountRef.current = 0;
    cancelAutoRefresh();
    
    try {
      await API.post(APILOGS_API.RESET, {}, authHeader);
      setLoading(false);
      setStatus({ state: "idle", message: "Pipeline réinitialisé — prêt à relancer" });
    } catch {
      setStatus({ state: "error", message: "Erreur lors de la réinitialisation" });
    } finally {
      setResetting(false);
    }
  };

  /* ── Télécharger CSV ── */
  const downloadCSV = async (url, filename) => {
    try {
      const res = await API.get(url, { ...authHeader, responseType: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([res.data]));
      link.download = filename;
      link.click();
    } catch {
      alert("Erreur lors du téléchargement.");
    }
  };

  const showResetBtn =
    loading || status.state === "running" ||
    status.state === "pending" || status.state === "error";

  return (
    <DashboardLayout user={user}>

      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">Attijari <span>Audit</span> API Logs</h2>
          <p>Analyse IA des journaux API — Détection d'abus, timeouts et anomalies de trafic</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "⏳ Audit API en cours..." : "🚀 Lancer l'Analyse API Logs"}
          </button>

          {showResetBtn && (
            <button
              className="btn-header btn-refresh"
              onClick={resetPipeline}
              disabled={resetting}
              style={{ marginLeft: "10px", background: "#ef4444", color: "#fff", border: "none" }}
            >
              {resetting ? "..." : "🔄 Réinitialiser"}
            </button>
          )}

          {!results && !loading && (
            <button
              className="btn-header btn-refresh"
              onClick={fetchResults}
              style={{ marginLeft: "10px" }}
            >
              📂 Charger résultats existants
            </button>
          )}
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline API Logs :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
        {loading && pollCountRef.current > 0 && (
          <span style={{ marginLeft: "10px", fontSize: "11px", opacity: 0.6 }}>
            ({Math.round(pollCountRef.current * 3)}s)
          </span>
        )}
      </div>

      {/* ── Bannière de rafraîchissement automatique ── */}
      {autoRefreshInfo.active && autoRefreshInfo.displayTime && (
        <div className="pd-auto-refresh-banner">
          <div className="pd-auto-refresh-banner-content">
            <span className="pd-auto-refresh-icon">🔄</span>
            <span>
              Rafraîchissement automatique dans : <strong>{autoRefreshInfo.displayTime}</strong>
              {autoRefreshInfo.fileRows > 0 && (
                <span className="pd-auto-refresh-rows"> ({autoRefreshInfo.fileRows.toLocaleString()} lignes)</span>
              )}
            </span>
            <button 
              className="pd-cancel-refresh-btn"
              onClick={cancelAutoRefresh}
            >
              ✕ Annuler
            </button>
          </div>
        </div>
      )}

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs API</h4>
        <UploadZone 
          onUploaded={() => setCsvReady(true)} 
          authHeader={authHeader}
          onFileInfoUpdate={handleFileInfoUpdate}
        />
      </section>

      {/* ── CRISP-DM ── */}
      <section className="pd-section-glass pd-section-mb">
        <CrispDmSection />
      </section>

      {/* ── Bouton toggle résultats ── */}
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
                {results.stats?.anomaly_rate != null ? `${results.stats.anomaly_rate}%` : "---"}
              </div>
            </div>
          </div>

          {/* Distribution par vote */}
          {results.distributions?.by_vote && Object.keys(results.distributions.by_vote).length > 0 && (
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
          {results.distributions?.by_type && Object.keys(results.distributions.by_type).length > 0 && (
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
          {results.top20?.length > 0 && (
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
                      <td><span className="pd-anomaly-tag">{row.Anomaly_type}</span></td>
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
          )}

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