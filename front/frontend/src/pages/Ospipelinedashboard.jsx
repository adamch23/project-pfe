import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css";

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline OS & Infrastructure
   Toutes les routes utilisent le préfixe /os/
═══════════════════════════════════════════════════════════ */
const OS_API = {
  UPLOAD_CSV : "/os/upload-test-csv",
  CSV_INFO   : "/os/test-csv-info",
  RUN        : "/os/run",
  STATUS     : "/os/status",
  RESULTS    : "/os/results",
  DOWNLOAD   : "/os/download",
  DOWNLOAD_A : "/os/download/anomalies",
};

/* ═══════════════════════════════════════════════════════════
   DONNÉES CRISP-DM — Pipeline OS & Infrastructure
═══════════════════════════════════════════════════════════ */
const CRISP_PHASES = [
  {
    num: "01",
    color: "#1b4332",
    bgLight: "#d8f3dc",
    title: "Business Understanding",
    sub: "Objectifs métier & contraintes OS",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Détecter automatiquement les comportements anormaux dans les logs OS & Infrastructure : saturations CPU/mémoire, crashes de services, escalades de privilèges, malwares et mauvaises configurations — pour prévenir les interruptions système et les incidents de sécurité.",
    sections: [
      {
        label: "Objectif principal",
        type: "text",
        content:
          "Détection non supervisée d'anomalies OS & Infrastructure — Isolation Forest + Autoencoder Dense + LSTM Autoencoder avec feature engineering temporel et vote d'ensemble.",
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
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_os_anomalies" },
          { icon: "📄", name: "CSV", desc: "OS_info/Detected_OS_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG", desc: "OS_info/plot_os_*.png" },
        ],
      },
    ],
  },
  {
    num: "02",
    color: "#2d6a4f",
    bgLight: "#b7e4c7",
    title: "Data Understanding",
    sub: "Exploration & feature engineering temporel",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description:
      "Chargement et normalisation des noms de colonnes (lowercase), feature engineering temporel automatique à partir du timestamp, visualisation des distributions des features numériques clés.",
    sections: [
      {
        label: "Fichiers sources",
        type: "output",
        items: [
          { icon: "📂", name: "OS&Infrastructure.csv", desc: "Entraînement" },
          { icon: "📂", name: "OS&Infrastructure_test.csv", desc: "Test (uploadable)" },
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
        label: "Features numériques analysées",
        type: "pills",
        items: [
          { label: "cpu_usage_percent", cls: "crp-pill-teal" },
          { label: "memory_usage_percent", cls: "crp-pill-teal" },
          { label: "disk_usage_percent", cls: "crp-pill-teal" },
          { label: "disk_io_rate", cls: "crp-pill-teal" },
          { label: "network_io_rate", cls: "crp-pill-teal" },
          { label: "open_file_descriptors", cls: "crp-pill-teal" },
          { label: "running_process_count", cls: "crp-pill-teal" },
          { label: "failed_login_count_15min", cls: "crp-pill-teal" },
          { label: "service_restart_count_1h", cls: "crp-pill-teal" },
          { label: "uptime_hours", cls: "crp-pill-teal" },
          { label: "config_change_flag", cls: "crp-pill-teal" },
          { label: "+ 4 temporelles", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Sortie graphique",
        type: "output",
        items: [
          { icon: "📊", name: "OS_info/plot_os_distributions.png", desc: "Histogrammes 3×4 features numériques" },
        ],
      },
    ],
  },
  {
    num: "03",
    color: "#40916c",
    bgLight: "#d8f3dc",
    title: "Data Preparation",
    sub: "Encodage, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description:
      "LabelEncoder sur les 6 colonnes catégorielles avec gestion des valeurs inconnues en test. Double scaling : StandardScaler (IF/AE) et MinMaxScaler (LSTM). Séquences temporelles par fenêtre glissante de 5.",
    sections: [
      {
        label: "Colonnes encodées (LabelEncoder)",
        type: "pills",
        items: [
          { label: "host_id", cls: "crp-pill-purple" },
          { label: "host_role", cls: "crp-pill-purple" },
          { label: "event_type", cls: "crp-pill-purple" },
          { label: "service_name", cls: "crp-pill-purple" },
          { label: "process_name", cls: "crp-pill-purple" },
          { label: "patch_level", cls: "crp-pill-purple" },
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
          "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires. Padding médian sur les 4 premiers points en inférence pour couvrir tous les enregistrements.",
      },
    ],
  },
  {
    num: "04",
    color: "#52b788",
    bgLight: "#b7e4c7",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF", cls: "crp-badge-amber" },
      { label: "AE", cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description:
      "Trois modèles non supervisés entraînés sur les logs OS. La classification du type utilise d'abord les règles métier (event_type, seuils CPU/mémoire), puis KMeans sur les cas ambigus.",
    sections: [
      {
        label: "Modèles",
        type: "models",
        items: [
          {
            title: "Isolation Forest",
            dot: "#1b4332",
            lines: [
              "n_estimators=400, max_features=0.8",
              "contamination=auto, n_jobs=-1",
              "Score : −decision_function normalisé",
            ],
          },
          {
            title: "Autoencoder Dense OS",
            dot: "#40916c",
            lines: [
              "Input → 128 → 32 → 128 → Output",
              "Dropout 0.15, Adam lr=2e-3, batch=512",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
          {
            title: "LSTM Autoencoder OS",
            dot: "#2d6a4f",
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
        label: "Types d'anomalies OS détectés",
        type: "pills",
        items: [
          { label: "Malware", cls: "crp-pill-red" },
          { label: "Escalade privilèges", cls: "crp-pill-red" },
          { label: "Service crash", cls: "crp-pill-red" },
          { label: "Saturation CPU", cls: "crp-pill-amber" },
          { label: "Fuite mémoire", cls: "crp-pill-amber" },
          { label: "Mauvaise configuration système", cls: "crp-pill-amber" },
          { label: "Tentatives connexion suspectes", cls: "crp-pill-blue" },
          { label: "Trafic réseau anormal", cls: "crp-pill-blue" },
          { label: "Comportement anormal", cls: "crp-pill-gray" },
        ],
      },
    ],
  },
  {
    num: "05",
    color: "#74c69d",
    bgLight: "#d8f3dc",
    title: "Evaluation",
    sub: "Métriques & visualisations OS",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description:
      "Score de risque (0–10) calculé par règles métier pondérées selon la criticité : malware et escalade de privilèges au plus haut. Courbes MSE et projection PCA 2D colorée par type.",
    sections: [
      {
        label: "Score de risque OS — règles pondérées",
        type: "pills",
        items: [
          { label: "event_type = malware_detected → +9", cls: "crp-pill-red" },
          { label: "event_type = privilege_escalation → +8", cls: "crp-pill-red" },
          { label: "event_type = crash → +7", cls: "crp-pill-red" },
          { label: "service_restart_count_1h > 3 → +6", cls: "crp-pill-amber" },
          { label: "cpu_usage_percent > 90% → +5", cls: "crp-pill-amber" },
          { label: "memory_usage_percent > 90% → +5", cls: "crp-pill-amber" },
          { label: "disk_usage_percent > 90% → +4", cls: "crp-pill-amber" },
          { label: "failed_login_count_15min > 5 → +4", cls: "crp-pill-gray" },
          { label: "config_change_flag = 1 → +3", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Graphiques générés",
        type: "output",
        items: [
          { icon: "📈", name: "OS_info/plot_os_convergence.png", desc: "Courbes MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "OS_info/plot_os_pca.png", desc: "Projection PCA 2D par type d'anomalie OS" },
        ],
      },
    ],
  },
  {
    num: "06",
    color: "#52b788",
    bgLight: "#b7e4c7",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI", cls: "crp-badge-blue" },
      { label: "MongoDB", cls: "crp-badge-green" },
    ],
    description:
      "Pipeline exposé via API REST FastAPI avec préfixe /os/. Dossier de sortie OS_info/ isolé des autres pipelines. Collection MongoDB dédiée detected_os_anomalies.",
    sections: [
      {
        label: "Endpoints API — préfixe /os/",
        type: "output",
        items: [
          { icon: "⬆️", name: "POST /os/upload-test-csv", desc: "Upload données test OS" },
          { icon: "🚀", name: "POST /os/run", desc: "Lancement asynchrone (202)" },
          { icon: "📡", name: "GET /os/status", desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /os/results", desc: "Top 20 + stats OS" },
          { icon: "💾", name: "GET /os/download", desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /os/download/anomalies", desc: "Export anomalies uniquement" },
        ],
      },
      {
        label: "Dossier de sortie",
        type: "output",
        items: [
          { icon: "📁", name: "OS_info/", desc: "Isolé de Firewall_info/ et DB_info/ — aucun conflit" },
        ],
      },
      {
        label: "Stratégie MongoDB",
        type: "text",
        content:
          "Collection dédiée detected_os_anomalies (séparée des deux autres pipelines). Upsert par event_id, index sur is_anomaly / Anomaly_type / Risk / pipeline_run_at. Horodatage UTC unique par run.",
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
        <div className="crp-section-icon" style={{ background: "#1b4332" }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">
            Pipeline CRISP-DM — Détection d'Anomalies OS & Infrastructure
          </h3>
          <p className="crp-section-sub">
            6 phases · Feature engineering temporel · 3 modèles IA · Vote d'ensemble · OS_info/
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
   COMPOSANT UPLOAD — Pipeline OS
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader }) => {
  const [uploading, setUploading] = useState(false);
  const [fileInfo,  setFileInfo]  = useState(null);
  const inputRef = useRef();

  useEffect(() => { checkFileInfo(); }, []);

  const checkFileInfo = () => {
    API.get(OS_API.CSV_INFO, authHeader)
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
      await API.post(OS_API.UPLOAD_CSV, formData, authHeader);
      checkFileInfo();
      if (onUploaded) onUploaded();
    } catch {
      alert("Erreur lors de l'importation du fichier OS Infrastructure.");
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
        <p>🖥️ Cliquez pour importer les journaux OS & Infrastructure (.csv)</p>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   MAPPING COULEURS — Types d'anomalies OS
═══════════════════════════════════════════════════════════ */
const OS_TYPE_COLOR_MAP = {
  "Malware"                          : "pd-type-red",
  "Escalade privilèges"              : "pd-type-red",
  "Service crash"                    : "pd-type-red",
  "Saturation CPU"                   : "pd-type-amber",
  "Fuite mémoire"                    : "pd-type-amber",
  "Mauvaise configuration système"   : "pd-type-amber",
  "Tentatives connexion suspectes"   : "pd-type-blue",
  "Trafic réseau anormal"            : "pd-type-blue",
  "Comportement anormal"             : "pd-type-gray",
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT PRINCIPAL — OSPipelineDashboard
═══════════════════════════════════════════════════════════ */
export default function OSPipelineDashboard() {
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
      API.get(OS_API.CSV_INFO, authHeader)
        .then((r) => setCsvReady(r.data.exists))
        .catch(() =>
          setStatus({ state: "error", message: "Service d'analyse OS hors ligne" })
        );
    }
    return () => clearTimeout(pollRef.current);
  }, [user]);

  const runPipeline = async () => {
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes OS & Infrastructure..." });
    try {
      await API.post(OS_API.RUN, {}, authHeader);
      pollStatus();
    } catch {
      setStatus({ state: "error", message: "Échec du lancement de l'audit OS" });
      setLoading(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await API.get(OS_API.STATUS, authHeader);
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
      const res = await API.get(OS_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats OS:", err);
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
      alert("Erreur lors du téléchargement du rapport OS.");
    }
  };

  return (
    <DashboardLayout user={user}>
      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">
            Attijari <span>Audit</span> OS & Infrastructure
          </h2>
          <p>Analyse IA des journaux système — Détection d'anomalies OS & Infrastructure</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "Audit OS en cours..." : "🚀 Lancer l'Analyse OS"}
          </button>
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline OS & Infrastructure :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
      </div>

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs OS & Infrastructure</h4>
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
            {showResults ? "🙈 Masquer les Résultats" : "📊 Afficher les Résultats OS"}
          </button>
        </div>
      )}

      {/* ── Résultats ── */}
      {results && showResults && (
        <div className="results-animate-fade">

          {/* KPI Cards */}
          <div className="pd-stats">
            <div className="pd-stat-card">
              <div className="pd-stat-label">Événements Analysés</div>
              <div className="pd-stat-value">
                {results.stats?.total_processed?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card gold">
              <div className="pd-stat-label">Anomalies OS Détectées</div>
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
              <h4 className="pd-dist-title">Distribution par type d'anomalie OS</h4>
              <div className="pd-type-list">
                {Object.entries(results.distributions.by_type).map(([type, count]) => {
                  const cls = OS_TYPE_COLOR_MAP[type] || "pd-type-gray";
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
            <div className="pd-panel-head">TOP 20 DES INCIDENTS OS & INFRASTRUCTURE IDENTIFIÉS</div>
            <table className="attijari-table-modern">
              <thead>
                <tr>
                  <th>HOST ID</th>
                  <th>RÔLE</th>
                  <th>TYPE D'ANOMALIE</th>
                  <th className="text-center">VOTES</th>
                  <th className="text-center">SCORE DE RISQUE</th>
                </tr>
              </thead>
              <tbody>
                {results.top20.map((row, i) => (
                  <tr key={i}>
                    <td className="pd-td-src">{row.host_id ?? "—"}</td>
                    <td>{row.host_role ?? "—"}</td>
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
              onClick={() => downloadCSV(OS_API.DOWNLOAD, "Rapport_Audit_OS_Attijari.csv")}
            >
              📥 Télécharger le rapport complet (.CSV)
            </button>
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(OS_API.DOWNLOAD_A, "Anomalies_OS_Attijari.csv")}
            >
              ⚠️ Télécharger les anomalies uniquement (.CSV)
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}