export const API_BASE = "/api";

export const PIPELINES = [
  { key: "firewall", label: "Firewall / Réseau",   icon: "🛡️", color: "#e63946", bg: "rgba(230,57,70,0.15)",  border: "rgba(230,57,70,0.35)"  },
  { key: "os",       label: "OS & Infrastructure", icon: "💻", color: "#2d9e6b", bg: "rgba(45,158,107,0.15)", border: "rgba(45,158,107,0.35)" },
  { key: "app",      label: "Logs Applicatifs",    icon: "📱", color: "#9b5de5", bg: "rgba(155,93,229,0.15)", border: "rgba(155,93,229,0.35)" },
  { key: "apilogs",  label: "API Logs",            icon: "🔌", color: "#0096c7", bg: "rgba(0,150,199,0.15)",  border: "rgba(0,150,199,0.35)"  },
  { key: "database", label: "Base de Données",     icon: "🗄️", color: "#f4a261", bg: "rgba(244,162,97,0.15)", border: "rgba(244,162,97,0.35)" },
];

export const RISK_CONFIG = {
  critical: { min: 8, color: "#e63946", label: "CRITIQUE", icon: "🔴", bg: "rgba(230,57,70,0.12)",  border: "rgba(230,57,70,0.3)"  },
  high:     { min: 5, color: "#f4a261", label: "ÉLEVÉ",    icon: "🟠", bg: "rgba(244,162,97,0.12)", border: "rgba(244,162,97,0.3)" },
  medium:   { min: 3, color: "#f9c74f", label: "MOYEN",    icon: "🟡", bg: "rgba(249,199,79,0.12)", border: "rgba(249,199,79,0.3)" },
  low:      { min: 0, color: "#52b788", label: "FAIBLE",   icon: "🟢", bg: "rgba(82,183,136,0.12)", border: "rgba(82,183,136,0.3)" },
};
