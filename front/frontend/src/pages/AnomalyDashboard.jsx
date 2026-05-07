// AnomalyDashboard.jsx - Version complète améliorée
import React, { useState, useEffect, useCallback, useContext } from "react";
import DashboardLayout from "./DashboardLayout";
import { AuthContext } from "../context/AuthContext";

const API_BASE = "/api";

const PIPELINES = [
  { key: "firewall", label: "Firewall / Réseau",   icon: "🛡️", color: "#e63946", bg: "rgba(230,57,70,0.15)",  border: "rgba(230,57,70,0.35)"  },
  { key: "os",       label: "OS & Infrastructure", icon: "💻", color: "#2d9e6b", bg: "rgba(45,158,107,0.15)", border: "rgba(45,158,107,0.35)" },
  { key: "app",      label: "Logs Applicatifs",    icon: "📱", color: "#9b5de5", bg: "rgba(155,93,229,0.15)", border: "rgba(155,93,229,0.35)" },
  { key: "apilogs",  label: "API Logs",            icon: "🔌", color: "#0096c7", bg: "rgba(0,150,199,0.15)",  border: "rgba(0,150,199,0.35)"  },
  { key: "database", label: "Base de Données",     icon: "🗄️", color: "#f4a261", bg: "rgba(244,162,97,0.15)", border: "rgba(244,162,97,0.35)" },
];

const RISK_CONFIG = {
  critical: { min: 8, color: "#e63946", label: "CRITIQUE", icon: "🔴", bg: "rgba(230,57,70,0.12)",  border: "rgba(230,57,70,0.3)"  },
  high:     { min: 5, color: "#f4a261", label: "ÉLEVÉ",    icon: "🟠", bg: "rgba(244,162,97,0.12)", border: "rgba(244,162,97,0.3)" },
  medium:   { min: 3, color: "#f9c74f", label: "MOYEN",    icon: "🟡", bg: "rgba(249,199,79,0.12)", border: "rgba(249,199,79,0.3)" },
  low:      { min: 0, color: "#52b788", label: "FAIBLE",   icon: "🟢", bg: "rgba(82,183,136,0.12)", border: "rgba(82,183,136,0.3)" },
};

function getRiskLevel(risk) {
  for (const [level, config] of Object.entries(RISK_CONFIG)) {
    if (risk >= config.min) return { level, ...config };
  }
  return { level: "low", ...RISK_CONFIG.low };
}

function authHeaders(token) {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

// ── Spinner ───────────────────────────────────────────────────────
function Spinner({ size = 14, color = "#fff" }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size,
      border: `2px solid ${color}30`, borderTopColor: color,
      borderRadius: "50%", animation: "spin 0.7s linear infinite", flexShrink: 0,
    }} />
  );
}

// ── Pagination component ──────────────────────────────────────────
function Pagination({ currentPage, totalPages, onPage, color }) {
  if (totalPages <= 1) return null;
  const pages = [];
  let start = Math.max(1, currentPage - 2);
  let end   = Math.min(totalPages, start + 4);
  if (end - start < 4) start = Math.max(1, end - 4);
  for (let p = start; p <= end; p++) pages.push(p);

  const btnBase = {
    padding: "5px 11px", borderRadius: "6px", fontSize: "11px",
    cursor: "pointer", border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.04)", color: "#9ca3af",
    transition: "all 0.15s", fontFamily: "inherit",
  };
  const disabled = { opacity: 0.3, cursor: "default", pointerEvents: "none" };

  return (
    <div style={{ display: "flex", gap: "5px", alignItems: "center", flexWrap: "wrap" }}>
      <button onClick={() => onPage(1)} disabled={currentPage === 1}
        style={{ ...btnBase, ...(currentPage === 1 ? disabled : {}) }}>«</button>
      <button onClick={() => onPage(currentPage - 1)} disabled={currentPage === 1}
        style={{ ...btnBase, ...(currentPage === 1 ? disabled : {}) }}>‹ Préc.</button>
      {pages.map(p => (
        <button key={p} onClick={() => onPage(p)} style={{
          ...btnBase,
          ...(p === currentPage ? { background: color, color: "#fff", border: "none", fontWeight: 700 } : {}),
        }}>{p}</button>
      ))}
      <button onClick={() => onPage(currentPage + 1)} disabled={currentPage >= totalPages}
        style={{ ...btnBase, ...(currentPage >= totalPages ? disabled : {}) }}>Suiv. ›</button>
      <button onClick={() => onPage(totalPages)} disabled={currentPage >= totalPages}
        style={{ ...btnBase, ...(currentPage >= totalPages ? disabled : {}) }}>»</button>
    </div>
  );
}

