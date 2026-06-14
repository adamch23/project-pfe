import React, { useState, useEffect } from 'react';
import DashboardLayout from "../../../layouts/DashboardLayout/DashboardLayout";
import './MonitoringDashboard.css';

/**
 * MonitoringDashboard Component
 * Embeds a Grafana dashboard with premium styling, loading states, and connectivity checks.
 */
const MonitoringDashboard = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  const grafanaUrl = "http://localhost:3000/d/pfe_ia_monitoring/pfe-2026-ia-monitoring?orgId=1&from=now-5m&to=now&timezone=browser&var-server=localhost:9182&refresh=auto&kiosk=true";
  const healthUrl = "http://localhost:3000/api/health"; // Grafana health check

  useEffect(() => {
    const checkGrafana = async () => {
      // Give Grafana a bit of time to initialize on the first try
      if (retryCount === 0) await new Promise(r => setTimeout(r, 3000));

      try {
        await fetch(healthUrl, { mode: 'no-cors' });
        setError(null);
      } catch (err) {
        setError("Le serveur Grafana est injoignable. Assurez-vous que le backend a bien lancé la stack de monitoring.");
      }
    };

    checkGrafana();
  }, [retryCount]);

  const handleLoad = () => {
    setIsLoading(false);
  };

  return (
    <DashboardLayout>
      <div className="monitoring-container">
        <header className="monitoring-header">
          <div className="title-group">
            <h1>Supervision IA & Infrastructure</h1>
            <p>Métriques de performance en temps réel — PFE 2026</p>
          </div>
          <button
            className="refresh-btn"
            onClick={() => {
              setIsLoading(true);
              setRetryCount(prev => prev + 1);
            }}
          >
            Actualiser
          </button>
        </header>

        <div className="dashboard-wrapper">
          {isLoading && !error && (
            <div className="loading-overlay">
              <div className="spinner"></div>
              <p>Chargement des données de monitoring...</p>
            </div>
          )}

          {error ? (
            <div className="error-container">
              <div className="error-icon">⚠️</div>
              <h2>Erreur de Connexion</h2>
              <p>{error}</p>
              <button className="retry-btn" onClick={() => setRetryCount(prev => prev + 1)}>
                Réessayer la connexion
              </button>
            </div>
          ) : (
            <iframe
              id="grafana-iframe"
              src={grafanaUrl}
              onLoad={handleLoad}
              title="Grafana Dashboard"
            />
          )}
        </div>
      </div>
    </DashboardLayout>
  );
};

export default MonitoringDashboard;
