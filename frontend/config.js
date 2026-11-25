// CalibrationCompass frontend configuration.
//
// apiBase is the URL of the backend API (the FastAPI service on Render).
// It is chosen by hostname: local development uses the local backend, and any
// deployed host (e.g. Vercel) uses the Render backend.
//
// You can also override it at runtime from the "Backend URL" field in the app
// (that value is saved in your browser's localStorage and wins over this one).
window.CC_CONFIG = {
  apiBase:
    location.hostname === "localhost" || location.hostname === "127.0.0.1"
      ? "http://localhost:8000"
      : "https://calibrationcompass-api.onrender.com"
};
