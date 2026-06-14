import { API_BASE } from "../../../config/constants";

const authHeaders = (token) => ({
  Authorization: `Bearer ${token}`,
  "Content-Type": "application/json",
});

export const anomalyService = {
  checkHealth: async () => {
    const r = await fetch(`${API_BASE}/xai/health`);
    return r.ok;
  },

  getResults: async (pipeline, token) => {
    const r = await fetch(`${API_BASE}/xai/${pipeline}/results`, {
      headers: authHeaders(token),
    });
    if (!r.ok) throw new Error("Erreur lors de la récupération des résultats");
    return r.json();
  },

  getStatus: async (pipeline, token) => {
    const r = await fetch(`${API_BASE}/xai/${pipeline}/status`, {
      headers: authHeaders(token),
    });
    if (!r.ok) throw new Error("Erreur lors de la récupération du statut");
    return r.json();
  },

  startAnalysis: async (pipeline, token) => {
    const r = await fetch(`${API_BASE}/xai/${pipeline}/analyze`, {
      method: "POST",
      headers: authHeaders(token),
    });
    if (!r.ok) {
      const d = await r.json();
      throw new Error(d.detail || "Erreur serveur");
    }
    return r.json();
  },

  deleteResults: async (pipeline, token) => {
    const r = await fetch(`${API_BASE}/xai/${pipeline}/results`, {
      method: "DELETE",
      headers: authHeaders(token),
    });
    if (!r.ok) {
      const d = await r.json();
      throw new Error(d.detail || "Erreur lors de la suppression");
    }
    return true;
  },
};
