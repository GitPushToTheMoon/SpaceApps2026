// Where the FastAPI backend lives.
//   Local dev: leave VITE_API_URL unset; vite.config.js proxies /api and /library to localhost:8000.
//   Deployed:  set VITE_API_URL=https://<your-cloud-run-url> in frontend/.env.production
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