// ================================================================
// MODAL RAPPORT IA
// ================================================================
function AIReportModal({ anomaly, typeAnalysis, pipeline, onClose }) {
  const riskInfo      = getRiskLevel(anomaly?.risk || 0);
  const pipelineConfig = PIPELINES.find(p => p.key === pipeline);
  const analysis      = typeAnalysis?.full_analysis || "";

  function parseSection(text, label) {
    const patterns = [
      new RegExp(`${label}\\s*[:\\-]?\\s*([\\s\\S]*?)(?=\\n(?:Explication|Recommandations|Temps estimé|la Cause|$))`, "i"),
      new RegExp(`${label}\\s*[:\\-]?\\s*([\\s\\S]*?)(?=\\n\\n|$)`, "i"),
    ];
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]?.trim()) return match[1].trim();
    }
    return null;
  }

  const cause        = parseSection(analysis, "la Cause") || parseSection(analysis, "Cause");
  const explication  = parseSection(analysis, "Explication");
  const tempsEstime  = (() => { const m = analysis.match(/Temps estimé[^:]*:([\s\S]*?)(?=\n\n|$)/i); return m?.[1]?.trim() || null; })();
  const recommandations = (() => { const m = analysis.match(/Recommandations?\s*:?([\s\S]*?)(?=Temps estimé|$)/i); return m?.[1]?.trim() || null; })();

  if (!anomaly) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0,
        background: "rgba(2,4,12,0.92)",
        backdropFilter: "blur(10px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: "16px",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "linear-gradient(160deg, #0a0f1e 0%, #0d1424 100%)",
          border: `1px solid ${riskInfo.color}35`,
          borderRadius: "18px",
          maxWidth: "820px", width: "100%", maxHeight: "90vh",
          overflow: "auto", position: "relative",
          boxShadow: `0 0 60px ${riskInfo.color}20, 0 25px 50px rgba(0,0,0,0.7)`,
          animation: "modalIn 0.28s cubic-bezier(.22,1,.36,1)",
        }}
      >
        {/* stripe top */}
        <div style={{ height: "3px", background: `linear-gradient(90deg, ${riskInfo.color}, ${pipelineConfig?.color})`, borderRadius: "18px 18px 0 0" }} />

        {/* header */}
        <div style={{ padding: "22px 26px 18px", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "8px" }}>
                <span style={{ fontSize: "22px" }}>{riskInfo.icon}</span>
                <span style={{ fontSize: "18px", fontWeight: 700, color: "#f0f4ff" }}>{anomaly.anomaly_type || "Anomalie"}</span>
                <span style={{ background: riskInfo.color, color: "#fff", padding: "3px 12px", borderRadius: "30px", fontSize: "10px", fontWeight: 700, letterSpacing: "1px" }}>
                  {riskInfo.label} · {anomaly.risk}/10
                </span>
              </div>
              <div style={{ fontSize: "11px", color: "#6b7280", display: "flex", gap: "14px", flexWrap: "wrap" }}>
                {anomaly.anomaly_id && <span>ID: <code style={{ color: "#8b95a8" }}>{anomaly.anomaly_id.slice(0, 14)}...</code></span>}
                {anomaly.timestamp  && <span>🕐 {new Date(anomaly.timestamp).toLocaleString("fr-FR")}</span>}
                <span>{pipelineConfig?.icon} {pipelineConfig?.label}</span>
              </div>
            </div>
            <button onClick={onClose} style={{
              background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
              width: "34px", height: "34px", borderRadius: "9px", cursor: "pointer",
              color: "#9ca3af", fontSize: "15px", flexShrink: 0, transition: "all 0.2s",
            }}
              onMouseEnter={e => { e.target.style.background = "rgba(255,255,255,0.12)"; e.target.style.color = "#fff"; }}
              onMouseLeave={e => { e.target.style.background = "rgba(255,255,255,0.06)"; e.target.style.color = "#9ca3af"; }}
            >✕</button>
          </div>
        </div>

        {/* body */}
        <div style={{ padding: "22px 26px" }}>
          {typeAnalysis && (
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "22px" }}>
              {[
                { label: "Événements similaires", value: typeAnalysis.count,               color: pipelineConfig?.color },
                { label: "Risque moyen",           value: `${typeAnalysis.risk_avg}/10`,   color: riskInfo.color },
                { label: "Risque max",             value: `${typeAnalysis.risk_max}/10`,   color: "#e63946" },
                { label: "Critiques",              value: typeAnalysis.critical_count || 0, color: "#e63946" },
              ].map(stat => (
                <div key={stat.label} style={{
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "10px", padding: "10px 16px", textAlign: "center", flex: "1", minWidth: "90px",
                }}>
                  <div style={{ fontSize: "20px", fontWeight: 700, color: stat.color }}>{stat.value}</div>
                  <div style={{ fontSize: "10px", color: "#6b7280", marginTop: "2px" }}>{stat.label}</div>
                </div>
              ))}
            </div>
          )}

          {analysis ? (
            <>
              {cause         && <ReportSection icon="⚑" title="LA CAUSE"                 color={riskInfo.color}       content={cause} />}
              {explication   && <ReportSection icon="◎" title="EXPLICATION TECHNIQUE"     color="#0096c7"              content={explication} />}
              {recommandations && <ReportSection icon="✓" title="RECOMMANDATIONS"          color="#52b788"              content={recommandations} isRecommendations />}
              {tempsEstime   && <ReportSection icon="◷" title="TEMPS ESTIMÉ DE RÉSOLUTION" color="#f9c74f"             content={tempsEstime} />}
              {!cause && !explication && !recommandations && (
                <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "12px", padding: "18px", fontSize: "13px", lineHeight: 1.7, color: "#d1d5db", whiteSpace: "pre-line" }}>
                  {analysis}
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: "center", padding: "40px", color: "#6b7280", fontSize: "13px" }}>
              <div style={{ fontSize: "30px", marginBottom: "12px" }}>⏳</div>
              <div>Rapport IA non encore généré.</div>
            </div>
          )}

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginTop: "18px" }}>
            {typeAnalysis?.rag_used && (
              <span style={{ background: "rgba(0,150,199,0.12)", color: "#0096c7", padding: "4px 12px", borderRadius: "20px", fontSize: "10px", fontWeight: 600 }}>🧠 Enrichi par RAG</span>
            )}
            {typeAnalysis?.count > 1 && (
              <span style={{ background: "rgba(244,162,97,0.12)", color: "#f4a261", padding: "4px 12px", borderRadius: "20px", fontSize: "10px", fontWeight: 600 }}>📊 Corrélé avec {typeAnalysis.count} anomalies</span>
            )}
            {typeAnalysis?.top_src_ips && Object.keys(typeAnalysis.top_src_ips).length > 0 && (
              <span style={{ background: "rgba(230,57,70,0.12)", color: "#e63946", padding: "4px 12px", borderRadius: "20px", fontSize: "10px", fontWeight: 600 }}>🌐 {Object.keys(typeAnalysis.top_src_ips).length} IP sources</span>
            )}
          </div>

          <details style={{ marginTop: "18px" }}>
            <summary style={{ fontSize: "11px", color: "#6b7280", cursor: "pointer", padding: "8px", userSelect: "none" }}>📋 Données brutes</summary>
            <pre style={{ fontSize: "10px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", padding: "12px", borderRadius: "8px", overflow: "auto", marginTop: "8px", color: "#8b95a8", lineHeight: 1.5 }}>
              {JSON.stringify({ ...anomaly, _analysis_ref: undefined }, null, 2)}
            </pre>
          </details>
        </div>
      </div>
      <style>{`@keyframes modalIn{from{opacity:0;transform:scale(.95) translateY(14px)}to{opacity:1;transform:scale(1) translateY(0)}}`}</style>
    </div>
  );
}

