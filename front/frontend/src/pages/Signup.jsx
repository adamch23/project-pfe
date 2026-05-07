import { useState, useEffect, useRef } from "react";
import API from "../api/axios";
import { useNavigate } from "react-router-dom";
import "./signup.css";
import BgImage from "../Images/Attijari_Bank_background.jpg";
import LogoImg from "../Images/Logo_Attijari_bank.png";

const PASSWORD_RULES = [
  { id: "length",  label: "Au moins 8 caractères",                        test: (p) => p.length >= 8 },
  { id: "upper",   label: "Au moins une majuscule",                        test: (p) => /[A-Z]/.test(p) },
  { id: "lower",   label: "Au moins une minuscule",                        test: (p) => /[a-z]/.test(p) },
  { id: "digit",   label: "Au moins un chiffre",                           test: (p) => /\d/.test(p) },
  { id: "special", label: "Caractère spécial (@$!%*?&._-#)",               test: (p) => /[@$!%*?&._\-#]/.test(p) },
];

function PasswordStrength({ password }) {
  if (!password) return null;
  const passed = PASSWORD_RULES.filter((r) => r.test(password)).length;
  const colors = ["#e74c3c", "#e67e22", "#f1c40f", "#27ae60", "#1e8449"];
  const labels = ["Très faible", "Faible", "Moyen", "Fort", "Très fort"];
  return (
    <div className="pwd-strength">
      <div className="pwd-bars">
        {PASSWORD_RULES.map((_, i) => (
          <div key={i} className="pwd-bar" style={{ background: i < passed ? colors[passed - 1] : "#e0e0e0" }} />
        ))}
      </div>
      <span className="pwd-label" style={{ color: colors[passed - 1] || "#999" }}>
        {labels[passed - 1] || ""}
      </span>
      <ul className="pwd-rules-list">
        {PASSWORD_RULES.map((rule) => {
          const ok = rule.test(password);
          return (
            <li key={rule.id} style={{ color: ok ? "#27ae60" : "#e74c3c" }}>
              {ok ? "✔" : "✖"} {rule.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Erreur lors de l'inscription";
}

export default function Signup() {
  const [firstName,       setFirstName]       = useState("");
  const [lastName,        setLastName]        = useState("");
  const [email,           setEmail]           = useState("");
  const [password,        setPassword]        = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message,         setMessage]         = useState("");
  const [isError,         setIsError]         = useState(false);
  const [loading,         setLoading]         = useState(false);
  const [showPwdRules,    setShowPwdRules]    = useState(false);
  const cardRef = useRef(null);
  const particlesRef = useRef(null);
  const navigate = useNavigate();

  // Effet 3D de rotation sur la carte
  useEffect(() => {
    const card = cardRef.current;
    if (!card) return;

    const handleMouseMove = (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = ((y - centerY) / centerY) * -8;
      const rotateY = ((x - centerX) / centerX) * 8;

      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;

      const glowX = (x / rect.width) * 100;
      const glowY = (y / rect.height) * 100;
      card.style.setProperty('--glow-x', `${glowX}%`);
      card.style.setProperty('--glow-y', `${glowY}%`);
    };

    const handleMouseLeave = () => {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)';
      card.style.removeProperty('--glow-x');
      card.style.removeProperty('--glow-y');
    };

    card.addEventListener('mousemove', handleMouseMove);
    card.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      card.removeEventListener('mousemove', handleMouseMove);
      card.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  // Effet de particules 3D
  useEffect(() => {
    if (!particlesRef.current) return;
    const canvas = particlesRef.current;
    const ctx = canvas.getContext('2d');
    let animationId;
    let particles = [];

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };

    class Particle3D {
      constructor(width, height) {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.z = Math.random() * 100;
        this.vx = (Math.random() - 0.5) * 0.5;
        this.vy = (Math.random() - 0.5) * 0.5;
        this.vz = (Math.random() - 0.5) * 0.3;
        this.size = 2;
        this.opacity = 0.3 + Math.random() * 0.5;
      }

      update(width, height) {
        this.x += this.vx;
        this.y += this.vy;
        this.z += this.vz;

        if (this.x < 0) this.x = width;
        if (this.x > width) this.x = 0;
        if (this.y < 0) this.y = height;
        if (this.y > height) this.y = 0;
        if (this.z < 0) this.z = 100;
        if (this.z > 100) this.z = 0;

        const scale = 1 + (this.z / 100);
        this.currentSize = this.size * scale;
      }

      draw(ctx, mouseX, mouseY) {
        const dx = this.x - mouseX;
        const dy = this.y - mouseY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        let opacityMultiplier = 1;

        if (distance < 100) {
          opacityMultiplier = 1 + (100 - distance) / 50;
          this.currentSize = this.size * (1 + (100 - distance) / 200);
        }

        const finalOpacity = Math.min(this.opacity * opacityMultiplier, 0.8);
        ctx.fillStyle = `rgba(255, 184, 28, ${finalOpacity})`;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.currentSize, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const initParticles = () => {
      particles = [];
      for (let i = 0; i < 150; i++) {
        particles.push(new Particle3D(canvas.width, canvas.height));
      }
    };

    let mouseX = canvas.width / 2;
    let mouseY = canvas.height / 2;

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(particle => {
        particle.update(canvas.width, canvas.height);
        particle.draw(ctx, mouseX, mouseY);
      });
      animationId = requestAnimationFrame(animate);
    };

    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    };

    const handleResize = () => {
      resizeCanvas();
      initParticles();
    };

    window.addEventListener('resize', handleResize);
    canvas.addEventListener('mousemove', handleMouseMove);

    resizeCanvas();
    initParticles();
    animate();

    return () => {
      cancelAnimationFrame(animationId);
      canvas.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const validateLocally = () => {
    if (!firstName.trim()) return "Le prénom est requis";
    if (!lastName.trim())  return "Le nom est requis";
    if (!email.trim())     return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
    const failedRules = PASSWORD_RULES.filter((r) => !r.test(password));
    if (failedRules.length > 0)
      return `Mot de passe invalide — ${failedRules.map((r) => r.label.toLowerCase()).join(", ")}`;
    if (password !== confirmPassword) return "Les mots de passe ne correspondent pas";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage(""); setIsError(false);
    const localError = validateLocally();
    if (localError) { setIsError(true); setMessage(localError); return; }
    setLoading(true);
    try {
      await API.post("/signup", {
        email,
        password,
        first_name: firstName.trim(),
        last_name:  lastName.trim(),
      });
      setIsError(false);
      setMessage("Inscription réussie ! Redirection...");
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setIsError(true);
      setMessage(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  const allRulesOk = PASSWORD_RULES.every((r) => r.test(password));

  return (
    <div className="signup-page-wrapper">
      {/* Canvas 3D pour les particules */}
      <canvas ref={particlesRef} className="particles-canvas-3d" />

      {/* ── Left decorative panel avec animations 3D ── */}
      <div className="signup-left" aria-hidden="true">
        <div className="signup-left-grid" />
        <div className="cube-3d-container">
          <div className="cube-3d">
            <div className="cube-face front"></div>
            <div className="cube-face back"></div>
            <div className="cube-face right"></div>
            <div className="cube-face left"></div>
            <div className="cube-face top"></div>
            <div className="cube-face bottom"></div>
          </div>
        </div>
        <div className="signup-left-inner">
          {/* LOGO */}
          <div className="signup-left-logo animated-logo">
            <img src={LogoImg} alt="Attijari bank" className="left-logo-img" />
          </div>
          <div className="signup-left-tagline">Portail Sécurisé</div>
          <div className="signup-left-bar" />
          <h2 className="signup-left-title floating-title">Rejoignez<br />la révolution IA</h2>
          <p className="signup-left-sub fade-in">
            Créez votre espace et bénéficiez d'outils d'analyse avancés pour la détection d'anomalies.
          </p>
          <div className="signup-left-dots">
            {[...Array(16)].map((_, i) => (
              <div
                key={i}
                className="signup-dot pulse-dot"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
          <div className="signup-left-features">
            <div className="signup-feat feat-3d">
              <div className="signup-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              Protection des données
            </div>
            <div className="signup-feat feat-3d">
              <div className="signup-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </div>
              Validation admin requise
            </div>
            <div className="signup-feat feat-3d">
              <div className="signup-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2"/>
                  <path d="M7 11V7a5 5 0 0110 0v4"/>
                </svg>
              </div>
              Chiffrement SSL 256-bit
            </div>
          </div>
        </div>
      </div>

      {/* ── Right form panel avec image de fond ── */}
      <div
        className="signup-right"
        style={{
          backgroundImage: `url(${BgImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="signup-card" ref={cardRef}>
          <div className="signup-top-bar">
            <div className="shimmer-effect"></div>
          </div>

          <div className="signup-header">
            {/* LOGO dans la carte */}
            <div className="signup-card-logo">
              <img src={LogoImg} alt="Attijari bank" className="card-logo-img" />
            </div>
            <h1 className="glitch-text" data-text="Inscription">Inscription</h1>
            <p>Créez votre espace sécurisé pour accéder à la plateforme</p>
          </div>

          <form onSubmit={handleSubmit} className="signup-form">

            <div className="signup-row">
              <div className="signup-field floating-label">
                <label>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  Prénom
                </label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Mohamed"
                  required
                  className="input-3d"
                />
              </div>
              <div className="signup-field floating-label">
                <label>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  Nom
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Ben Ali"
                  required
                  className="input-3d"
                />
              </div>
            </div>

            <div className="signup-field floating-label">
              <label>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
                Email Professionnel
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nom@attijari.tn"
                required
                className="input-3d"
              />
            </div>

            <div className="signup-field floating-label">
              <label>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2"/>
                  <path d="M7 11V7a5 5 0 0110 0v4"/>
                </svg>
                Mot de passe
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setShowPwdRules(true)}
                placeholder="••••••••"
                required
                className={`input-3d ${password ? (allRulesOk ? "input-valid" : "input-invalid") : ""}`}
              />
              {showPwdRules && <PasswordStrength password={password} />}
            </div>

            <div className="signup-field floating-label">
              <label>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="11" width="18" height="11" rx="2"/>
                  <path d="M7 11V7a5 5 0 0110 0v4"/>
                </svg>
                Confirmer le mot de passe
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                className={`input-3d ${confirmPassword ? (confirmPassword === password ? "input-valid" : "input-invalid") : ""}`}
              />
              {confirmPassword && (
                <span className={`input-match-msg ${confirmPassword === password ? "ok" : "fail"}`}>
                  {confirmPassword === password ? "✔ Correspondance" : "✖ Ne correspond pas"}
                </span>
              )}
            </div>

            {message && (
              <div className={`signup-error-box shake-animation ${isError ? "error" : "success"}`}>
                <span>{isError ? "⚠" : "✓"}</span> {message}
              </div>
            )}

            <button type="submit" disabled={loading} className="signup-btn btn-3d">
              {loading ? (
                <><span className="signup-spinner" /> Traitement en cours...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Créer mon espace
                </>
              )}
            </button>
          </form>

          <div className="signup-footer-links">
            <a href="/login" className="link-3d">Déjà inscrit ? Se connecter →</a>
          </div>

          <div className="signup-security pulse-security">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            Données protégées · SSL 256-bit · Validation admin requise
          </div>
        </div>
      </div>
    </div>
  );
}