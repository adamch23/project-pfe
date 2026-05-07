// AdminDashboard.jsx - Version complète avec boutons horizontaux
import React, { useState, useEffect, useContext } from "react";
import API from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import DashboardLayout from "./DashboardLayout";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement,
  Filler
} from 'chart.js';
import { Bar, Doughnut, Line } from 'react-chartjs-2';
import "./AdminDashboard.css";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement,
  Filler
);

export default function AdminDashboard() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showStats, setShowStats] = useState(true);
  const { user } = useContext(AuthContext);

  const [showModal, setShowModal] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", password: "", role: "employer" });
  const [passwordModal, setPasswordModal] = useState({ show: false, userId: null });
  const [passwordData, setPasswordData] = useState({ newPassword: "", confirmPassword: "" });

  const authHeader = { headers: { Authorization: `Bearer ${user?.token}` } };

  const [chartData, setChartData] = useState({
    roleDistribution: { admin: 0, employer: 0 },
    statusDistribution: { active: 0, inactive: 0 },
    monthlyActivity: [0, 0, 0, 0, 0, 0],
    weeklyConnections: [0, 0, 0, 0, 0, 0, 0]
  });

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const res = await API.get("/users", authHeader);
      setUsers(res.data);
      calculateCharts(res.data);
    } catch (err) {
      console.error("Erreur :", err);
      alert("Erreur lors du chargement des utilisateurs.");
    } finally {
      setLoading(false);
    }
  };

  const calculateCharts = (userData) => {
    const adminCount = userData.filter(u => u.role === 'admin').length;
    const employerCount = userData.filter(u => u.role === 'employer').length;
    const activeCount = userData.filter(u => u.is_active).length;
    const inactiveCount = userData.filter(u => !u.is_active).length;
    const monthlyActivity = [12, 19, 15, 17, 14, 22];
    const weeklyConnections = [45, 52, 38, 48, 55, 42, 58];
    
    setChartData({
      roleDistribution: { admin: adminCount, employer: employerCount },
      statusDistribution: { active: activeCount, inactive: inactiveCount },
      monthlyActivity,
      weeklyConnections
    });
  };

  useEffect(() => { if (user) fetchUsers(); }, [user]);

  const handleAction = async (method, url, data = {}) => {
    try {
      await API[method](url, data, authHeader);
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Action impossible.");
    }
  };

  const handlePasswordChange = async () => {
    if (passwordData.newPassword !== passwordData.confirmPassword) return alert("Incohérence mots de passe.");
    await handleAction('put', `/users/${passwordModal.userId}/password`, { password: passwordData.newPassword });
    setPasswordModal({ show: false, userId: null });
    setPasswordData({ newPassword: "", confirmPassword: "" });
  };

  const handleCreateUser = async () => {
    if (!newUser.email || !newUser.password) {
      alert("Veuillez remplir tous les champs.");
      return;
    }
    await handleAction('post', "/users", newUser);
    setShowModal(false);
    setNewUser({ email: "", password: "", role: "employer" });
  };

  const roleChartData = {
    labels: ['Administrateurs', 'Employés'],
    datasets: [{
      data: [chartData.roleDistribution.admin, chartData.roleDistribution.employer],
      backgroundColor: ['#8B5CF6', '#FFB81C'],
      borderWidth: 0,
      hoverOffset: 10
    }]
  };

  const statusChartData = {
    labels: ['Actifs', 'Inactifs'],
    datasets: [{
      data: [chartData.statusDistribution.active, chartData.statusDistribution.inactive],
      backgroundColor: ['#10B981', '#EF4444'],
      borderWidth: 0,
      hoverOffset: 10
    }]
  };

  const monthlyChartData = {
    labels: ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin'],
    datasets: [{
      label: 'Nouveaux utilisateurs',
      data: chartData.monthlyActivity,
      backgroundColor: 'rgba(255, 184, 28, 0.5)',
      borderColor: '#FFB81C',
      borderWidth: 2,
      borderRadius: 8,
      tension: 0.4
    }]
  };

  const weeklyChartData = {
    labels: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
    datasets: [{
      label: 'Connexions',
      data: chartData.weeklyConnections,
      fill: true,
      backgroundColor: 'rgba(255, 184, 28, 0.1)',
      borderColor: '#FFB81C',
      borderWidth: 2,
      pointBackgroundColor: '#FFB81C',
      pointBorderColor: '#fff',
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0.4
    }]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
        labels: { font: { size: 11 } }
      },
      tooltip: { backgroundColor: '#1E293B' }
    }
  };

  return (
    <DashboardLayout user={user}>
      <div className="admin-dashboard">
        {/* En-tête */}
        <div className="admin-header">
          <div className="admin-title-section">
            <h1>Administration</h1>
            <p>Gestion des utilisateurs et analyse de la plateforme</p>
          </div>
          <div className="admin-actions">
            <button 
              className={`btn-outline ${showStats ? 'active' : ''}`} 
              onClick={() => setShowStats(!showStats)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <line x1="12" y1="22" x2="12" y2="12"/>
                <polyline points="9 10 12 7 15 10"/>
              </svg>
              {showStats ? 'Masquer stats' : 'Afficher stats'}
            </button>
            <button className="btn-primary" onClick={() => setShowModal(true)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
                <line x1="12" y1="3" x2="12" y2="11"/>
                <line x1="9" y1="7" x2="15" y2="7"/>
              </svg>
              Nouvel utilisateur
            </button>
          </div>
        </div>

        {/* Panneau des statistiques */}
        {showStats && (
          <div className="stats-dashboard">
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: '#3B82F6' }}>👥</div>
                <div className="kpi-info">
                  <span className="kpi-title">Total utilisateurs</span>
                  <span className="kpi-value">{users.length}</span>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: '#10B981' }}>🟢</div>
                <div className="kpi-info">
                  <span className="kpi-title">Utilisateurs actifs</span>
                  <span className="kpi-value">{users.filter(u => u.is_active).length}</span>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: '#F59E0B' }}>⏳</div>
                <div className="kpi-info">
                  <span className="kpi-title">En attente</span>
                  <span className="kpi-value">{users.filter(u => !u.is_active).length}</span>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon" style={{ background: '#8B5CF6' }}>👑</div>
                <div className="kpi-info">
                  <span className="kpi-title">Administrateurs</span>
                  <span className="kpi-value">{users.filter(u => u.role === 'admin').length}</span>
                </div>
              </div>
            </div>

            <div className="charts-grid">
              <div className="chart-card">
                <div className="chart-header">
                  <h3>Distribution des rôles</h3>
                  <span className="chart-subtitle">Administrateurs vs Employés</span>
                </div>
                <div className="chart-container">
                  <Doughnut data={roleChartData} options={chartOptions} />
                </div>
              </div>

              <div className="chart-card">
                <div className="chart-header">
                  <h3>Statut des comptes</h3>
                  <span className="chart-subtitle">Actifs vs Inactifs</span>
                </div>
                <div className="chart-container">
                  <Doughnut data={statusChartData} options={chartOptions} />
                </div>
              </div>

              <div className="chart-card chart-full">
                <div className="chart-header">
                  <h3>Évolution mensuelle</h3>
                  <span className="chart-subtitle">Nouveaux utilisateurs (6 mois)</span>
                </div>
                <div className="chart-container large">
                  <Bar data={monthlyChartData} options={chartOptions} />
                </div>
              </div>

              <div className="chart-card chart-full">
                <div className="chart-header">
                  <h3>Activité hebdomadaire</h3>
                  <span className="chart-subtitle">Connexions par jour</span>
                </div>
                <div className="chart-container large">
                  <Line data={weeklyChartData} options={chartOptions} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tableau des utilisateurs */}
        <div className="users-table-container">
          <div className="table-header">
            <h3>Liste des utilisateurs</h3>
            <div className="table-info">
              <span>{users.length} utilisateur(s) au total</span>
              <button className="btn-icon" onClick={fetchUsers}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M23 4v6h-6M1 20v-6h6"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
              </button>
            </div>
          </div>
          
          <div className="table-responsive">
            <table className="users-table">
              <thead>
                <tr>
                  <th>UTILISATEUR</th>
                  <th>RÔLE</th>
                  <th>STATUT</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="4" className="loading-cell">
                      <div className="spinner"></div>
                      Chargement des utilisateurs...
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id}>
                      <td className="user-cell">
                        <div className="user-avatar">
                          {u.email.charAt(0).toUpperCase()}
                        </div>
                        <div className="user-info">
                          <div className="user-email">{u.email}</div>
                          <div className="user-id">ID: {u.id}</div>
                        </div>
                      </td>
                      <td>
                        <span className={`role-badge ${u.role}`}>
                          {u.role === 'admin' ? 'Administrateur' : 'Employé'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${u.is_active ? 'active' : 'pending'}`}>
                          {u.is_active ? 'Actif' : 'En attente'}
                        </span>
                      </td>
                      <td className="actions-cell">
                        {/* BOUTONS HORIZONTAUX SUR LA MÊME LIGNE */}
                        <div className="actions-horizontal">
                          {!u.is_active ? (
                            <button 
                              className="action-horiz approve" 
                              onClick={() => handleAction('put', `/users/${u.id}/activate`)}
                              title="Approuver"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polyline points="20 6 9 17 4 12"/>
                              </svg>
                              Approuver
                            </button>
                          ) : (
                            <button 
                              className="action-horiz deactivate" 
                              onClick={() => handleAction('put', `/users/${u.id}/deactivate`)}
                              title="Désactiver"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="18" y1="6" x2="6" y2="18"/>
                              </svg>
                              Désactiver
                            </button>
                          )}
                          <button 
                            className="action-horiz role" 
                            onClick={() => handleAction('put', `/users/${u.id}`, { role: u.role === 'admin' ? 'employer' : 'admin' })}
                            title="Changer rôle"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                              <circle cx="12" cy="7" r="4"/>
                            </svg>
                            Changer rôle
                          </button>
                          <button 
                            className="action-horiz password" 
                            onClick={() => setPasswordModal({ show: true, userId: u.id })}
                            title="Modifier mot de passe"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <rect x="3" y="11" width="18" height="11" rx="2"/>
                              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                            </svg>
                            Mot de passe
                          </button>
                          <button 
                            className="action-horiz delete" 
                            onClick={() => { if(window.confirm("Supprimer définitivement cet utilisateur ?")) handleAction('delete', `/users/${u.id}`) }}
                            title="Supprimer"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                            Supprimer
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Modal de modification du mot de passe */}
      {passwordModal.show && (
        <div className="modal-overlay" onClick={() => setPasswordModal({ show: false, userId: null })}>
          <div className="modal-container" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Modification du mot de passe</h3>
              <button className="modal-close" onClick={() => setPasswordModal({ show: false })}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Nouveau mot de passe</label>
                <input 
                  type="password" 
                  placeholder="Entrez le nouveau mot de passe"
                  value={passwordData.newPassword}
                  onChange={e => setPasswordData({...passwordData, newPassword: e.target.value})} 
                />
              </div>
              <div className="form-group">
                <label>Confirmation</label>
                <input 
                  type="password" 
                  placeholder="Confirmez le mot de passe"
                  value={passwordData.confirmPassword}
                  onChange={e => setPasswordData({...passwordData, confirmPassword: e.target.value})} 
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setPasswordModal({ show: false })}>Annuler</button>
              <button className="btn-primary" onClick={handlePasswordChange}>Enregistrer</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de création d'utilisateur */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-container" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Créer un nouvel utilisateur</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Email</label>
                <input 
                  type="email" 
                  placeholder="exemple@attijari.tn" 
                  value={newUser.email} 
                  onChange={e => setNewUser({...newUser, email: e.target.value})} 
                />
              </div>
              <div className="form-group">
                <label>Mot de passe temporaire</label>
                <input 
                  type="password" 
                  placeholder="Mot de passe provisoire" 
                  value={newUser.password} 
                  onChange={e => setNewUser({...newUser, password: e.target.value})} 
                />
              </div>
              <div className="form-group">
                <label>Rôle</label>
                <select value={newUser.role} onChange={e => setNewUser({...newUser, role: e.target.value})}>
                  <option value="employer">Employé</option>
                  <option value="admin">Administrateur</option>
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowModal(false)}>Annuler</button>
              <button className="btn-primary" onClick={handleCreateUser}>Créer le compte</button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}