function ReportSection({ icon, title, color, content, isRecommendations }) {
  return (
    <div style={{ marginBottom: "18px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
        <span style={{ fontSize: "14px" }}>{icon}</span>
        <span style={{ fontSize: "10px", fontWeight: 700, color, letterSpacing: "1.5px" }}>{title}</span>
        <div style={{ flex: 1, height: "1px", background: `linear-gradient(90deg, ${color}35, transparent)` }} />
      </div>
      <div style={{
        background: "rgba(255,255,255,0.03)", border: `1px solid ${color}20`,
        borderLeft: `3px solid ${color}`, borderRadius: "0 10px 10px 0",
        padding: "14px 16px", fontSize: "13px", lineHeight: 1.75, color: "#d1d5db", whiteSpace: "pre-line",
      }}>
        {isRecommendations ? <FormattedRecommendations text={content} /> : content}
      </div>
    </div>
  );
}

function FormattedRecommendations({ text }) {
  const lines = text.split("\n").filter(Boolean);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "7px" }}>
      {lines.map((line, i) => {
        const isItem = line.match(/^[\*\-•]\s|Immédiat|Court terme|Prévention/i);
        return (
          <div key={i} style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
            {isItem && <span style={{ color: "#52b788", flexShrink: 0, marginTop: "2px" }}>▸</span>}
            <span style={{ color: isItem ? "#e2e8f0" : "#9ca3af" }}>{line.replace(/^[\*\-•]\s+/, "")}</span>
          </div>
        );
      })}
    </div>
  );
}

