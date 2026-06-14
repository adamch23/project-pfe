/**
 * FaceGuardContext.jsx — Version améliorée
 * Seuil plus tolérant + grace period + multi-inputSize
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "./AuthContext";
import API from "../api/axios";

const MODELS_URL      = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";
const SCAN_INTERVAL   = 800;
const ABSENT_TIMEOUT  = 5000;
const GRACE_PERIOD    = 6000;
const MATCH_THRESHOLD = 0.58;
const STORAGE_KEY     = "faceGuardEnabled";

export const FaceGuardContext = createContext(null);

export function FaceGuardProvider({ children }) {
  const { user } = useContext(AuthContext);

  const [isGuardActive, setIsGuardActive] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [isBlocked,    setIsBlocked]    = useState(false);
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [guardReady,   setGuardReady]   = useState(false);
  const [hasFacePhoto, setHasFacePhoto] = useState(false);

  const videoRef       = useRef(null);
  const streamRef      = useRef(null);
  const intervalRef    = useRef(null);
  const absentTimerRef = useRef(null);
  const graceTimerRef  = useRef(null);
  const refDescriptor  = useRef(null);
  const isBlockedRef   = useRef(false);
  const isActiveRef    = useRef(isGuardActive);
  const graceActiveRef = useRef(true);

  useEffect(() => { isActiveRef.current  = isGuardActive; }, [isGuardActive]);
  useEffect(() => { isBlockedRef.current = isBlocked; },     [isBlocked]);

  const loadModels = useCallback(async () => {
    if (modelsLoaded) return true;
    try {
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL);
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL);
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL);
      setModelsLoaded(true);
      return true;
    } catch { return false; }
  }, [modelsLoaded]);

  const loadRefDescriptor = useCallback(async () => {
    try {
      const res = await API.get("/users/me");
      const photoB64 = res.data.face_photo;
      setHasFacePhoto(!!photoB64);
      if (!photoB64) return false;

      const img = await faceapi.fetchImage(photoB64);
      let detection = await faceapi
        .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.3 }))
        .withFaceLandmarks().withFaceDescriptor();

      if (!detection) {
        detection = await faceapi
          .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 608, scoreThreshold: 0.2 }))
          .withFaceLandmarks().withFaceDescriptor();
      }

      if (!detection) return false;
      refDescriptor.current = detection.descriptor;
      return true;
    } catch { return false; }
  }, []);

  const startCamera = useCallback(async () => {
    if (streamRef.current) return true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: "user" }
      });
      streamRef.current = stream;
      if (!videoRef.current) {
        const v = document.createElement("video");
        v.setAttribute("playsinline", "");
        v.setAttribute("muted", "");
        v.style.cssText = "position:fixed;opacity:0;pointer-events:none;width:1px;height:1px;top:0;left:0;";
        document.body.appendChild(v);
        videoRef.current = v;
      }
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      return true;
    } catch { return false; }
  }, []);

  const stopCamera = useCallback(() => {
    if (intervalRef.current)    clearInterval(intervalRef.current);
    if (absentTimerRef.current) clearTimeout(absentTimerRef.current);
    if (graceTimerRef.current)  clearTimeout(graceTimerRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.remove();
      videoRef.current = null;
    }
    intervalRef.current = absentTimerRef.current = graceTimerRef.current = null;
  }, []);

  const detectFace = async () => {
    if (!videoRef.current || videoRef.current.readyState < 2) return null;
    let d = await faceapi
      .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.3 }))
      .withFaceLandmarks().withFaceDescriptor();
    if (!d) {
      d = await faceapi
        .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.2 }))
        .withFaceLandmarks().withFaceDescriptor();
    }
    return d;
  };

  const handleFaceAbsent = () => {
    if (graceActiveRef.current || absentTimerRef.current) return;
    absentTimerRef.current = setTimeout(() => {
      if (isActiveRef.current) setIsBlocked(true);
      absentTimerRef.current = null;
    }, ABSENT_TIMEOUT);
  };

  const startDetectionLoop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      if (!isActiveRef.current || !refDescriptor.current) return;
      try {
        const detection = await detectFace();
        if (detection) {
          const distance = faceapi.euclideanDistance(refDescriptor.current, detection.descriptor);
          if (distance < MATCH_THRESHOLD) {
            if (absentTimerRef.current) { clearTimeout(absentTimerRef.current); absentTimerRef.current = null; }
            if (isBlockedRef.current) setIsBlocked(false);
          } else {
            handleFaceAbsent();
          }
        } else {
          handleFaceAbsent();
        }
      } catch { /* silencieux */ }
    }, SCAN_INTERVAL);
  }, []);

  const startGrace = () => {
    graceActiveRef.current = true;
    if (graceTimerRef.current) clearTimeout(graceTimerRef.current);
    graceTimerRef.current = setTimeout(() => { graceActiveRef.current = false; }, GRACE_PERIOD);
  };

  useEffect(() => {
    if (!user) return;
    const init = async () => {
      if (!await loadModels())        return;
      if (!await loadRefDescriptor()) return;
      if (!await startCamera())       return;
      setGuardReady(true);
      startGrace();
      if (isGuardActive) startDetectionLoop();
    };
    init();
    return () => stopCamera();
  }, [user]);

  useEffect(() => {
    if (!guardReady) return;
    if (isGuardActive) {
      startGrace();
      if (!streamRef.current) {
        startCamera().then(ok => { if (ok) startDetectionLoop(); });
      } else {
        startDetectionLoop();
      }
    } else {
      if (intervalRef.current)    clearInterval(intervalRef.current);
      if (absentTimerRef.current) clearTimeout(absentTimerRef.current);
      if (graceTimerRef.current)  clearTimeout(graceTimerRef.current);
      setIsBlocked(false);
    }
  }, [isGuardActive, guardReady]);

  const toggleGuard = useCallback(() => {
    setIsGuardActive(prev => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  return (
    <FaceGuardContext.Provider value={{ isGuardActive, isBlocked, hasFacePhoto, guardReady, toggleGuard }}>
      {children}
    </FaceGuardContext.Provider>
  );
}

export function useFaceGuard() {
  return useContext(FaceGuardContext);
}