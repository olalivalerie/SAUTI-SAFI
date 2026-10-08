const API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "sautiSafiToken";
const USER_KEY = "sautiSafiUser";

function token() {
  return localStorage.getItem(TOKEN_KEY);
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function api(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {})
  };

  const currentToken = token();
  if (currentToken) headers.Authorization = `Bearer ${currentToken}`;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error("Cannot connect to SAUTI SAFI. Make sure FastAPI is running on port 8000.");
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    if (response.status === 401) clearSession();
    const detail = Array.isArray(data.detail)
      ? data.detail.map(item => item.msg).join(" ")
      : data.detail;
    throw new Error(detail || `Request failed (${response.status}).`);
  }

  return data;
}

function showMessage(id, text, type = "error") {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = text;
  element.className = `message show ${type}`;
}

function logout() {
  clearSession();
  window.location.href = "login.html";
}