// ================================================================
// COMPOSANT PRINCIPAL
// ================================================================
export default function AnomalyDashboard() {
  const { user } = useContext(AuthContext);
  const token = user?.token || "";

  const [activePipeline, setActivePipeline]   = useState("firewall");
  const [results, setResults]                 = useState(null);
  const [status, setStatus]                   = useState(null);
  const [loading, setLoading]                 = useState(false);
  const [deleting, setDeleting]               = useState(false);
  const [error, setError]                     = useState(null);
  const [searchTerm, setSearchTerm]           = useState("");
  const [riskFilter, setRiskFilter]           = useState("all");
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);
  const [polling, setPolling]                 = useState(false);
  const [serverAvailable, setServerAvailable] = useState(true);
  const [viewMode, setViewMode]               = useState("all");
  const [currentPage, setCurrentPage]         = useState(1);
  const [sortBy, setSortBy]                   = useState("risk_desc");

  // On affiche TOUTES les anomalies — pas de limite arbitraire
  const PAGE_SIZE = 200;

  const pipelineConfig = PIPELINES.find(p => p.key === activePipeline);

  // ── API calls ────────────────────────────────────────────────
  const checkServer = useCallback(async () => {
    try { const r = await fetch(`${API_BASE}/xai/health`); setServerAvailable(r.ok); }
    catch { setServerAvailable(false); }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/xai/${activePipeline}/results`, { headers: authHeaders(token) });
      if (r.ok) { const data = await r.json(); setResults(data); setLoading(false); setPolling(false); return data; }
      return null;
    } catch { return null; }
  }, [activePipeline, token]);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/xai/${activePipeline}/status`, { headers: authHeaders(token) });
      if (r.ok) { const d = await r.json(); setStatus(d); return d; }
      return null;
    } catch { return null; }
  }, [activePipeline, token]);

  const startAnalysis = async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/xai/${activePipeline}/analyze`, { method: "POST", headers: authHeaders(token) });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || "Erreur serveur"); }
      setPolling(true);
    } catch (err) { setError(err.message); setLoading(false); }
  };

  const deleteResults = async () => {
    if (!window.confirm(`Supprimer les résultats IA pour "${pipelineConfig?.label}" ?`)) return;
    setDeleting(true); setError(null);
    try {
      const r = await fetch(`${API_BASE}/xai/${activePipeline}/results`, { method: "DELETE", headers: authHeaders(token) });
      if (r.ok) { setResults(null); setCurrentPage(1); setViewMode("all"); }
      else { const d = await r.json(); setError(d.detail || "Erreur lors de la suppression"); }
    } catch (e) { setError(e.message); }
    finally { setDeleting(false); }
  };

  // ── Polling ──────────────────────────────────────────────────
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      const st = await fetchStatus();
      if (st?.state === "done" || st?.state === "error") {
        clearInterval(interval); setPolling(false);
        await fetchResults(); setLoading(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, fetchStatus, fetchResults]);

  useEffect(() => {
    if (token) { checkServer(); fetchResults(); }
  }, [token, activePipeline]);

  // ── Données ──────────────────────────────────────────────────
  function getTypeAnalysis(anomaly) {
    if (!results?.type_analyses) return null;
    const atype = anomaly.Anomaly_type || anomaly.anomaly_type || "";
    return results.type_analyses[atype] || null;
  }

  const rawAnomalies  = results?.all_anomalies || [];
  const typeAnalyses  = results?.type_analyses  || {};
  const globalStats   = results?.global_stats   || {};
  const analysisReady = results && Object.keys(typeAnalyses).length > 0;

  let filtered = rawAnomalies.filter(a => {
    const risk  = a.Risk ?? a.risk ?? 0;
    const atype = a.Anomaly_type || a.anomaly_type || "";
    if (riskFilter !== "all") {
      const cfg  = RISK_CONFIG[riskFilter];
      const next = Object.values(RISK_CONFIG).find(c => c.min > cfg.min);
      if (risk < cfg.min) return false;
      if (next && risk >= next.min) return false;
    }
    if (searchTerm) {
      const t = searchTerm.toLowerCase();
      return (
        (a._id?.toLowerCase().includes(t)) ||
        (atype.toLowerCase().includes(t)) ||
        (a.Src_ip?.toLowerCase().includes(t)) ||
        (a.Dst_ip?.toLowerCase().includes(t)) ||
        (a.Firewall_rule_id?.toLowerCase().includes(t)) ||
        (a.event_id?.toLowerCase().includes(t))
      );
    }
    return true;
  });

  filtered = [...filtered].sort((a, b) => {
    const ra = a.Risk ?? a.risk ?? 0, rb = b.Risk ?? b.risk ?? 0;
    if (sortBy === "risk_desc") return rb - ra;
    if (sortBy === "risk_asc")  return ra - rb;
    if (sortBy === "type")      return (a.Anomaly_type || "").localeCompare(b.Anomaly_type || "");
    return 0;
  });

  const totalPages     = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pagedAnomalies = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const criticalCount  = filtered.filter(a => (a.Risk ?? a.risk ?? 0) >= 8).length;
  const highCount      = filtered.filter(a => { const r = a.Risk ?? a.risk ?? 0; return r >= 5 && r < 8; }).length;

  const handlePage = (p) => {
    setCurrentPage(Math.max(1, Math.min(totalPages, p)));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // ── Styles communs ───────────────────────────────────────────
  const cardStyle = {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: "12px",
  };

  const selectStyle = {
    padding: "8px 12px",
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "8px", color: "#e2e8f0",
    fontSize: "12px", cursor: "pointer",
    fontFamily: "inherit", outline: "none",
  };

  // ── Render ───────────────────────────────────────────────────
  return (
    <DashboardLayout>
      {/* Global CSS */}
      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes blink   { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
        @keyframes fadeIn  { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        .ano-row { transition: all 0.18s; }
        .ano-row:hover { background: rgba(255,255,255,0.065) !important; transform: translateX(3px); }
        .ano-btn:hover  { filter: brightness(1.15); }
        .tab-btn:hover  { border-color: rgba(255,255,255,0.2) !important; color: #e2e8f0 !important; }
        .del-btn:hover  { background: rgba(230,57,70,0.18) !important; }
        input::placeholder { color: #4b5563; }
        select option { background: #0d1424; color: #e2e8f0; }
        details summary::-webkit-details-marker { color: #6b7280; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 3px; }
      `}</style>

      {/* MODAL */}
      {selectedAnomaly && (
        <AIReportModal
          anomaly={selectedAnomaly}
          typeAnalysis={getTypeAnalysis(selectedAnomaly)}
          pipeline={activePipeline}
          onClose={() => setSelectedAnomaly(null)}
        />
      )}

      <div style={{ padding: "1.5rem", maxWidth: "1400px", margin: "0 auto", fontFamily: "'IBM Plex Mono','Fira Code',monospace", color: "#e2e8f0" }}>

        {/* ── HEADER ── */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "1.8rem" }}>
          <div style={{
            width: "46px", height: "46px", borderRadius: "13px",
            background: `linear-gradient(135deg, ${pipelineConfig?.color}25, ${pipelineConfig?.color}08)`,
            border: `1px solid ${pipelineConfig?.border}`,
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: "22px",
          }}>{pipelineConfig?.icon}</div>
          <div>
            <h1 style={{ fontSize: "21px", fontWeight: 700, margin: 0, color: "#f0f4ff", letterSpacing: "-0.4px" }}>
              Détection & Analyse des Anomalies
            </h1>
            <p style={{ margin: 0, fontSize: "11.5px", color: "#6b7280", marginTop: "3px" }}>
              Analyse IA par corrélation de type · Rapports personnalisés · Powered by Ollama + RAG
            </p>
          </div>
        </div>

        {/* ── SERVER WARNING ── */}
        {!serverAvailable && (
          <div style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.35)", color: "#e63946", padding: "12px 16px", borderRadius: "10px", marginBottom: "1.4rem", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "10px" }}>
            ⚠️ Serveur backend indisponible — vérifiez que FastAPI tourne sur le port 8000
          </div>
        )}

        {/* ── PIPELINE TABS ── */}
        <div style={{ display: "flex", gap: "7px", marginBottom: "1.4rem", flexWrap: "wrap" }}>
          {PIPELINES.map(p => (
            <button key={p.key} className="tab-btn"
              onClick={() => { setActivePipeline(p.key); setResults(null); setSearchTerm(""); setCurrentPage(1); }}
              style={{
                padding: "8px 17px",
                background: activePipeline === p.key ? p.bg : "rgba(255,255,255,0.03)",
                color: activePipeline === p.key ? p.color : "#6b7280",
                border: activePipeline === p.key ? `1px solid ${p.border}` : "1px solid rgba(255,255,255,0.07)",
                borderRadius: "8px", cursor: "pointer", fontWeight: 600,
                fontSize: "12px", display: "flex", alignItems: "center", gap: "6px",
                transition: "all 0.18s", fontFamily: "inherit",
              }}
            >
              <span style={{ fontSize: "14px" }}>{p.icon}</span> {p.label}
              {polling && activePipeline === p.key && (
                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: p.color, animation: "blink 1s infinite", flexShrink: 0 }} />
              )}
            </button>
          ))}
        </div>

        {/* ── ACTION BAR ── */}
        <div style={{ ...cardStyle, display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.4rem", flexWrap: "wrap", gap: "12px", padding: "13px 17px" }}>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>

            {/* Lancer analyse */}
            <button
              onClick={startAnalysis}
              disabled={loading || polling || !serverAvailable}
              className="ano-btn"
              style={{
                padding: "9px 18px", background: pipelineConfig?.color, color: "#fff",
                border: "none", borderRadius: "8px",
                cursor: (loading || polling || !serverAvailable) ? "not-allowed" : "pointer",
                fontWeight: 700, fontSize: "12px", display: "flex", alignItems: "center", gap: "8px",
                opacity: (loading || polling || !serverAvailable) ? 0.55 : 1, transition: "all 0.2s",
                fontFamily: "inherit",
              }}
            >
              {loading || polling ? <><Spinner />&nbsp;Analyse en cours...</> : <><span>🤖</span> Lancer l'analyse IA</>}
            </button>

            {/* Rafraîchir */}
            <button onClick={fetchResults} className="ano-btn" title="Rafraîchir" style={{ padding: "9px 13px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", cursor: "pointer", color: "#9ca3af", fontSize: "14px", transition: "all 0.2s", fontFamily: "inherit" }}>🔄</button>

            {/* Supprimer résultats */}
            {results && (
              <button
                onClick={deleteResults}
                disabled={deleting}
                className="del-btn ano-btn"
                title="Supprimer les résultats IA"
                style={{
                  padding: "9px 16px", background: "rgba(230,57,70,0.1)",
                  border: "1px solid rgba(230,57,70,0.35)", borderRadius: "8px",
                  cursor: deleting ? "not-allowed" : "pointer", color: "#e63946",
                  fontSize: "12px", fontWeight: 600, display: "flex", alignItems: "center", gap: "7px",
                  opacity: deleting ? 0.5 : 1, transition: "all 0.2s", fontFamily: "inherit",
                }}
              >
                {deleting ? <><Spinner size={13} color="#e63946" />&nbsp;Suppression...</> : <><span>🗑️</span> Supprimer résultats</>}
              </button>
            )}

            {/* Statut analyse */}
            {analysisReady && (
              <span style={{ display: "flex", alignItems: "center", gap: "6px", background: "rgba(82,183,136,0.1)", border: "1px solid rgba(82,183,136,0.3)", color: "#52b788", padding: "6px 12px", borderRadius: "8px", fontSize: "11px", fontWeight: 600 }}>
                ✅ Rapports IA disponibles · {Object.keys(typeAnalyses).length} types analysés
              </span>
            )}
          </div>

          <div style={{ display: "flex", gap: "7px", alignItems: "center", flexWrap: "wrap" }}>
            {/* Recherche */}
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: "11px", top: "50%", transform: "translateY(-50%)", color: "#6b7280", fontSize: "12px", pointerEvents: "none" }}>🔍</span>
              <input type="text" placeholder="ID, type, IP, règle..."
                value={searchTerm}
                onChange={e => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                style={{ ...selectStyle, width: "200px", paddingLeft: "32px" }}
              />
            </div>

            {/* Filtre risque */}
            <select value={riskFilter} onChange={e => { setRiskFilter(e.target.value); setCurrentPage(1); }} style={selectStyle}>
              <option value="all">Tous les risques</option>
              <option value="critical">🔴 Critique (≥ 8)</option>
              <option value="high">🟠 Élevé (5-7)</option>
              <option value="medium">🟡 Moyen (3-4)</option>
              <option value="low">🟢 Faible (0-2)</option>
            </select>

            {/* Tri */}
            <select value={sortBy} onChange={e => { setSortBy(e.target.value); setCurrentPage(1); }} style={selectStyle}>
              <option value="risk_desc">Risque ↓</option>
              <option value="risk_asc">Risque ↑</option>
              <option value="type">Type A-Z</option>
            </select>
          </div>
        </div>

        {/* ── PROGRESS BAR ── */}
        {polling && status?.progress !== undefined && (
          <div style={{ marginBottom: "1.4rem", animation: "fadeIn 0.3s ease" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px", fontSize: "11px", color: "#9ca3af" }}>
              <span>{status.message || "Analyse en cours..."}</span>
              <span style={{ color: pipelineConfig?.color, fontWeight: 700 }}>{status.progress}%</span>
            </div>
            <div style={{ height: "4px", background: "rgba(255,255,255,0.07)", borderRadius: "2px", overflow: "hidden" }}>
              <div style={{ width: `${status.progress}%`, height: "100%", background: pipelineConfig?.color, transition: "width 0.5s ease", borderRadius: "2px" }} />
            </div>
          </div>
        )}

        {/* ── STATS CARDS ── */}
        {results && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "9px", marginBottom: "1.4rem", animation: "fadeIn 0.4s ease" }}>
            {[
              { label: "Total Anomalies",  value: rawAnomalies.length,                                        color: "#f0f4ff",             icon: "📊" },
              { label: "Types détectés",   value: Object.keys(typeAnalyses).length || globalStats.types_count || 0, color: pipelineConfig?.color, icon: "🔖" },
              { label: "Critiques",        value: criticalCount,                                               color: "#e63946",             icon: "🔴" },
              { label: "Élevés",           value: highCount,                                                   color: "#f4a261",             icon: "🟠" },
              { label: "Risque moyen",     value: `${globalStats.avg_risk || globalStats.risk_avg || 0}/10`,   color: "#f9c74f",             icon: "⚠️" },
              { label: "Rapports IA",      value: Object.keys(typeAnalyses).length,                            color: "#52b788",             icon: "🤖" },
            ].map(stat => (
              <div key={stat.label} style={{ ...cardStyle, padding: "13px 15px" }}>
                <div style={{ fontSize: "10px", color: "#6b7280", display: "flex", alignItems: "center", gap: "5px", marginBottom: "5px" }}>
                  <span style={{ fontSize: "12px" }}>{stat.icon}</span>{stat.label}
                </div>
                <div style={{ fontSize: "22px", fontWeight: 700, color: stat.color }}>{stat.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* ── VIEW TOGGLE ── */}
        {results && (
          <div style={{ display: "flex", gap: "6px", marginBottom: "1rem" }}>
            {[
              { key: "all",   label: `📋 Toutes les anomalies (${rawAnomalies.length})` },
              { key: "types", label: `🔖 Par type (${Object.keys(typeAnalyses).length})` },
            ].map(v => (
              <button key={v.key} onClick={() => { setViewMode(v.key); setCurrentPage(1); }} style={{
                padding: "7px 15px", borderRadius: "8px", fontSize: "12px", fontWeight: 600, cursor: "pointer",
                background: viewMode === v.key ? pipelineConfig?.bg : "rgba(255,255,255,0.03)",
                color: viewMode === v.key ? pipelineConfig?.color : "#6b7280",
                border: viewMode === v.key ? `1px solid ${pipelineConfig?.border}` : "1px solid rgba(255,255,255,0.07)",
                transition: "all 0.18s", fontFamily: "inherit",
              }}>{v.label}</button>
            ))}
          </div>
        )}

        {/* ── VUE : TOUTES LES ANOMALIES ── */}
        {results && viewMode === "all" && (
          <div style={{ animation: "fadeIn 0.3s ease" }}>
            {/* Info + pagination haut */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
              <span style={{ fontSize: "11px", color: "#6b7280" }}>
                {filtered.length} anomalie(s) totales
                {searchTerm && ` · filtre: "${searchTerm}"`}
                {` · page ${currentPage}/${totalPages}`}
                {analysisReady && " · Cliquez sur Détail IA pour le rapport personnalisé"}
              </span>
              <Pagination currentPage={currentPage} totalPages={totalPages} onPage={handlePage} color={pipelineConfig?.color} />
            </div>

            {/* Liste */}
            <div style={{ display: "flex", flexDirection: "column", gap: "7px" }}>
              {pagedAnomalies.map(anomaly => {
                const risk      = anomaly.Risk ?? anomaly.risk ?? 0;
                const atype     = anomaly.Anomaly_type || anomaly.anomaly_type || "Type inconnu";
                const riskInfo  = getRiskLevel(risk);
                const hasReport = analysisReady && !!typeAnalyses[atype];

                return (
                  <div key={anomaly._id} className="ano-row" style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderLeft: `3px solid ${riskInfo.color}`,
                    borderRadius: "0 11px 11px 0", padding: "13px 17px",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    gap: "12px", flexWrap: "wrap",
                  }}>
                    <div style={{ flex: 1, minWidth: "220px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "7px", flexWrap: "wrap", marginBottom: "5px" }}>
                        <span style={{ fontSize: "13px", fontWeight: 700, color: "#e2e8f0" }}>{atype}</span>
                        <span style={{ background: riskInfo.color, color: "#fff", padding: "2px 10px", borderRadius: "20px", fontSize: "10px", fontWeight: 700 }}>
                          {riskInfo.label} {risk}/10
                        </span>
                        {hasReport && (
                          <span style={{ background: "rgba(82,183,136,0.12)", color: "#52b788", padding: "2px 8px", borderRadius: "20px", fontSize: "9px", fontWeight: 600 }}>
                            ✅ Rapport IA prêt
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: "10px", color: "#6b7280", display: "flex", gap: "12px", flexWrap: "wrap" }}>
                        <span>ID: <code style={{ color: "#8b95a8" }}>{(anomaly._id || "—").slice(0, 10)}...</code></span>
                        {anomaly.Src_ip           && <span>Src: <code style={{ color: "#8b95a8" }}>{anomaly.Src_ip}</code></span>}
                        {anomaly.Dst_ip           && <span>Dst: <code style={{ color: "#8b95a8" }}>{anomaly.Dst_ip}</code></span>}
                        {anomaly.Protocol         && <span><code style={{ color: "#8b95a8" }}>{anomaly.Protocol}</code></span>}
                        {anomaly.Firewall_rule_id && <span>Rule: <code style={{ color: "#8b95a8" }}>{anomaly.Firewall_rule_id}</code></span>}
                        {anomaly.timestamp        && <span>🕐 {new Date(anomaly.timestamp).toLocaleString("fr-FR")}</span>}
                      </div>
                    </div>

                    <button
                      className="ano-btn"
                      onClick={() => setSelectedAnomaly({ ...anomaly, anomaly_type: atype, risk, anomaly_id: anomaly._id })}
                      style={{
                        padding: "7px 15px", borderRadius: "8px", fontSize: "11px", fontWeight: 600, cursor: "pointer",
                        background: hasReport ? pipelineConfig?.bg : "rgba(255,255,255,0.05)",
                        color: hasReport ? pipelineConfig?.color : "#6b7280",
                        border: hasReport ? `1px solid ${pipelineConfig?.border}` : "1px solid rgba(255,255,255,0.1)",
                        transition: "all 0.18s", whiteSpace: "nowrap", fontFamily: "inherit",
                      }}
                    >
                      {hasReport ? "🤖 Détail IA →" : "📋 Détail →"}
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Pagination bas */}
            {totalPages > 1 && (
              <div style={{ display: "flex", justifyContent: "center", marginTop: "20px" }}>
                <Pagination currentPage={currentPage} totalPages={totalPages} onPage={handlePage} color={pipelineConfig?.color} />
              </div>
            )}

            {filtered.length === 0 && rawAnomalies.length > 0 && (
              <div style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
                <div style={{ fontSize: "26px", marginBottom: "10px" }}>🔍</div>
                <div style={{ fontSize: "13px" }}>Aucune anomalie ne correspond aux filtres</div>
              </div>
            )}
          </div>
        )}

        {/* ── VUE : PAR TYPE ── */}
        {results && viewMode === "types" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "13px", animation: "fadeIn 0.3s ease" }}>
            {Object.entries(typeAnalyses).map(([atype, typeData]) => {
              const riskInfo        = getRiskLevel(typeData.risk_avg || 0);
              const anomaliesOfType = rawAnomalies.filter(a => (a.Anomaly_type || a.anomaly_type) === atype);

              return (
                <div key={atype} className="ano-row" style={{
                  background: "rgba(255,255,255,0.03)",
                  border: `1px solid ${riskInfo.color}22`,
                  borderTop: `3px solid ${riskInfo.color}`,
                  borderRadius: "0 0 13px 13px", padding: "17px",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 700, color: "#e2e8f0", marginBottom: "5px" }}>{atype}</div>
                      <div style={{ display: "flex", gap: "7px", flexWrap: "wrap" }}>
                        <span style={{ background: riskInfo.bg, color: riskInfo.color, padding: "2px 10px", borderRadius: "20px", fontSize: "10px", fontWeight: 700 }}>
                          {riskInfo.label} {typeData.risk_avg}/10 moy
                        </span>
                        <span style={{ background: "rgba(255,255,255,0.07)", color: "#9ca3af", padding: "2px 10px", borderRadius: "20px", fontSize: "10px" }}>
                          {typeData.count} événements
                        </span>
                      </div>
                    </div>
                    {typeData.rag_used && (
                      <span style={{ background: "rgba(0,150,199,0.1)", color: "#0096c7", padding: "3px 8px", borderRadius: "6px", fontSize: "9px", fontWeight: 700 }}>🧠 RAG</span>
                    )}
                  </div>

                  {typeData.full_analysis && (
                    <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: "8px", padding: "11px", marginBottom: "11px", fontSize: "11px", color: "#9ca3af", lineHeight: 1.6, maxHeight: "70px", overflow: "hidden", position: "relative" }}>
                      {typeData.full_analysis.slice(0, 180)}...
                      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "28px", background: "linear-gradient(transparent, #0a0f1e)" }} />
                    </div>
                  )}

                  {typeData.top_src_ips && Object.keys(typeData.top_src_ips).length > 0 && (
                    <div style={{ marginBottom: "11px" }}>
                      <div style={{ fontSize: "10px", color: "#6b7280", marginBottom: "4px" }}>IP Sources :</div>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                        {Object.keys(typeData.top_src_ips).slice(0, 3).map(ip => (
                          <code key={ip} style={{ background: "rgba(230,57,70,0.1)", color: "#e63946", padding: "2px 8px", borderRadius: "4px", fontSize: "10px" }}>{ip}</code>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ display: "flex", gap: "7px" }}>
                    <button className="ano-btn" onClick={() => {
                      const first = anomaliesOfType[0];
                      if (first) setSelectedAnomaly({ ...first, anomaly_type: atype, risk: typeData.risk_avg, anomaly_id: first._id });
                    }} style={{
                      flex: 1, padding: "8px 12px", borderRadius: "8px",
                      background: pipelineConfig?.bg, color: pipelineConfig?.color,
                      border: `1px solid ${pipelineConfig?.border}`,
                      cursor: "pointer", fontSize: "11px", fontWeight: 600,
                      transition: "all 0.18s", fontFamily: "inherit",
                    }}>🤖 Voir rapport IA</button>
                    <div style={{ padding: "8px 12px", background: "rgba(255,255,255,0.04)", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.07)", fontSize: "11px", color: "#6b7280" }}>
                      {anomaliesOfType.length} cas
                    </div>
                  </div>
                </div>
              );
            })}

            {Object.keys(typeAnalyses).length === 0 && (
              <div style={{ gridColumn: "1/-1", textAlign: "center", padding: "40px", color: "#6b7280" }}>
                <div style={{ fontSize: "26px", marginBottom: "10px" }}>🤖</div>
                <div style={{ fontSize: "13px" }}>Lancez l'analyse IA pour générer les rapports par type</div>
              </div>
            )}
          </div>
        )}

        {/* ── ÉTAT VIDE ── */}
        {!results && !loading && !polling && (
          <div style={{ textAlign: "center", padding: "70px 20px", color: "#6b7280", animation: "fadeIn 0.4s ease" }}>
            <div style={{ width: "70px", height: "70px", borderRadius: "18px", margin: "0 auto 18px", background: pipelineConfig?.bg, border: `1px solid ${pipelineConfig?.border}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "30px" }}>
              {pipelineConfig?.icon}
            </div>
            <div style={{ fontSize: "15px", fontWeight: 600, color: "#9ca3af", marginBottom: "8px" }}>Aucune donnée chargée</div>
            <div style={{ fontSize: "12px", maxWidth: "340px", margin: "0 auto", lineHeight: 1.7 }}>
              Cliquez sur <strong style={{ color: pipelineConfig?.color }}>Lancer l'analyse IA</strong> pour détecter et analyser toutes les anomalies du pipeline <strong style={{ color: "#e2e8f0" }}>{pipelineConfig?.label}</strong>.
            </div>
          </div>
        )}

        {results && rawAnomalies.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px", color: "#6b7280" }}>
            <div style={{ fontSize: "38px", marginBottom: "14px" }}>✅</div>
            <div style={{ fontSize: "14px", color: "#9ca3af" }}>Aucune anomalie détectée dans ce pipeline</div>
          </div>
        )}

        {/* ── ERROR ── */}
        {error && (
          <div style={{ background: "rgba(230,57,70,0.1)", border: "1px solid rgba(230,57,70,0.35)", color: "#e63946", padding: "13px 17px", borderRadius: "10px", marginTop: "16px", fontSize: "12.5px", display: "flex", alignItems: "center", gap: "10px" }}>
            ❌ {error}
            <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", color: "#e63946", cursor: "pointer", fontSize: "14px", padding: "0" }}>✕</button>
          </div>
        )}

      </div>
    </DashboardLayout>
  );
}