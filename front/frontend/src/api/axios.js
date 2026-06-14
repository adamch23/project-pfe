import axios from "axios";

const API = axios.create({
  baseURL: "/api",
  withCredentials: true, // Crucial pour envoyer les cookies HttpOnly à chaque requête
});

export default API;