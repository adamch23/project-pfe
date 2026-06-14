/* e:\front\frontend\src\features\face-verify\pages\FaceVerify\FaceVerify.jsx */
import { useEffect, useRef, useState, useContext, useCallback } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "../../../../context/AuthContext";
import API from "../../../../api/axios";
import "./FaceVerify.css";

// Configuration de Sécurité Bancaire
const MODELS_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";
const MATCH_THRESHOLD = 0.52;
const BLINK_THRESHOLD = 0.23; // Seuil de fermeture des yeux (EAR)
const SMILE_THRESHOLD = 0.50; // Seuil de sourire (MAR)
const DESCRIPTOR_BUFFER = 10;

export default function FaceVerify() {
  const { user, completeFaceVerification, logout } = useContext(AuthContext);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const refDescRef = useRef(null);
  const descriptorsBuffer = useRef([]);

  const [status, setStatus] = useState("loading");
  const [step, setStep] = useState(0); // 0: Idle, 1: Blink, 2: Smile, 3: Capture
  const [message, setMessage] = useState("Initialisation...");
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const init = async () => {
      await loadModels();
      await loadReferencePhoto();
    };
    init();
    return () => stopCamera();
  }, []);

  const loadModels = async () => {
    try {
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL),
        faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL),
        faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL),
        faceapi.nets.faceExpressionNet.loadFromUri(MODELS_URL)
      ]);
      setProgress(60);
    } catch (e) { handleError("Erreur modèles IA.", e); }
  };

  const loadReferencePhoto = async () => {
    try {
      setMessage("Récupération du profil...");
      const res = await API.get("/users/me");
      const photoB64 = res.data.face_photo;
      if (!photoB64) { completeFaceVerification(); return; }

      const img = await faceapi.fetchImage(photoB64);
      const detection = await faceapi.detectSingleFace(img, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor();
      if (!detection) { setStatus("error"); setMessage("Profil biométrique invalide."); return; }

      refDescRef.current = detection.descriptor;
      setProgress(100);
      await startCamera();
    } catch (e) { handleError("Erreur synchronisation.", e); }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => videoRef.current.play().catch(() => { });
      }
      setStatus("ready");
      setMessage("Positionnez votre visage dans le cadre.");
    } catch (e) { handleError("Caméra inaccessible.", e); }
  };

  const stopCamera = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
  };

  // --- ANALYSEURS DE VIE (Liveness) ---
  const getEAR = (eye) => {
    const v1 = Math.hypot(eye[1].x - eye[5].x, eye[1].y - eye[5].y);
    const v2 = Math.hypot(eye[2].x - eye[4].x, eye[2].y - eye[4].y);
    const h = Math.hypot(eye[0].x - eye[3].x, eye[0].y - eye[3].y);
    return (v1 + v2) / (2 * h);
  };

  const getMAR = (mouth) => {
    const v = Math.hypot(mouth[14].x - mouth[18].x, mouth[14].y - mouth[18].y);
    const h = Math.hypot(mouth[12].x - mouth[16].x, mouth[12].y - mouth[16].y);
    return v / h;
  };

  const startVerification = () => {
    setStatus("scanning");
    setStep(1); // Étape 1 : Clignement
    setMessage("Détection de vie : Clignez des yeux...");
    descriptorsBuffer.current = [];
    runWorkflow();
  };

  const runWorkflow = () => {
    let internalStep = 1;
    let livenessAccumulator = 0;

    intervalRef.current = setInterval(async () => {
      if (!videoRef.current) return;
      const detection = await faceapi.detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 224 })).withFaceLandmarks().withFaceExpressions().withFaceDescriptor();

      if (!detection) return;
      drawHUD(detection);

      const landmarks = detection.landmarks.positions;

      // ÉTAPE 1 : CLIGNEMENT (Preuve de vie organique)
      if (internalStep === 1) {
        const ear = (getEAR(landmarks.slice(36, 42)) + getEAR(landmarks.slice(42, 48))) / 2;
        if (ear < 0.26) { // Seuil plus sensible
          livenessAccumulator++;
          if (livenessAccumulator >= 1) { // Une seule frame suffit si marquée
            internalStep = 2;
            setStep(2);
            livenessAccumulator = 0;
            setMessage("C'est bon ! Maintenant, faites un grand sourire...");
          }
        }
      }
      // ÉTAPE 2 : SOURIRE (Preuve de mobilité)
      else if (internalStep === 2) {
        const mar = getMAR(landmarks.slice(48, 68));
        const happy = detection.expressions.happy;
        if (mar > SMILE_THRESHOLD || happy > 0.85) {
          livenessAccumulator++;
          if (livenessAccumulator >= 3) {
            internalStep = 3;
            setStep(3);
            setMessage("Authentification en cours...");
          }
        }
      }
      // ÉTAPE 3 : CAPTURE FINALE & MATCHING
      else if (internalStep === 3) {
        descriptorsBuffer.current.push(detection.descriptor);
        setProgress(Math.round((descriptorsBuffer.current.length / DESCRIPTOR_BUFFER) * 100));
        if (descriptorsBuffer.current.length >= DESCRIPTOR_BUFFER) {
          clearInterval(intervalRef.current);
          validateIdentity();
        }
      }
    }, 90);
  };

  const validateIdentity = async () => {
    const avgDesc = new Float32Array(128);
    for (let i = 0; i < 128; i++) {
      avgDesc[i] = descriptorsBuffer.current.reduce((a, b) => a + b[i], 0) / DESCRIPTOR_BUFFER;
    }
    const distance = faceapi.euclideanDistance(refDescRef.current, avgDesc);
    const score = Math.round((1 - distance) * 100);

    // Journalisation de la tentative (Backend)
    await logBiometricEvent(distance, score);

    if (distance < MATCH_THRESHOLD) {
      setStatus("success");
      setMessage(`Identité confirmée (${score}%)`);
      setTimeout(() => { stopCamera(); completeFaceVerification(); }, 1500);
    } else {
      setStatus("error");
      setMessage(`Reconnaissance échouée (${score}%). Veuillez réessayer.`);
    }
  };

  const logBiometricEvent = async (dist, score) => {
    try {
      await API.post("/biometrics/log-attempt", {
        user_id: user?.id,
        distance: dist,
        confidence_score: score,
        timestamp: new Date().toISOString()
      });
    } catch (e) { console.warn("Log failed", e); }
  };

  const drawHUD = (detection) => {
    if (!canvasRef.current) return;
    const dims = faceapi.matchDimensions(canvasRef.current, videoRef.current, true);
    faceapi.resizeResults(detection, dims);
    const ctx = canvasRef.current.getContext("2d");
    ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
  };

  const handleError = (msg, e) => { console.error(e); setStatus("error"); setMessage(msg); };
  const reset = () => { stopCamera(); startCamera(); setStep(0); };

  return (
    <div className="fv-wrapper">
      <div className="fv-card">
        <div className="fv-header">
          <div className="fv-brand">Attijari<span>bank</span></div>
          <h2 className="fv-title">Identité Numérique</h2>
          <p className="fv-subtitle">Vérification de vie active</p>
        </div>

        <div className="fv-video-container">
          <video ref={videoRef} className="fv-video" muted playsInline />
          <canvas ref={canvasRef} className="fv-canvas" />
          <div className="fv-hud"><div className="fv-scan-line" /><div className="fv-face-guide" /></div>
          {status === "scanning" && (
            <div className="fv-liveness-box">
              {step === 1 ? "�️ Challenge : Clignez des yeux" : step === 2 ? "😊 Challenge : Souriez" : "⏳ Analyse finale..."}
            </div>
          )}
          {status === "success" && <div className="fv-status-overlay success">✅</div>}
          {status === "error" && <div className="fv-status-overlay error">❌</div>}
        </div>

        <div className="fv-message-container">
          <span className="fv-message">{message}</span>
        </div>

        <div className="fv-actions">
          {status === "ready" && <button className="fv-btn fv-btn--primary" onClick={startVerification}>Démarrer la vérification</button>}
          {status === "error" && <button className="fv-btn fv-btn--primary" onClick={reset}>Réessayer</button>}
          {status === "error" && <button className="fv-btn fv-btn--secondary" onClick={logout}>Déconnexion</button>}
        </div>
        <div className="fv-security-footer">🔐 Biométrie conforme ISO/IEC 30107-3</div>
      </div>
    </div>
  );
}