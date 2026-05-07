import { useState, useContext, useEffect, useRef } from "react";
import { AuthContext } from "../context/AuthContext";
import "./login.css";
import BgImage from "../Images/Attijari_Bank_background.jpg";
import LogoImg from "../Images/Logo_Attijari_bank.png";

function extractError(err) {
  const data = err.response?.data;
  if (!data) return "Erreur réseau. Veuillez réessayer.";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(" | ");
  return "Échec de l'authentification. Vérifiez vos accès.";
}

export default function Login() {
  const { login } = useContext(AuthContext);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
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

  const validate = () => {
    if (!email.trim()) return "L'email est requis";
    if (!/^[\w.-]+@[\w.-]+\.\w{2,}$/.test(email)) return "Format d'email invalide";
    if (!password.trim()) return "Le mot de passe est requis";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    const err = validate();
    if (err) { setMessage(err); return; }
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setMessage(extractError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page-wrapper">
      {/* Canvas 3D pour les particules */}
      <canvas ref={particlesRef} className="particles-canvas-3d" />

      {/* ── Left decorative panel avec animations 3D ── */}
      <div className="login-left" aria-hidden="true">
        <div className="login-left-grid" />
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
        <div className="login-left-inner">
          {/* LOGO à la place du texte ATTIJARIBANK */}
          <div className="login-left-logo animated-logo">
            <img src={LogoImg} alt="Attijari bank" className="left-logo-img" />
          </div>
          <div className="login-left-tagline">Portail Sécurisé</div>
          <div className="login-left-bar" />
          <h2 className="login-left-title floating-title">Surveillance<br />IA &amp; Sécurité</h2>
          <p className="login-left-sub fade-in">
            Accédez à vos outils d'analyse et de détection d'anomalies en temps réel.
          </p>
          <div className="login-left-dots">
            {[...Array(16)].map((_, i) => (
              <div
                key={i}
                className="login-dot pulse-dot"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
          <div className="login-left-features">
            <div className="login-feat feat-3d">
              <div className="login-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </div>
              Authentification biométrique
            </div>
            <div className="login-feat feat-3d">
              <div className="login-feat-icon">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </div>
              Détection IA en temps réel
            </div>
            <div className="login-feat feat-3d">
              <div className="login-feat-icon">
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
        className="login-right"
        style={{
          backgroundImage: `url(${BgImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="login-card" ref={cardRef}>
          <div className="login-top-bar">
            <div className="shimmer-effect"></div>
          </div>

          <div className="login-header">
            {/* LOGO dans la carte (mobile + desktop) à la place du texte "Attijaribank" */}
            <div className="login-card-logo">
              <img src={LogoImg} alt="Attijari bank" className="card-logo-img" />
            </div>
            <h1 className="glitch-text" data-text="Connexion">Connexion</h1>
            <p>Entrez vos identifiants pour accéder à votre espace sécurisé</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field floating-label">
              <label>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                Identifiant / Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nom@attijari.tn"
                required
                autoComplete="email"
                className="input-3d"
              />
            </div>

            <div className="login-field floating-label">
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
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="input-3d"
              />
            </div>

            {message && (
              <div className="login-error-box shake-animation">
                <span>⚠</span> {message}
              </div>
            )}

            <button type="submit" disabled={loading} className="login-btn btn-3d">
              {loading ? (
                <><span className="login-spinner" /> Vérification en cours...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Accéder à mon espace
                </>
              )}
            </button>
          </form>

          <div className="login-footer-links">
            <a href="/forgot-password" className="link-3d">Mot de passe oublié ?</a>
            <a href="/signup" className="link-3d">Créer un compte</a>
          </div>

          <div className="login-security pulse-security">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            Connexion SSL 256-bit · Ne communiquez jamais vos codes
          </div>
        </div>
      </div>
    </div>
  );
}