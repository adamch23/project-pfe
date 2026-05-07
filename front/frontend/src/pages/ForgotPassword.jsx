import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/axios";
import "./ForgotPassword.css";
import BgImage from "../Images/Attijari_Bank_background.jpg";
import LogoImg from "../Images/Logo_Attijari_bank.png";

function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Erreur lors de l'envoi du code.";
}

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const cardRef = useRef(null);
  const particlesRef = useRef(null);

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
    if (!email.trim()) return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    const localError = validateLocally();
    if (localError) {
      setError(localError);
      return;
    }

    setLoading(true);
    try {
      const res = await API.post("/forgot-password", { email });
      setMessage(res.data?.message || "Email envoyé avec succès !");
      setTimeout(() => navigate(`/reset-password?email=${encodeURIComponent(email)}`), 2000);
    } catch (err) {
      setError(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="forgot-page-wrapper">
      {/* Canvas 3D pour les particules */}
      <canvas ref={particlesRef} className="particles-canvas-3d" />

      {/* ── Left decorative panel avec animations 3D ── */}
      <div className="forgot-left" aria-hidden="true">
        <div className="forgot-left-grid" />
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
        <div className="forgot-left-inner">
          <div className="forgot-left-logo animated-logo">
            <img src={LogoImg} alt="Attijari bank" className="left-logo-img" />
          </div>
          <div className="forgot-left-tagline">Portail Sécurisé</div>
          <div className="forgot-left-bar" />
          <h2 className="forgot-left-title floating-title">Mot de passe<br />oublié ?</h2>
          <p className="forgot-left-sub fade-in">
            Ne vous inquiétez pas. Nous vous enverrons un code de vérification pour réinitialiser votre mot de passe.
          </p>
          <div className="forgot-left-dots">
            {[...Array(16)].map((_, i) => (
              <div
                key={i}
                className="forgot-dot pulse-dot"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
          <div className="forgot-left-features">
            <div className="forgot-feat feat-3d">
              <div className="forgot-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              Sécurité maximale
            </div>
            <div className="forgot-feat feat-3d">
              <div className="forgot-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </div>
              Code à 6 chiffres
            </div>
            <div className="forgot-feat feat-3d">
              <div className="forgot-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
        className="forgot-right"
        style={{
          backgroundImage: `url(${BgImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="forgot-card" ref={cardRef}>
          <div className="forgot-top-bar">
            <div className="shimmer-effect"></div>
          </div>

          <div className="forgot-header">
            <div className="forgot-card-logo">
              <img src={LogoImg} alt="Attijari bank" className="card-logo-img" />
            </div>
            <h1 className="glitch-text" data-text="Mot de passe oublié">Mot de passe oublié</h1>
            <p>Entrez votre email pour recevoir un code de vérification à 6 chiffres.</p>
          </div>

          <form onSubmit={handleSubmit} className="forgot-form">
            <div className="forgot-field floating-label">
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

            {error && (
              <div className="forgot-error-box shake-animation">
                <span>⚠</span> {error}
              </div>
            )}

            {message && (
              <div className="forgot-success-box">
                <span>✓</span> {message}
              </div>
            )}

            <button type="submit" disabled={loading} className="forgot-btn btn-3d">
              {loading ? (
                <><span className="forgot-spinner" /> Envoi en cours...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                  </svg>
                  Envoyer le code
                </>
              )}
            </button>
          </form>

          <div className="forgot-footer-links">
            <a href="/login" className="link-3d">Retour à la connexion →</a>
          </div>

          <div className="forgot-security pulse-security">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            Sécurité SSL 256-bit · Protection des données
          </div>
        </div>
      </div>
    </div>
  );
}