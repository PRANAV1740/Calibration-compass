// CalibrationCompass frontend configuration.
//
// apiBase is the URL of the backend API (the FastAPI service on Render).
// Change it here to your Render URL before deploying, e.g.
//   apiBase: "https://calibrationcompass-api.onrender.com"
//
// You can also override it at runtime from the "Backend URL" field in the app
// (that value is saved in your browser's localStorage and wins over this one).
window.CC_CONFIG = {
  apiBase: "http://localhost:8000"
};
