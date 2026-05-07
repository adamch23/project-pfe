import { useEffect, useRef, useState, useContext } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "../context/AuthContext";
import API from "../api/axios";
import "./FaceVerify.css";

const MODELS_URL      = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";
const MATCH_THRESHOLD = 0.55;  // distance euclidienne — plus strict
const MAX_ATTEMPTS    = 8;     // plus de tentatives pour être généreux
const SCAN_INTERVAL   = 600;   // ms — plus réactif

export default function FaceVerify() {
  const { user, completeFaceVerification, logout } = useContext(AuthContext);

  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);
  const refDescRef  = useRef(null); // stocké en ref pour éviter les stale closures

  const [status,    setStatus]    = useState("loading");
  const [message,   setMessage]   = useState("Chargement des modèles IA...");
  const [progress,  setProgress]  = useState(0);
  const [attempts,  setAttempts]  = useState(0);
  const [bestScore, setBestScore] = useState(null); // meilleur score obtenu

  // ── 1. Charger les modèles ─────────────────────────────────────
  useEffect(() => {
    loadModels();
    return () => stopCamera();
  }, []);

  const loadModels = async () => {
    try {
      setProgress(5);
      setMessage("Initialisation des modèles IA (1/3)...");
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL);
      setProgress(35);
      setMessage("Chargement du détecteur facial (2/3)...");
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL);
      setProgress(65);
      setMessage("Chargement du modèle de reconnaissance (3/3)...");
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL);
      setProgress(85);
      await loadReferencePhoto();
    } catch {
      setStatus("error");
      setMessage("Erreur lors du chargement des modèles IA. Vérifiez votre connexion.");
    }
  };

  // ── 2. Charger la photo de référence ──────────────────────────
  const loadReferencePhoto = async () => {
    try {
      setMessage("Récupération de votre photo de référence...");
      const res = await API.get("/users/me");
      const photoB64 = res.data.face_photo;

      if (!photoB64) {
        completeFaceVerification();
        return;
      }

      // Essayer avec plusieurs options de détection pour plus de robustesse
      const img = await faceapi.fetchImage(photoB64);

      let detection = null;

      // Tentative 1 : TinyFaceDetector standard
      detection = await faceapi
        .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.3 }))
        .withFaceLandmarks()
        .withFaceDescriptor();

      // Tentative 2 : seuil plus bas si pas détecté
      if (!detection) {
        detection = await faceapi
          .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 608, scoreThreshold: 0.2 }))
          .withFaceLandmarks()
          .withFaceDescriptor();
      }

      if (!detection) {
        setStatus("error");
        setMessage("Impossible d'extraire les caractéristiques faciales de votre photo de référence. Veuillez la mettre à jour dans votre profil.");
        return;
      }

      refDescRef.current = detection.descriptor;
      setProgress(100);
      await startCamera();
    } catch {
      setStatus("error");
      setMessage("Erreur lors du chargement de votre photo de référence.");
    }
  };

  // ── 3. Démarrer la webcam ─────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus("ready");
      setMessage("Positionnez votre visage dans le cadre et appuyez sur Vérifier");
    } catch {
      setStatus("error");
      setMessage("Accès à la caméra refusé. Veuillez autoriser l'accès à la webcam.");
    }
  };

  const stopCamera = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  };

  // ── 4. Lancer la vérification ─────────────────────────────────
  const startVerification = () => {
    if (status !== "ready" || !refDescRef.current) return;
    setStatus("scanning");
    setMessage("Analyse en cours... Regardez la caméra");
    setAttempts(0);
    setBestScore(null);
    runDetectionLoop();
  };

  const runDetectionLoop = () => {
    let tries = 0;
    let best  = 1; // meilleure distance (plus bas = meilleur)

    intervalRef.current = setInterval(async () => {
      tries++;
      setAttempts(tries);

      if (!videoRef.current || videoRef.current.readyState < 2) return;

      try {
        // Essayer plusieurs tailles d'entrée pour plus de robustesse
        let detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.3 }))
          .withFaceLandmarks()
          .withFaceDescriptor();

        if (!detection) {
          detection = await faceapi
            .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.2 }))
            .withFaceLandmarks()
            .withFaceDescriptor();
        }

        // Dessiner le cadre de détection
        if (canvasRef.current && detection) {
          const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
          const resized = faceapi.resizeResults(detection, dims);
          const ctx = canvasRef.current.getContext("2d");
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
          faceapi.draw.drawDetections(canvasRef.current, resized);
        }

        if (detection && refDescRef.current) {
          const distance = faceapi.euclideanDistance(refDescRef.current, detection.descriptor);
          const score    = parseFloat((1 - distance).toFixed(3));

          if (distance < best) {
            best = distance;
            setBestScore(Math.round(score * 100));
          }

          if (distance < MATCH_THRESHOLD) {
            // ✅ Identité confirmée
            clearInterval(intervalRef.current);
            stopCamera();
            setStatus("success");
            setMessage(`Identité confirmée ! Score de confiance : ${Math.round(score * 100)}%`);
            setTimeout(() => completeFaceVerification(), 1800);
            return;
          }
        }

        // Fin des tentatives
        if (tries >= MAX_ATTEMPTS) {
          clearInterval(intervalRef.current);
          setStatus("error");
          if (best < 1) {
            setMessage(`Visage détecté mais non reconnu (score max : ${Math.round((1 - best) * 100)}%). Vérifiez l'éclairage et réessayez.`);
          } else {
            setMessage("Aucun visage détecté. Assurez-vous d'être bien éclairé et face à la caméra.");
          }
        }
      } catch (err) {
        console.error("Detection error:", err);
      }
    }, SCAN_INTERVAL);
  };

  const handleRetry = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setStatus("ready");
    setMessage("Positionnez votre visage dans le cadre et appuyez sur Vérifier");
    setAttempts(0);
    setBestScore(null);
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext("2d");
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    }
    if (!streamRef.current) startCamera();
  };

  // ── Barre de progression tentatives ─────────────────────────
  const attemptsPct = Math.round((attempts / MAX_ATTEMPTS) * 100);

  return (
    <div className="fv-wrapper">
      <div className="fv-card">

        {/* Header */}
        <div className="fv-header">
          <div className="fv-brand">Attijari<span>bank</span></div>
          <h2 className="fv-title">Vérification Faciale</h2>
          <p className="fv-subtitle">Authentification biométrique sécurisée</p>
        </div>

        {/* Barre de chargement */}
        {status === "loading" && (
          <div className="fv-progress-wrap">
            <div className="fv-progress-bar">
              <div className="fv-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="fv-progress-pct">{progress}%</span>
          </div>
        )}

        {/* Zone vidéo */}
        {status !== "loading" && (
          <div className="fv-video-container">
            <video ref={videoRef} className="fv-video" muted playsInline />
            <canvas ref={canvasRef} className="fv-canvas" />

            {/* Overlay succès */}
            {status === "success" && (
              <div className="fv-overlay fv-overlay--success">
                <div className="fv-result-icon">✓</div>
              </div>
            )}
            {/* Overlay erreur */}
            {status === "error" && (
              <div className="fv-overlay fv-overlay--error">
                <div className="fv-result-icon">✕</div>
              </div>
            )}

            {/* Cadre de guidage */}
            {(status === "ready" || status === "scanning") && (
              <div className={`fv-face-guide ${status === "scanning" ? "fv-face-guide--scanning" : ""}`} />
            )}

            {/* Score en temps réel */}
            {status === "scanning" && bestScore !== null && (
              <div className="fv-live-score">
                Score : {bestScore}%
              </div>
            )}
          </div>
        )}

        {/* Message d'état */}
        <div className={`fv-message fv-message--${status}`}>
          {status === "loading" && <span className="fv-spinner" />}
          {message}
        </div>

        {/* Barre de tentatives */}
        {status === "scanning" && (
          <div className="fv-attempts-wrap">
            <div className="fv-attempts-bar">
              <div className="fv-attempts-fill" style={{ width: `${attemptsPct}%` }} />
            </div>
            <span className="fv-attempts-label">Tentative {attempts} / {MAX_ATTEMPTS}</span>
          </div>
        )}

        {/* Boutons */}
        <div className="fv-actions">
          {status === "ready" && (
            <button className="fv-btn fv-btn--primary" onClick={startVerification}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              Vérifier mon identité
            </button>
          )}
          {status === "error" && (
            <>
              <button className="fv-btn fv-btn--primary" onClick={handleRetry}>
                Réessayer
              </button>
              <button className="fv-btn fv-btn--secondary" onClick={logout}>
                Se déconnecter
              </button>
            </>
          )}
          {status === "scanning" && (
            <button className="fv-btn fv-btn--secondary" onClick={handleRetry}>
              Annuler
            </button>
          )}
        </div>

        {/* Conseils */}
        {(status === "ready" || status === "error") && (
          <div className="fv-tips">
            <div className="fv-tip">💡 Bonne luminosité frontale</div>
            <div className="fv-tip">📐 Visage centré dans le cadre</div>
            <div className="fv-tip">👓 Retirez lunettes si besoin</div>
          </div>
        )}

        <p className="fv-security-note">
          🔒 Vérification locale — aucune image transmise à nos serveurs
        </p>
      </div>
    </div>
  );
}