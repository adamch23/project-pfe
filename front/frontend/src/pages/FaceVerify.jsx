import { useEffect, useRef, useState, useContext } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "../context/AuthContext";
import API from "../api/axios";
import "./FaceVerify.css";

const MODELS_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";
const MATCH_THRESHOLD = 0.5; // distance euclidienne — plus bas = plus strict

export default function FaceVerify() {
  const { user, completeFaceVerification, logout } = useContext(AuthContext);
  const videoRef    = useRef(null);
  const canvasRef   = useRef(null);
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);

  const [status,      setStatus]      = useState("loading"); // loading | ready | scanning | success | error
  const [message,     setMessage]     = useState("Chargement des modèles IA...");
  const [progress,    setProgress]    = useState(0);
  const [attempts,    setAttempts]    = useState(0);
  const [refDescriptor, setRefDescriptor] = useState(null);
  const MAX_ATTEMPTS = 5;

  // ── 1. Charger les modèles face-api.js ───────────────────────
  useEffect(() => {
    loadModels();
    return () => stopCamera();
  }, []);

  const loadModels = async () => {
    try {
      setMessage("Chargement des modèles IA (1/3)...");
      setProgress(10);
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL);
      setProgress(40);
      setMessage("Chargement des modèles IA (2/3)...");
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL);
      setProgress(70);
      setMessage("Chargement des modèles IA (3/3)...");
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL);
      setProgress(90);

      // ── 2. Récupérer la photo de référence depuis l'API ──────
      await loadReferencePhoto();
    } catch (err) {
      setStatus("error");
      setMessage("Erreur lors du chargement des modèles IA. Vérifiez votre connexion.");
    }
  };

  const loadReferencePhoto = async () => {
    try {
      setMessage("Récupération de votre photo de référence...");
      const res = await API.get("/users/me");
      const photoB64 = res.data.face_photo;

      if (!photoB64) {
        // Pas de photo → passer directement au dashboard
        completeFaceVerification();
        return;
      }

      // Créer un élément image à partir du base64
      const img = await faceapi.fetchImage(photoB64);
      const detection = await faceapi
        .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (!detection) {
        setStatus("error");
        setMessage("Impossible d'extraire les caractéristiques faciales de votre photo de référence. Veuillez la mettre à jour dans votre profil.");
        return;
      }

      setRefDescriptor(detection.descriptor);
      setProgress(100);
      await startCamera();
    } catch (err) {
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
    } catch (err) {
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
    if (status !== "ready" || !refDescriptor) return;
    setStatus("scanning");
    setMessage("Analyse en cours... Regardez la caméra");
    setAttempts(0);
    runDetectionLoop();
  };

  const runDetectionLoop = () => {
    let tries = 0;
    intervalRef.current = setInterval(async () => {
      tries++;
      setAttempts(tries);

      if (!videoRef.current || videoRef.current.readyState < 2) return;

      try {
        const detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 320 }))
          .withFaceLandmarks()
          .withFaceDescriptor();

        // Dessiner le cadre de détection
        if (canvasRef.current && detection) {
          const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
          const resized = faceapi.resizeResults(detection, dims);
          const ctx = canvasRef.current.getContext("2d");
          ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
          faceapi.draw.drawDetections(canvasRef.current, resized);
        }

        if (detection) {
          const distance = faceapi.euclideanDistance(refDescriptor, detection.descriptor);

          if (distance < MATCH_THRESHOLD) {
            // ✅ Correspondance !
            clearInterval(intervalRef.current);
            stopCamera();
            setStatus("success");
            setMessage(`Identité confirmée ! (score : ${(1 - distance).toFixed(2)})`);
            setTimeout(() => completeFaceVerification(), 1500);
          } else if (tries >= MAX_ATTEMPTS) {
            // ❌ Trop de tentatives
            clearInterval(intervalRef.current);
            setStatus("error");
            setMessage(`Échec de la reconnaissance faciale après ${MAX_ATTEMPTS} tentatives.`);
          }
        } else if (tries >= MAX_ATTEMPTS) {
          clearInterval(intervalRef.current);
          setStatus("error");
          setMessage("Aucun visage détecté. Assurez-vous d'être bien éclairé et face à la caméra.");
        }
      } catch (err) {
        console.error("Detection error:", err);
      }
    }, 800);
  };

  const handleRetry = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setStatus("ready");
    setMessage("Positionnez votre visage dans le cadre et appuyez sur Vérifier");
    setAttempts(0);
    if (canvasRef.current) {
      const ctx = canvasRef.current.getContext("2d");
      ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    }
    if (!streamRef.current) startCamera();
  };

  return (
    <div className="fv-wrapper">
      <div className="fv-card">
        {/* Header */}
        <div className="fv-header">
          <div className="fv-brand">Attijari<span>bank</span></div>
          <h2 className="fv-title">Vérification Faciale</h2>
          <p className="fv-subtitle">Authentification biométrique sécurisée</p>
        </div>

        {/* Barre de progression (loading uniquement) */}
        {status === "loading" && (
          <div className="fv-progress-bar">
            <div className="fv-progress-fill" style={{ width: `${progress}%` }} />
          </div>
        )}

        {/* Zone vidéo */}
        {status !== "loading" && (
          <div className="fv-video-container">
            <video ref={videoRef} className="fv-video" muted playsInline />
            <canvas ref={canvasRef} className="fv-canvas" />

            {/* Overlay selon l'état */}
            {status === "success" && (
              <div className="fv-overlay fv-overlay--success">
                <div className="fv-checkmark">✓</div>
              </div>
            )}
            {status === "error" && (
              <div className="fv-overlay fv-overlay--error">
                <div className="fv-crossmark">✕</div>
              </div>
            )}

            {/* Cadre de guidage */}
            {(status === "ready" || status === "scanning") && (
              <div className={`fv-face-guide ${status === "scanning" ? "fv-face-guide--scanning" : ""}`} />
            )}
          </div>
        )}

        {/* Message d'état */}
        <div className={`fv-message fv-message--${status}`}>
          {status === "loading" && <span className="fv-spinner" />}
          {message}
        </div>

        {/* Compteur de tentatives */}
        {status === "scanning" && (
          <div className="fv-attempts">
            Tentative {attempts} / {MAX_ATTEMPTS}
          </div>
        )}

        {/* Boutons d'action */}
        <div className="fv-actions">
          {status === "ready" && (
            <button className="fv-btn fv-btn--primary" onClick={startVerification}>
              <span>👁</span> Vérifier mon identité
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

        <p className="fv-security-note">
          🔒 La vérification est effectuée localement — aucune image n'est transmise
        </p>
      </div>
    </div>
  );
}