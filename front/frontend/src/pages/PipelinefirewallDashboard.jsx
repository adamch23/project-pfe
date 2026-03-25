import React, { useState, useEffect, useRef, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import "./PipelineDashboard.css";

/* ═══════════════════════════════════════════════════════════
   ROUTES API — Pipeline Firewall
   Toutes les routes utilisent le préfixe /firewall/
   pour ne pas entrer en conflit avec d'autres pipelines.
═══════════════════════════════════════════════════════════ */
const FIREWALL_API = {
  UPLOAD_CSV : "/firewall/upload-test-csv",
  CSV_INFO   : "/firewall/test-csv-info",
  RUN        : "/firewall/run",
  STATUS     : "/firewall/status",
  RESULTS    : "/firewall/results",
  DOWNLOAD   : "/firewall/download",
  DOWNLOAD_A : "/firewall/download/anomalies",
};

/* ═══════════════════════════════════════════════════════════
   DONNÉES CRISP-DM
═══════════════════════════════════════════════════════════ */
const CRISP_PHASES = [
  {
    num: "01",
    color: "#002e5d",
    bgLight: "#e6eef7",
    title: "Business Understanding",
    sub: "Objectifs métier & contraintes",
    badges: [{ label: "Stratégique", cls: "crp-badge-blue" }],
    description:
      "Définir la problématique métier : détecter automatiquement les comportements anormaux dans les journaux firewall pour réduire les risques de sécurité réseau.",
    sections: [
      {
        label: "Objectif principal",
        type: "text",
        content:
          "Détection non supervisée d'anomalies — Isolation Forest + Autoencoder + LSTM Autoencoder.",
      },
      {
        label: "Sorties attendues",
        type: "pills",
        items: [
          { label: "is_anomaly", cls: "crp-pill-blue" },
          { label: "Anomaly_type", cls: "crp-pill-blue" },
          { label: "Risk (0–10)", cls: "crp-pill-blue" },
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
        ],
      },
      {
        label: "Persistance",
        type: "output",
        items: [
          { icon: "🍃", name: "MongoDB", desc: "firewall_db / detected_anomalies" },
          { icon: "📄", name: "CSV", desc: "Firewall_info/Detected_Anomalies.csv + _anomalies_only.csv" },
          { icon: "📊", name: "PNG", desc: "Firewall_info/plot_*.png" },
        ],
      },
    ],
  },
  {
    num: "02",
    color: "#0f766e",
    bgLight: "#d1fae5",
    title: "Data Understanding",
    sub: "Exploration & distributions",
    badges: [{ label: "Exploration", cls: "crp-badge-green" }],
    description:
      "Chargement des deux datasets (train / test), vérification des valeurs nulles, et visualisation des distributions des features numériques.",
    sections: [
      {
        label: "Fichiers sources",
        type: "output",
        items: [
          { icon: "📂", name: "FirewallReseauLogs.csv", desc: "Entraînement" },
          { icon: "📂", name: "Firewall_Logstest.csv", desc: "Test (uploadable)" },
        ],
      },
      {
        label: "17 features analysées",
        type: "pills",
        items: [
          { label: "Src_port", cls: "crp-pill-teal" },
          { label: "Dst_port", cls: "crp-pill-teal" },
          { label: "Protocol", cls: "crp-pill-teal" },
          { label: "Bytes_sent", cls: "crp-pill-teal" },
          { label: "Bytes_received", cls: "crp-pill-teal" },
          { label: "Packet_count", cls: "crp-pill-teal" },
          { label: "Latency_ms", cls: "crp-pill-teal" },
          { label: "Packet_loss_pct", cls: "crp-pill-teal" },
          { label: "Cpu_usage_fw_pct", cls: "crp-pill-teal" },
          { label: "Concurrent_connections", cls: "crp-pill-teal" },
          { label: "Connection_duration_sec", cls: "crp-pill-teal" },
          { label: "+ 6 autres", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Sorties graphiques",
        type: "output",
        items: [
          { icon: "📊", name: "Firewall_info/plot_distributions.png", desc: "Histogrammes 3×4 features" },
        ],
      },
    ],
  },
  {
    num: "03",
    color: "#7c3aed",
    bgLight: "#ede9fe",
    title: "Data Preparation",
    sub: "Encodage, scaling, séquences",
    badges: [{ label: "Preprocessing", cls: "crp-badge-purple" }],
    description:
      "Encodage LabelEncoder des colonnes catégorielles, gestion des inconnues en test, double scaling (StandardScaler pour IF/AE, MinMaxScaler pour LSTM).",
    sections: [
      {
        label: "Colonnes catégorielles encodées",
        type: "pills",
        items: [
          { label: "Protocol", cls: "crp-pill-purple" },
          { label: "Action", cls: "crp-pill-purple" },
          { label: "Rule_action", cls: "crp-pill-purple" },
          { label: "Network_zone_src", cls: "crp-pill-purple" },
          { label: "Network_zone_dst", cls: "crp-pill-purple" },
          { label: "Nat_translation", cls: "crp-pill-purple" },
        ],
      },
      {
        label: "Scalers appliqués",
        type: "output",
        items: [
          { icon: "⚖️", name: "StandardScaler", desc: "→ Isolation Forest & Autoencoder" },
          { icon: "📐", name: "MinMaxScaler", desc: "→ LSTM Autoencoder (séquences)" },
        ],
      },
      {
        label: "Séquences LSTM",
        type: "text",
        content:
          "Fenêtre glissante LSTM_WINDOW=5, échantillon LSTM_SAMPLE=8 000 séquences aléatoires pour l'entraînement. Padding médian sur les (W−1) premiers points en inférence.",
      },
    ],
  },
  {
    num: "04",
    color: "#b45309",
    bgLight: "#fef3c7",
    title: "Modeling",
    sub: "3 modèles + vote d'ensemble",
    badges: [
      { label: "IF", cls: "crp-badge-amber" },
      { label: "AE", cls: "crp-badge-amber" },
      { label: "LSTM", cls: "crp-badge-amber" },
    ],
    description:
      "Trois modèles complémentaires entraînés indépendamment, puis combinés par vote majoritaire pour maximiser la robustesse de détection.",
    sections: [
      {
        label: "Modèles",
        type: "models",
        items: [
          {
            title: "Isolation Forest",
            dot: "#002e5d",
            lines: [
              "n_estimators=100, max_features=0.8",
              "contamination=auto",
              "Score : −decision_function normalisé",
            ],
          },
          {
            title: "Autoencoder Dense",
            dot: "#7c3aed",
            lines: [
              "Input → 64 → 16 → 64 → Output",
              "Dropout 0.1, Adam lr=2e-3",
              "Seuil : μ + 1.5σ sur MSE train",
            ],
          },
          {
            title: "LSTM Autoencoder",
            dot: "#0f766e",
            lines: [
              "LSTM(32) → RepeatVector → LSTM(32)",
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
        label: "Classification du type",
        type: "pills",
        items: [
          { label: "DDoS", cls: "crp-pill-red" },
          { label: "Latence / Perte paquet", cls: "crp-pill-amber" },
          { label: "Scan réseau", cls: "crp-pill-amber" },
          { label: "Port inhabituel", cls: "crp-pill-blue" },
          { label: "Comportement anormal", cls: "crp-pill-gray" },
        ],
      },
    ],
  },
  {
    num: "05",
    color: "#be123c",
    bgLight: "#fee2e2",
    title: "Evaluation",
    sub: "Métriques & visualisations",
    badges: [{ label: "Analyse", cls: "crp-badge-red" }],
    description:
      "Calcul du score de risque (0–10) par règles métier, génération des courbes de convergence des autoencoders et projection PCA 2D des anomalies détectées.",
    sections: [
      {
        label: "Score de risque — règles",
        type: "pills",
        items: [
          { label: "Packet_count ≥ 5000 → +9", cls: "crp-pill-red" },
          { label: "Bytes_sent ≥ 1M → +8", cls: "crp-pill-red" },
          { label: "Concurrent_conn ≥ 5000 → +7", cls: "crp-pill-red" },
          { label: "Latency_ms ≥ 300 → +7", cls: "crp-pill-amber" },
          { label: "Packet_loss ≥ 5% → +6", cls: "crp-pill-amber" },
          { label: "CPU ≥ 85% → +5", cls: "crp-pill-amber" },
          { label: "Dst_port ≥ 20000 → +4", cls: "crp-pill-gray" },
        ],
      },
      {
        label: "Graphiques générés",
        type: "output",
        items: [
          { icon: "📈", name: "Firewall_info/plot_convergence.png", desc: "MSE loss AE + LSTM AE" },
          { icon: "🔵", name: "Firewall_info/plot_pca.png", desc: "Projection PCA 2D par type d'anomalie" },
        ],
      },
    ],
  },
  {
    num: "06",
    color: "#0369a1",
    bgLight: "#e0f2fe",
    title: "Deployment & Monitoring",
    sub: "Export CSV + MongoDB + API REST",
    badges: [
      { label: "FastAPI", cls: "crp-badge-blue" },
      { label: "MongoDB", cls: "crp-badge-green" },
    ],
    description:
      "Exposition du pipeline via API REST FastAPI (upload CSV, lancement asynchrone, polling statut, téléchargement résultats) et persistance MongoDB avec upsert par Event_id.",
    sections: [
      {
        label: "Endpoints API — préfixe /firewall/",
        type: "output",
        items: [
          { icon: "⬆️", name: "POST /firewall/upload-test-csv", desc: "Upload données test" },
          { icon: "🚀", name: "POST /firewall/run", desc: "Lancement asynchrone (202)" },
          { icon: "📡", name: "GET /firewall/status", desc: "Polling état pipeline" },
          { icon: "📊", name: "GET /firewall/results", desc: "Top 20 + stats" },
          { icon: "💾", name: "GET /firewall/download", desc: "Export CSV complet" },
          { icon: "⚠️", name: "GET /firewall/download/anomalies", desc: "Export anomalies uniquement" },
        ],
      },
      {
        label: "Dossier de sortie",
        type: "output",
        items: [
          { icon: "📁", name: "Firewall_info/", desc: "CSV + PNG isolés du dossier racine IA" },
        ],
      },
      {
        label: "Stratégie MongoDB",
        type: "text",
        content:
          "Upsert par Event_id (pas de doublons entre runs). Index créés sur is_anomaly, Anomaly_type, Risk, pipeline_run_at. Horodatage UTC unique par run pour la traçabilité.",
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
        return (
          <p key={idx} className="crp-content-text">
            {sec.content}
          </p>
        );

      case "pills":
        return (
          <div key={idx} className="crp-items-list">
            {sec.items.map((it, j) => (
              <span key={j} className={`crp-pill ${it.cls}`}>
                {it.label}
              </span>
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
                  <span
                    className="crp-model-dot"
                    style={{ background: m.dot }}
                  />
                  {m.title}
                </div>
                {m.lines.map((l, k) => (
                  <div key={k} className="crp-model-detail">
                    {l}
                  </div>
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
                  <div
                    className="crp-vote-fill"
                    style={{ width: `${v.pct}%`, background: v.color }}
                  />
                </div>
              </div>
            ))}
            {sec.note && (
              <p className="crp-vote-note">{sec.note}</p>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <section className="crp-wrap">
      <div className="crp-section-header">
        <div className="crp-section-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </div>
        <div>
          <h3 className="crp-section-title">
            Pipeline CRISP-DM — Détection d'Anomalies Réseau Firewall
          </h3>
          <p className="crp-section-sub">
            6 phases · 3 modèles IA · Vote d'ensemble · MongoDB · Sorties dans Firewall_info/
          </p>
        </div>
      </div>

      <div className="crp-phases">
        {CRISP_PHASES.map((ph, i) => {
          const isOpen = openIndex === i;
          return (
            <div
              key={i}
              className={`crp-phase-card ${isOpen ? "crp-open" : ""}`}
              style={{ "--ph-color": ph.color, "--ph-bg": ph.bgLight }}
            >
              <div
                className="crp-phase-header"
                onClick={() => toggle(i)}
                role="button"
                aria-expanded={isOpen}
              >
                <span
                  className="crp-phase-num"
                  style={{ background: ph.color, color: "#fff" }}
                >
                  {ph.num}
                </span>
                <div className="crp-phase-title-block">
                  <div className="crp-phase-title">{ph.title}</div>
                  <div className="crp-phase-sub">{ph.sub}</div>
                </div>
                <div className="crp-badges">
                  {ph.badges.map((b, j) => (
                    <span key={j} className={`crp-badge ${b.cls}`}>
                      {b.label}
                    </span>
                  ))}
                </div>
                <svg
                  className="crp-chevron"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  width="16"
                  height="16"
                >
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
   COMPOSANT UPLOAD — Pipeline Firewall
═══════════════════════════════════════════════════════════ */
const UploadZone = ({ onUploaded, authHeader }) => {
  const [uploading, setUploading] = useState(false);
  const [fileInfo, setFileInfo]   = useState(null);
  const inputRef = useRef();

  useEffect(() => { checkFileInfo(); }, []);

  const checkFileInfo = () => {
    API.get(FIREWALL_API.CSV_INFO, authHeader)
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
      await API.post(FIREWALL_API.UPLOAD_CSV, formData, authHeader);
      checkFileInfo();
      if (onUploaded) onUploaded();
    } catch {
      alert("Erreur lors de l'importation du fichier Firewall.");
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
        <p>📁 Cliquez pour importer les journaux Firewall (.csv)</p>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   COMPOSANT PRINCIPAL — PipelineDashboard (Firewall)
═══════════════════════════════════════════════════════════ */
export default function PipelineDashboard() {
  const { user } = useContext(AuthContext);

  const [status,      setStatus]      = useState({ state: "idle", message: "Système prêt" });
  const [results,     setResults]     = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [csvReady,    setCsvReady]    = useState(false);
  const [showResults, setShowResults] = useState(false);
  const pollRef = useRef(null);

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  // Vérification initiale du CSV de test Firewall
  useEffect(() => {
    if (user) {
      API.get(FIREWALL_API.CSV_INFO, authHeader)
        .then((r) => setCsvReady(r.data.exists))
        .catch(() =>
          setStatus({ state: "error", message: "Service d'analyse Firewall hors ligne" })
        );
    }
    return () => clearTimeout(pollRef.current);
  }, [user]);

  const runPipeline = async () => {
    setLoading(true);
    setShowResults(false);
    setStatus({ state: "pending", message: "Initialisation des algorithmes Firewall..." });
    try {
      await API.post(FIREWALL_API.RUN, {}, authHeader);
      pollStatus();
    } catch {
      setStatus({ state: "error", message: "Échec du lancement de l'audit Firewall" });
      setLoading(false);
    }
  };

  const pollStatus = async () => {
    try {
      const res = await API.get(FIREWALL_API.STATUS, authHeader);
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
      const res = await API.get(FIREWALL_API.RESULTS, authHeader);
      setResults(res.data);
      setShowResults(true);
    } catch (err) {
      console.error("Erreur résultats Firewall:", err);
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
      alert("Erreur lors du téléchargement du rapport Firewall.");
    }
  };

  return (
    <DashboardLayout user={user}>
      {/* ── Header ── */}
      <div className="admin-view-header">
        <div className="header-text">
          <h2 className="pd-title">
            Attijari <span>Audit</span> Security
          </h2>
          <p>Analyse IA des flux réseaux Firewall — Détection d'anomalies</p>
        </div>
        <div className="header-action-btns">
          <button
            className="btn-header btn-add"
            onClick={runPipeline}
            disabled={loading || !csvReady}
          >
            {loading ? "Audit Firewall en cours..." : "🚀 Lancer l'Analyse Firewall"}
          </button>
        </div>
      </div>

      {/* ── Barre de statut ── */}
      <div className={`pd-status-bar state-${status.state}`}>
        {loading && <div className="pd-spinner" />}
        <span className="pd-status-label">Statut du pipeline Firewall :</span>
        <span className={`pd-status-message ${status.state === "error" ? "pd-status-error" : ""}`}>
          {status.message}
        </span>
      </div>

      {/* ── Import CSV ── */}
      <section className="pd-section-glass">
        <h4 className="pd-section-title-sm">1. Importation des Logs Firewall</h4>
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
            {showResults ? "🙈 Masquer les Résultats" : "📊 Afficher les Résultats Firewall"}
          </button>
        </div>
      )}

      {/* ── Résultats ── */}
      {results && showResults && (
        <div className="results-animate-fade">

          {/* KPI Cards */}
          <div className="pd-stats">
            <div className="pd-stat-card">
              <div className="pd-stat-label">Flux Analysés</div>
              <div className="pd-stat-value">
                {results.stats?.total_processed?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card gold">
              <div className="pd-stat-label">Anomalies Détectées</div>
              <div className="pd-stat-value">
                {results.stats?.total_anomalies?.toLocaleString() ?? "---"}
              </div>
            </div>
            <div className="pd-stat-card red">
              <div className="pd-stat-label">Alertes Critiques</div>
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
              <h4 className="pd-dist-title">Distribution par type d'anomalie</h4>
              <div className="pd-type-list">
                {Object.entries(results.distributions.by_type).map(([type, count]) => {
                  const colorMap = {
                    DDoS                    : "pd-type-red",
                    "Scan réseau"           : "pd-type-amber",
                    "Latence / Perte paquet": "pd-type-amber",
                    "Port inhabituel"       : "pd-type-blue",
                    "Comportement anormal"  : "pd-type-gray",
                  };
                  const cls = colorMap[type] || "pd-type-gray";
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
            <div className="pd-panel-head">TOP 20 DES MENACES FIREWALL IDENTIFIÉES</div>
            <table className="attijari-table-modern">
              <thead>
                <tr>
                  <th>IP SOURCE</th>
                  <th>IP DESTINATION</th>
                  <th>TYPE DE MENACE</th>
                  <th className="text-center">VOTES</th>
                  <th className="text-center">SCORE DE RISQUE</th>
                </tr>
              </thead>
              <tbody>
                {results.top20.map((row, i) => (
                  <tr key={i}>
                    <td className="pd-td-src">{row.Src_ip}</td>
                    <td>{row.Dst_ip}</td>
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
              onClick={() => downloadCSV(FIREWALL_API.DOWNLOAD, "Rapport_Audit_Firewall_Attijari.csv")}
            >
              📥 Télécharger le rapport complet (.CSV)
            </button>
            <button
              className="btn-header btn-refresh"
              onClick={() => downloadCSV(FIREWALL_API.DOWNLOAD_A, "Anomalies_Firewall_Attijari.csv")}
            >
              ⚠️ Télécharger les anomalies uniquement (.CSV)
            </button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}