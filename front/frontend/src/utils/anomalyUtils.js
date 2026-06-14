import { RISK_CONFIG } from "../config/constants";

export const getRiskLevel = (risk) => {
  for (const [level, config] of Object.entries(RISK_CONFIG)) {
    if (risk >= config.min) return { level, ...config };
  }
  return { level: "low", ...RISK_CONFIG.low };
};

export const parseAnalysisSection = (text, label) => {
  if (!text) return null;
  const patterns = [
    new RegExp(`${label}\\s*[:\\-]?\\s*([\\s\\S]*?)(?=\\n(?:Explication|Recommandations|Temps estimé|la Cause|$))`, "i"),
    new RegExp(`${label}\\s*[:\\-]?\\s*([\\s\\S]*?)(?=\\n\\n|$)`, "i"),
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]?.trim()) return match[1].trim();
  }
  return null;
};
