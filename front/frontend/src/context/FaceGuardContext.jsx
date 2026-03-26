/**
 * FaceGuardContext.jsx
 * ─────────────────────────────────────────────────────────────
 * Gère la surveillance faciale continue dans toute l'application.
 * - Charge les modèles face-api une seule fois
 * - Surveille la webcam en arrière-plan toutes les 800ms
 * - Expose : isGuardActive, isBlocked, toggleGuard
 * ─────────────────────────────────────────────────────────────
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "./AuthContext";
import API from "../api/axios";

const MODELS_URL      = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";
const SCAN_INTERVAL   = 800;   // ms entre chaque détection
const ABSENT_TIMEOUT  = 5000;  // ms sans visage avant blocage
const STORAGE_KEY     = "faceGuardEnabled";

export const FaceGuardContext = createContext(null);

export function FaceGuardProvider({ children }) {
  const { user } = useContext(AuthContext);

  // ── État ──────────────────────────────────────────────────────
  const [isGuardActive,  setIsGuardActive]  = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved !== null ? JSON.parse(saved) : true; // activé par défaut
  });
  const [isBlocked,      setIsBlocked]      = useState(false);
  const [modelsLoaded,   setModelsLoaded]   = useState(false);
  const [guardReady,     setGuardReady]     = useState(false); // modèles + photo chargés
  const [hasFacePhoto,   setHasFacePhoto]   = useState(false);

  // ── Refs (ne déclenchent pas de re-render) ────────────────────
  const videoRef        = useRef(null);
  const streamRef       = useRef(null);
  const intervalRef     = useRef(null);
  const absentTimerRef  = useRef(null);
  const refDescriptor   = useRef(null);
  const isBlockedRef    = useRef(false);
  const isActiveRef     = useRef(isGuardActive);

  // Sync ref avec state
  useEffect(() => { isActiveRef.current = isGuardActive; }, [isGuardActive]);
  useEffect(() => { isBlockedRef.current = isBlocked; }, [isBlocked]);

  // ── Charger les modèles ───────────────────────────────────────
  const loadModels = useCallback(async () => {
    if (modelsLoaded) return true;
    try {
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL);
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL);
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL);
      setModelsLoaded(true);
      return true;
    } catch {
      return false;
    }
  }, [modelsLoaded]);

  // ── Charger le descripteur de référence ───────────────────────
  const loadRefDescriptor = useCallback(async () => {
    try {
      const res = await API.get("/users/me");
      const photoB64 = res.data.face_photo;
      setHasFacePhoto(!!photoB64);
      if (!photoB64) return false;

      const img = await faceapi.fetchImage(photoB64);
      const detection = await faceapi
        .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (!detection) return false;
      refDescriptor.current = detection.descriptor;
      return true;
    } catch {
      return false;
    }
  }, []);

  // ── Démarrer la webcam ────────────────────────────────────────
  const startCamera = useCallback(async () => {
    if (streamRef.current) return; // déjà active
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: "user" }
      });
      streamRef.current = stream;

      // Créer un élément video caché
      if (!videoRef.current) {
        const v = document.createElement("video");
        v.setAttribute("playsinline", "");
        v.setAttribute("muted", "");
        v.style.display = "none";
        document.body.appendChild(v);
        videoRef.current = v;
      }
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      return true;
    } catch {
      return false;
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (intervalRef.current)    clearInterval(intervalRef.current);
    if (absentTimerRef.current) clearTimeout(absentTimerRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.remove();
      videoRef.current = null;
    }
    intervalRef.current    = null;
    absentTimerRef.current = null;
  }, []);

  // ── Boucle de détection ───────────────────────────────────────
  const startDetectionLoop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(async () => {
      if (!isActiveRef.current) return;
      if (!videoRef.current || videoRef.current.readyState < 2) return;
      if (!refDescriptor.current) return;

      try {
        const detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 224 }))
          .withFaceLandmarks()
          .withFaceDescriptor();

        if (detection) {
          const distance = faceapi.euclideanDistance(refDescriptor.current, detection.descriptor);

          if (distance < 0.5) {
            // ✅ Visage reconnu — débloquer si nécessaire
            if (absentTimerRef.current) {
              clearTimeout(absentTimerRef.current);
              absentTimerRef.current = null;
            }
            if (isBlockedRef.current) {
              setIsBlocked(false);
            }
          } else {
            // Visage détecté mais pas reconnu → traiter comme absent
            handleFaceAbsent();
          }
        } else {
          // Aucun visage
          handleFaceAbsent();
        }
      } catch {
        // silencieux
      }
    }, SCAN_INTERVAL);
  }, []);

  const handleFaceAbsent = () => {
    if (absentTimerRef.current) return; // timer déjà en cours
    absentTimerRef.current = setTimeout(() => {
      if (isActiveRef.current) {
        setIsBlocked(true);
      }
      absentTimerRef.current = null;
    }, ABSENT_TIMEOUT);
  };

  // ── Initialisation quand l'utilisateur est connecté ───────────
  useEffect(() => {
    if (!user) return;

    const init = async () => {
      const modelsOk = await loadModels();
      if (!modelsOk) return;

      const refOk = await loadRefDescriptor();
      if (!refOk) return; // pas de photo → pas de surveillance

      const camOk = await startCamera();
      if (!camOk) return;

      setGuardReady(true);
      if (isGuardActive) startDetectionLoop();
    };

    init();

    return () => stopCamera();
  }, [user]);

  // ── Réagir aux changements d'activation ───────────────────────
  useEffect(() => {
    if (!guardReady) return;

    if (isGuardActive) {
      if (!streamRef.current) {
        startCamera().then(ok => { if (ok) startDetectionLoop(); });
      } else {
        startDetectionLoop();
      }
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (absentTimerRef.current) clearTimeout(absentTimerRef.current);
      setIsBlocked(false);
    }
  }, [isGuardActive, guardReady]);

  // ── Toggle guard ──────────────────────────────────────────────
  const toggleGuard = useCallback(() => {
    setIsGuardActive(prev => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  return (
    <FaceGuardContext.Provider value={{
      isGuardActive,
      isBlocked,
      hasFacePhoto,
      guardReady,
      toggleGuard,
    }}>
      {children}
    </FaceGuardContext.Provider>
  );
}

export function useFaceGuard() {
  return useContext(FaceGuardContext);
}