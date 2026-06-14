import { useState, useEffect, useCallback } from "react";
import { anomalyService } from "../services/anomalyService";

export const useAnomalies = (activePipeline) => {
  const [results, setResults] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);
  const [polling, setPolling] = useState(false);
  const [serverAvailable, setServerAvailable] = useState(true);

  const checkServer = useCallback(async () => {
    try {
      const isAvailable = await anomalyService.checkHealth();
      setServerAvailable(isAvailable);
    } catch {
      setServerAvailable(false);
    }
  }, []);

  const fetchResults = useCallback(async () => {
    try {
      const data = await anomalyService.getResults(activePipeline);
      setResults(data);
      setLoading(false);
      setPolling(false);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }, [activePipeline]);

  const fetchStatus = useCallback(async () => {
    try {
      const d = await anomalyService.getStatus(activePipeline);
      setStatus(d);
      return d;
    } catch {
      return null;
    }
  }, [activePipeline]);

  const startAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      await anomalyService.startAnalysis(activePipeline);
      setPolling(true);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const deleteResults = async () => {
    setDeleting(true);
    setError(null);
    try {
      await anomalyService.deleteResults(activePipeline);
      setResults(null);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setDeleting(false);
    }
  };

  // Polling logic
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      const st = await fetchStatus();
      if (st?.state === "done" || st?.state === "error") {
        clearInterval(interval);
        setPolling(false);
        await fetchResults();
        setLoading(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, fetchStatus, fetchResults]);

  // Initial fetch
  useEffect(() => {
    checkServer();
    fetchResults();
  }, [activePipeline, checkServer, fetchResults]);

  return {
    results,
    status,
    loading,
    deleting,
    error,
    polling,
    serverAvailable,
    startAnalysis,
    deleteResults,
    refresh: fetchResults,
    setError,
  };
};
