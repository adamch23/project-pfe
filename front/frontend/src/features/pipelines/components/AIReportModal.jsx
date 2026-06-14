import React from "react";
import { getRiskLevel } from "../../../utils/anomalyUtils";
import { PIPELINES } from "../../../config/constants";

const FormattedRecommendations = ({ text }) => {
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
};

const ReportSection = ({ icon, title, color, content, isRecommendations }) => {
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
};

const AIReportModal = ({ anomaly, typeAnalysis, pipeline, onClose }) => {
  const riskInfo = getRiskLevel(anomaly?.risk || 0);
  const pipelineConfig = PIPELINES.find(p => p.key === pipeline);
  const analysis = typeAnalysis?.full_analysis || "";

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

  const cause = parseSection(analysis, "la Cause") || parseSection(analysis, "Cause");
  const explication = parseSection(analysis, "Explication");
  const tempsEstime = (() => { const m = analysis.match(/Temps estimé[^:]*:([\s\S]*?)(?=\n\n|$)/i); return m?.[1]?.trim() || null; })();
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
                {anomaly.timestamp && <span>🕐 {new Date(anomaly.timestamp).toLocaleString("fr-FR")}</span>}
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
                { label: "Événements similaires", value: typeAnalysis.count, color: pipelineConfig?.color },
                { label: "Risque moyen", value: `${typeAnalysis.risk_avg}/10`, color: riskInfo.color },
                { label: "Risque max", value: `${typeAnalysis.risk_max}/10`, color: "#e63946" },
                { label: "Critiques", value: typeAnalysis.critical_count || 0, color: "#e63946" },
                { label: "Génération LLM", value: `${typeAnalysis.generation_time || 0}s`, color: "#0096c7" },
                { label: "Analyse Pertinente", value: typeAnalysis.is_pertinent ? "Oui" : "Partielle", color: typeAnalysis.is_pertinent ? "#52b788" : "#f4a261" },
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
              {cause && <ReportSection icon="⚑" title="LA CAUSE" color={riskInfo.color} content={cause} />}
              {explication && <ReportSection icon="◎" title="EXPLICATION TECHNIQUE" color="#0096c7" content={explication} />}
              {recommandations && <ReportSection icon="✓" title="RECOMMANDATIONS" color="#52b788" content={recommandations} isRecommendations />}
              {tempsEstime && <ReportSection icon="◷" title="TEMPS ESTIMÉ DE RÉSOLUTION" color="#f9c74f" content={tempsEstime} />}
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
};

export default AIReportModal;
