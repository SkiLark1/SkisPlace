import './style.css'

async function initWidget() {
  const container = document.getElementById('skisplace-widget');
  if (!container) {
    console.error('SkisPlace: Mount point #skisplace-widget not found');
    return;
  }

  // 1. Get Config
  // In production, we look for the script tag that loaded us (document.currentScript doesn't work with module/defer easily in all browsers, 
  // but often we search by src or use a known ID).
  // For this "Hello Widget", we'll look for:
  // A) A script with id "skisplace-config" (dev/test helper)
  // B) The script src containing "widget.js" (prod pattern)

  let apiKey: string | null = null;

  const configScript = document.getElementById('skisplace-config');
  if (configScript) {
    apiKey = configScript.getAttribute('data-api-key');
  } else {
    // Search tags
    const scripts = document.querySelectorAll('script');
    for (const s of scripts) {
      if (s.src && s.src.includes('widget.js')) {
        apiKey = s.getAttribute('data-api-key');
        break;
      }
    }
  }

  if (!apiKey) {
    container.innerHTML = `<div class="sp-error">Configuration missing (API Key)</div>`;
    return;
  }

  container.innerHTML = `<div class="sp-loading">Connecting to SkisPlace...</div>`;

  // 2. Ping API
  // Note: During local dev `npm run dev`, localhost:5173 -> localhost:8000 might have CORS issues 
  // if not handled. The API allows "*" or specific domains. 
  // We verified API allows based on Origin header. 
  // Vite dev server origin is usually http://localhost:5173.
  // We need to make sure http://localhost:5173 is allowed in the Project Domains, OR the API allows it by default/open mode (which it does if no domains set).

  const API_URL = 'http://localhost:8000/api/v1/public/ping';

  try {
    const res = await fetch(API_URL, {
      method: 'GET',
      headers: {
        'X-API-KEY': apiKey
      }
    });

    if (!res.ok) {
      throw new Error(`Status ${res.status}`);
    }

    const data = await res.json();

    // 3. Render Success
    container.innerHTML = `
      <div class="sp-box">
        <div class="sp-status is-connected"></div>
        <div class="sp-content">
          <h3>Connected</h3>
          <p>Project: <strong>${data.project}</strong></p>
        </div>
      </div>
    `;

  } catch (err) {
    console.error(err);
    container.innerHTML = `
      <div class="sp-box error">
        <div class="sp-status is-error"></div>
        <div class="sp-content">
          <h3>Connection Failed</h3>
          <p>Could not reach SkisPlace API.</p>
        </div>
      </div>
    `;
  }
}

initWidget();
