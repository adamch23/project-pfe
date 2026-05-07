import { useNavigate } from "react-router-dom";
import { useContext, useEffect, useRef } from "react";
import { AuthContext } from "../context/AuthContext";
import "./NotFound.css";

export default function NotFound() {
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);
  const canvasRef = useRef(null);

  const handleGoHome = () => {
    if (!user) return navigate("/login");
    if (user.role === "admin") return navigate("/admin");
    return navigate("/AppPipelineDashboard");
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = Array.from({ length: 60 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2 + 0.5,
      dx: (Math.random() - 0.5) * 0.4,
      dy: (Math.random() - 0.5) * 0.4,
      o: Math.random() * 0.5 + 0.1,
    }));

    let raf;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,184,28,${p.o})`;
        ctx.fill();
        p.x += p.dx;
        p.y += p.dy;
        if (p.x < 0 || p.x > canvas.width) p.dx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.dy *= -1;
      });
      raf = requestAnimationFrame(draw);
    };
    draw();

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);

  return (
    <div className="nf-wrapper">
      <canvas ref={canvasRef} className="nf-canvas" aria-hidden="true" />

      <div className="nf-grid" aria-hidden="true" />
      <div className="nf-orb nf-orb--gold" aria-hidden="true" />
      <div className="nf-orb nf-orb--red" aria-hidden="true" />

      <div className="nf-container">
        <div className="nf-brand" onClick={handleGoHome}>
          Attijari<span>bank</span>
        </div>

        <div className="nf-code-wrap" aria-label="Erreur 404">
          <span className="nf-digit nf-digit--1">4</span>
          <div className="nf-zero-wrap">
            <svg className="nf-zero-svg" viewBox="0 0 120 140" fill="none">
              <text
                x="60" y="108"
                textAnchor="middle"
                fontSize="130"
                fontWeight="900"
                fontFamily="Georgia,serif"
                fill="none"
                stroke="#FFB81C"
                strokeWidth="3"
              >0</text>
            </svg>
            <div className="nf-orbit-dot" />
          </div>
          <span className="nf-digit nf-digit--2">4</span>
        </div>

        <div className="nf-divider">
          <span className="nf-divider-line" />
          <span className="nf-divider-diamond" />
          <span className="nf-divider-line" />
        </div>

        <h1 className="nf-title">Page introuvable</h1>
        <p className="nf-sub">
          La ressource demandée n'existe pas ou a été déplacée.<br />
          Vérifiez l'URL ou retournez à votre espace sécurisé.
        </p>

        <div className="nf-actions">
          <button className="nf-btn nf-btn--primary" onClick={handleGoHome}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M5 12L12 19M5 12L12 5"/>
            </svg>
            Retour à l'accueil
          </button>
          <button className="nf-btn nf-btn--secondary" onClick={() => navigate(-1)}>
            Page précédente
          </button>
        </div>

        <p className="nf-error-code">ERR_404 · PAGE_NOT_FOUND · ATTIJARI_PORTAL</p>
      </div>
    </div>
  );
}