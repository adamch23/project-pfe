import { useContext } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import './dashboard.css';

const Sidebar = () => (
  <aside className="sidebar">
    <div className="sidebar-header">
      <span className="brand-main">Attijari</span><span className="brand-sub">bank</span>
    </div>
    <nav className="sidebar-menu">
      <NavLink to="/AppPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🖥️</span> App Pipeline
      </NavLink>
      <NavLink to="/APILogsPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🔌</span> API Pipeline
      </NavLink>
      <NavLink to="/OSPipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">⚙️</span> OS Pipeline
      </NavLink>
      <NavLink to="/DatabasePipelineDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🗄️</span> Database Pipeline
      </NavLink>
      <NavLink to="/PipelineFirewallDashboard" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🔥</span> Firewall Pipeline
      </NavLink>
      <NavLink to="/admin" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">🛡️</span> Administration
      </NavLink>

  <NavLink to="/profile" className={({ isActive }) => isActive ? "menu-item active" : "menu-item"}>
        <span className="menu-icon">👤</span> Profile
      </NavLink>

    </nav>
    <div className="sidebar-footer">
      <p>© 2026 Attijariwafa Bank</p>
    </div>
  </aside>
);

const Navbar = ({ user, logout }) => (
  <header className="navbar">
    <div className="nav-search-container">
      <div className="search-bar">
        <span className="search-icon">🔍</span>
        <input type="text" placeholder="Rechercher un service..." />
      </div>
    </div>

    <div className="nav-right-side">
      <div className="user-profile-card">
        <div className="user-details">
          <span className="u-name">{user?.name || "Adam Chemengui"}</span>
          <span className="u-email">{user?.email || "adam.chemengui@esprit.tn"}</span>
          <span className="u-role-badge">{user?.role || "admin"}</span>
        </div>
        <div className="u-avatar">
          {user?.name?.charAt(0) || "A"}
        </div>
      </div>
      <button onClick={logout} className="logout-action-btn">
        Déconnexion
      </button>
    </div>
  </header>
);

export default function DashboardLayout({ children }) {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="dashboard-app-container">
      <Sidebar />
      <main className="dashboard-main">
        <Navbar user={user} logout={handleLogout} />
        <div className="dashboard-content-scroll">
          {children}
        </div>
      </main>
    </div>
  );
}