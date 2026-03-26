import { useState, useEffect, useRef, useContext } from "react";
import * as faceapi from "@vladmandic/face-api";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import API from "../api/axios";
import "./PersonalInfo.css";

const MODELS_URL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/";

const PASSWORD_RULES = [
  { id: "length",  label: "8+ caractères",        test: p => p.length >= 8 },
  { id: "upper",   label: "Majuscule",             test: p => /[A-Z]/.test(p) },
  { id: "lower",   label: "Minuscule",             test: p => /[a-z]/.test(p) },
  { id: "digit",   label: "Chiffre",               test: p => /\d/.test(p) },
  { id: "special", label: "Caractère spécial",     test: p => /[@$!%*?&._\-#]/.test(p) },
];

function extractError(err) {
  const d = err.response?.data;
  if (!d) return "Erreur réseau.";
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) return d.detail.map(x => x.msg).join(" | ");
  return "Une erreur est survenue.";
}

function Toast({ msg, type, onClose }) {
  useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t); }, []);
  return (
    <div className={`pi-toast pi-toast--${type}`}>
      <span>{type === "success" ? "✔" : "⚠"}</span> {msg}
      <button className="pi-toast-close" onClick={onClose}>×</button>
    </div>
  );
}

export default function PersonalInfo() {
  const { user, updateUserContext } = useContext(AuthContext);

  // ── Profile state ──────────────────────────────────────────────
  const [profile,        setProfile]        = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  // ── Edit info ─────────────────────────────────────────────────
  const [editMode,   setEditMode]   = useState(false);
  const [firstName,  setFirstName]  = useState("");
  const [lastName,   setLastName]   = useState("");
  const [email,      setEmail]      = useState("");
  const [savingInfo, setSavingInfo] = useState(false);

  // ── Password ──────────────────────────────────────────────────
  const [oldPassword,   setOldPassword]   = useState("");
  const [newPassword,   setNewPassword]   = useState("");
  const [confirmPwd,    setConfirmPwd]    = useState("");
  const [savingPwd,     setSavingPwd]     = useState(false);
  const [showPwdRules,  setShowPwdRules]  = useState(false);

  // ── Face photo ────────────────────────────────────────────────
  const [facePhotoMode, setFacePhotoMode] = useState("view"); // view | capture | uploading
  const [modelsLoaded,  setModelsLoaded]  = useState(false);
  const [cameraActive,  setCameraActive]  = useState(false);
  const [capturedImage, setCapturedImage] = useState(null);
  const videoRef  = useRef(null);
  const streamRef = useRef(null);

  // ── Toast ─────────────────────────────────────────────────────
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => setToast({ msg, type });

  // ── Load profile ──────────────────────────────────────────────
  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    try {
      const res = await API.get("/users/me");
      setProfile(res.data);
      setFirstName(res.data.first_name || "");
      setLastName(res.data.last_name || "");
      setEmail(res.data.email || "");
    } catch (err) {
      showToast("Impossible de charger le profil.", "error");
    } finally {
      setLoadingProfile(false);
    }
  };

  // ── Save profile info ─────────────────────────────────────────
  const handleSaveInfo = async () => {
    if (!email.trim()) return showToast("L'email est requis.", "error");
    setSavingInfo(true);
    try {
      const res = await API.put("/users/me", { email, first_name: firstName, last_name: lastName });
      setProfile(res.data);
      const newName = (firstName && lastName)
        ? `${firstName} ${lastName}`
        : firstName || lastName || email;
      updateUserContext({ email: res.data.email, name: newName });
      setEditMode(false);
      showToast("Profil mis à jour avec succès !");
    } catch (err) {
      showToast(extractError(err), "error");
    } finally {
      setSavingInfo(false);
    }
  };

  // ── Change password ───────────────────────────────────────────
  const handleChangePassword = async () => {
    if (!oldPassword) return showToast("L'ancien mot de passe est requis.", "error");
    const failedRules = PASSWORD_RULES.filter(r => !r.test(newPassword));
    if (failedRules.length)
      return showToast(`Mot de passe faible : ${failedRules.map(r => r.label).join(", ")}`, "error");
    if (newPassword !== confirmPwd)
      return showToast("Les mots de passe ne correspondent pas.", "error");

    setSavingPwd(true);
    try {
      await API.put("/users/me/password", { old_password: oldPassword, new_password: newPassword });
      setOldPassword(""); setNewPassword(""); setConfirmPwd("");
      showToast("Mot de passe modifié avec succès !");
    } catch (err) {
      showToast(extractError(err), "error");
    } finally {
      setSavingPwd(false);
    }
  };

  // ── Face photo — charger modèles ──────────────────────────────
  const loadFaceModels = async () => {
    if (modelsLoaded) return true;
    try {
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL);
      await faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL);
      await faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL);
      setModelsLoaded(true);
      return true;
    } catch {
      showToast("Erreur lors du chargement des modèles IA.", "error");
      return false;
    }
  };

  // ── Face photo — démarrer la caméra ──────────────────────────
  const startFaceCapture = async () => {
    setFacePhotoMode("capture");
    setCapturedImage(null);
    showToast("Chargement des modèles IA...", "info");
    const ok = await loadFaceModels();
    if (!ok) { setFacePhotoMode("view"); return; }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: 480, height: 360 },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
      }
    } catch {
      showToast("Accès à la caméra refusé.", "error");
      setFacePhotoMode("view");
    }
  };

  const stopFaceCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  };

  // ── Face photo — capturer la photo ────────────────────────────
  // FIX : pas de miroir dans le canvas envoyé au backend.
  // Le miroir visuel est géré uniquement en CSS sur la balise <video>.
  const capturePhoto = async () => {
    if (!videoRef.current) return;

    const detection = await faceapi
      .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
      .withFaceLandmarks();

    if (!detection) {
      showToast("Aucun visage détecté. Positionnez-vous face à la caméra.", "error");
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width  = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext("2d");
    // Pas de transformation miroir — image normale pour le backend
    ctx.drawImage(videoRef.current, 0, 0);
    // Qualité augmentée à 0.95 pour une meilleure extraction des descripteurs
    const dataURL = canvas.toDataURL("image/jpeg", 0.95);
    setCapturedImage(dataURL);
    stopFaceCamera();
  };

  // ── Face photo — uploader la photo ────────────────────────────
  const uploadFacePhoto = async () => {
    if (!capturedImage) return;
    setFacePhotoMode("uploading");
    try {
      await API.post("/users/me/face-photo", { image: capturedImage });
      setProfile(prev => ({ ...prev, has_face_photo: true, face_photo: capturedImage }));
      updateUserContext({ has_face_photo: true });
      setCapturedImage(null);
      setFacePhotoMode("view");
      showToast("Photo de reconnaissance faciale enregistrée !");
    } catch (err) {
      showToast(extractError(err), "error");
      setFacePhotoMode("capture");
    }
  };

  // ── Face photo — supprimer ────────────────────────────────────
  const deleteFacePhoto = async () => {
    if (!window.confirm("Supprimer votre photo de reconnaissance faciale ?")) return;
    try {
      await API.delete("/users/me/face-photo");
      setProfile(prev => ({ ...prev, has_face_photo: false, face_photo: null }));
      updateUserContext({ has_face_photo: false });
      showToast("Photo supprimée.");
    } catch (err) {
      showToast(extractError(err), "error");
    }
  };

  // ── Upload depuis fichier ─────────────────────────────────────
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return showToast("Seules les images sont acceptées.", "error");

    const ok = await loadFaceModels();
    if (!ok) return;

    const reader = new FileReader();
    reader.onload = async (ev) => {
      const dataURL = ev.target.result;
      const img = await faceapi.fetchImage(dataURL);
      const detection = await faceapi
        .detectSingleFace(img, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks();

      if (!detection) {
        showToast("Aucun visage détecté dans cette image.", "error");
        return;
      }
      setCapturedImage(dataURL);
    };
    reader.readAsDataURL(file);
  };

  // ── Helpers UI ────────────────────────────────────────────────
  const initials = () => {
    if (profile?.first_name && profile?.last_name)
      return `${profile.first_name[0]}${profile.last_name[0]}`.toUpperCase();
    return (profile?.email || "?")[0].toUpperCase();
  };

  const displayName = () => {
    if (profile?.first_name || profile?.last_name)
      return `${profile.first_name || ""} ${profile.last_name || ""}`.trim();
    return profile?.email || "";
  };

  const roleBadge  = () => profile?.role === "admin" ? "Administrateur" : "Employé";
  const pwdRulesOk = PASSWORD_RULES.every(r => r.test(newPassword));

  if (loadingProfile) {
    return (
      <DashboardLayout>
        <div className="pi-loading">
          <div className="pi-spinner" /> Chargement du profil...
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="pi-page">

        {/* Toast notification */}
        {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

        {/* ── En-tête profil ── */}
        <div className="pi-hero">
          <div className="pi-avatar">{initials()}</div>
          <div className="pi-hero-info">
            <h1 className="pi-hero-name">{displayName()}</h1>
            <div className="pi-hero-meta">
              <span className={`pi-role-badge pi-role-badge--${profile?.role}`}>{roleBadge()}</span>
              <span className={`pi-status-badge ${profile?.is_active ? "pi-status-badge--active" : "pi-status-badge--inactive"}`}>
                {profile?.is_active ? "● Actif" : "● Inactif"}
              </span>
            </div>
            <p className="pi-hero-email">{profile?.email}</p>
          </div>
        </div>

        <div className="pi-grid">

          {/* ══ Section 1 : Informations personnelles ══ */}
          <div className="pi-card">
            <div className="pi-card-header">
              <h2>Informations personnelles</h2>
              {!editMode && (
                <button className="pi-btn-icon" onClick={() => setEditMode(true)} title="Modifier">
                  ✎ Modifier
                </button>
              )}
            </div>

            {!editMode ? (
              /* ── Vue lecture ── */
              <div className="pi-info-grid">
                <div className="pi-info-item">
                  <span className="pi-info-label">Prénom</span>
                  <span className="pi-info-value">{profile?.first_name || <em className="pi-empty">Non renseigné</em>}</span>
                </div>
                <div className="pi-info-item">
                  <span className="pi-info-label">Nom</span>
                  <span className="pi-info-value">{profile?.last_name || <em className="pi-empty">Non renseigné</em>}</span>
                </div>
                <div className="pi-info-item pi-info-item--full">
                  <span className="pi-info-label">Email</span>
                  <span className="pi-info-value">{profile?.email}</span>
                </div>
                <div className="pi-info-item">
                  <span className="pi-info-label">Rôle</span>
                  <span className="pi-info-value">{roleBadge()}</span>
                </div>
                <div className="pi-info-item">
                  <span className="pi-info-label">Statut</span>
                  <span className="pi-info-value">{profile?.is_active ? "Actif" : "Inactif"}</span>
                </div>
              </div>
            ) : (
              /* ── Mode édition ── */
              <div className="pi-form">
                <div className="pi-form-row">
                  <div className="pi-field">
                    <label>Prénom</label>
                    <input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="Votre prénom" />
                  </div>
                  <div className="pi-field">
                    <label>Nom</label>
                    <input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="Votre nom" />
                  </div>
                </div>
                <div className="pi-field">
                  <label>Email</label>
                  <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="votre@email.com" />
                </div>
                <div className="pi-form-actions">
                  <button className="pi-btn pi-btn--primary" onClick={handleSaveInfo} disabled={savingInfo}>
                    {savingInfo ? "Enregistrement..." : "Enregistrer"}
                  </button>
                  <button
                    className="pi-btn pi-btn--ghost"
                    onClick={() => {
                      setEditMode(false);
                      setFirstName(profile?.first_name || "");
                      setLastName(profile?.last_name || "");
                      setEmail(profile?.email || "");
                    }}
                  >
                    Annuler
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ══ Section 2 : Reconnaissance faciale ══ */}
          <div className="pi-card">
            <div className="pi-card-header">
              <h2>Reconnaissance faciale</h2>
              <span className={`pi-face-badge ${profile?.has_face_photo ? "pi-face-badge--on" : "pi-face-badge--off"}`}>
                {profile?.has_face_photo ? "● Activée" : "○ Non activée"}
              </span>
            </div>

            <p className="pi-face-desc">
              {profile?.has_face_photo
                ? "Votre reconnaissance faciale est activée. Lors de la connexion, une vérification de votre visage sera demandée."
                : "Activez la reconnaissance faciale pour sécuriser davantage votre compte. Une vérification faciale sera requise à chaque connexion."}
            </p>

            {/* Aperçu de la photo actuelle */}
            {profile?.face_photo && facePhotoMode === "view" && (
              <div className="pi-face-preview">
                <img src={profile.face_photo} alt="Photo de référence" className="pi-face-img" />
              </div>
            )}

            {/* Mode view — boutons d'action */}
            {facePhotoMode === "view" && (
              <div className="pi-face-actions">
                <button className="pi-btn pi-btn--primary" onClick={startFaceCapture}>
                  📷 {profile?.has_face_photo ? "Mettre à jour la photo" : "Ajouter une photo"}
                </button>
                <label className="pi-btn pi-btn--secondary pi-btn--file">
                  📁 Importer une image
                  <input type="file" accept="image/*" onChange={handleFileUpload} style={{ display: "none" }} />
                </label>
                {profile?.has_face_photo && (
                  <button className="pi-btn pi-btn--danger" onClick={deleteFacePhoto}>
                    🗑 Supprimer
                  </button>
                )}
              </div>
            )}

            {/* Mode capture caméra */}
            {facePhotoMode === "capture" && (
              <div className="pi-webcam-container">
                {!capturedImage ? (
                  <>
                    <div className="pi-webcam-wrap">
                      {/* FIX : miroir CSS uniquement pour l'affichage — le canvas capturé est normal */}
                      <video ref={videoRef} className="pi-webcam pi-webcam--mirror" muted playsInline />
                      <div className="pi-webcam-guide" />
                    </div>
                    <div className="pi-face-actions">
                      {cameraActive && (
                        <button className="pi-btn pi-btn--primary" onClick={capturePhoto}>
                          📸 Capturer
                        </button>
                      )}
                      <button
                        className="pi-btn pi-btn--ghost"
                        onClick={() => { stopFaceCamera(); setFacePhotoMode("view"); setCapturedImage(null); }}
                      >
                        Annuler
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="pi-face-preview">
                      <img src={capturedImage} alt="Aperçu" className="pi-face-img" />
                    </div>
                    <div className="pi-face-actions">
                      <button className="pi-btn pi-btn--primary" onClick={uploadFacePhoto}>
                        ✔ Utiliser cette photo
                      </button>
                      <button className="pi-btn pi-btn--ghost" onClick={() => { setCapturedImage(null); startFaceCapture(); }}>
                        Reprendre
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Uploading */}
            {facePhotoMode === "uploading" && (
              <div className="pi-uploading">
                <div className="pi-spinner" /> Enregistrement de la photo...
              </div>
            )}

            {/* Photo importée depuis fichier — confirmation */}
            {capturedImage && facePhotoMode === "view" && (
              <div className="pi-face-confirm">
                <div className="pi-face-preview">
                  <img src={capturedImage} alt="Aperçu" className="pi-face-img" />
                </div>
                <div className="pi-face-actions">
                  <button className="pi-btn pi-btn--primary" onClick={uploadFacePhoto}>
                    ✔ Enregistrer cette photo
                  </button>
                  <button className="pi-btn pi-btn--ghost" onClick={() => setCapturedImage(null)}>
                    Annuler
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ══ Section 3 : Changer le mot de passe ══ */}
          <div className="pi-card pi-card--full">
            <div className="pi-card-header">
              <h2>Changer le mot de passe</h2>
            </div>

            <div className="pi-form">
              <div className="pi-form-row">
                <div className="pi-field">
                  <label>Mot de passe actuel</label>
                  <input
                    type="password"
                    value={oldPassword}
                    onChange={e => setOldPassword(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
              </div>
              <div className="pi-form-row">
                <div className="pi-field">
                  <label>Nouveau mot de passe</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    onFocus={() => setShowPwdRules(true)}
                    placeholder="••••••••"
                    style={{ borderColor: newPassword ? (pwdRulesOk ? "#2ecc71" : "#e74c3c") : undefined }}
                  />
                  {showPwdRules && newPassword && (
                    <div className="pi-pwd-rules">
                      {PASSWORD_RULES.map(r => (
                        <span
                          key={r.id}
                          className={`pi-pwd-rule ${r.test(newPassword) ? "pi-pwd-rule--ok" : "pi-pwd-rule--fail"}`}
                        >
                          {r.test(newPassword) ? "✔" : "✖"} {r.label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="pi-field">
                  <label>Confirmer le mot de passe</label>
                  <input
                    type="password"
                    value={confirmPwd}
                    onChange={e => setConfirmPwd(e.target.value)}
                    placeholder="••••••••"
                    style={{ borderColor: confirmPwd ? (confirmPwd === newPassword ? "#2ecc71" : "#e74c3c") : undefined }}
                  />
                  {confirmPwd && (
                    <span style={{ fontSize: "12px", color: confirmPwd === newPassword ? "#2ecc71" : "#e74c3c", marginTop: "4px", display: "block" }}>
                      {confirmPwd === newPassword ? "✔ Correspondance" : "✖ Ne correspond pas"}
                    </span>
                  )}
                </div>
              </div>
              <div className="pi-form-actions">
                <button className="pi-btn pi-btn--primary" onClick={handleChangePassword} disabled={savingPwd}>
                  {savingPwd ? "Modification..." : "Modifier le mot de passe"}
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </DashboardLayout>
  );
}