import { createContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/axios";

export const AuthContext = createContext();

function generateNameFromEmail(email) {
  const localPart = email.split("@")[0];
  const parts = localPart.split(/[._]/);
  const nameParts = parts.map(p => p.charAt(0).toUpperCase() + p.slice(1));
  return nameParts.join(" ");
}

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // ← AJOUT CLÉ

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const role = localStorage.getItem("role");
    const email = localStorage.getItem("email");
    const name = localStorage.getItem("name");

    if (token && role && email) {
      setUser({ token, role, email, name: name || generateNameFromEmail(email) });
    }

    setLoading(false); // ← on indique que la vérification est terminée
  }, []);

  const login = async (emailInput, password) => {
    const res = await API.post("/login", { email: emailInput, password });
    const { access_token } = res.data;

    localStorage.setItem("access_token", access_token);

    const userRes = await API.get("/users/me", {
      headers: { Authorization: `Bearer ${access_token}` },
    });

    const { role, email } = userRes.data;
    const name = userRes.data.name || generateNameFromEmail(email);

    localStorage.setItem("role", role);
    localStorage.setItem("email", email);
    localStorage.setItem("name", name);

    setUser({ token: access_token, role, email, name });

    if (role === "admin") navigate("/admin");
    else navigate("/dashboard");
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("role");
    localStorage.removeItem("email");
    localStorage.removeItem("name");
    setUser(null);
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};