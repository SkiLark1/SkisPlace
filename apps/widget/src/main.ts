// @ts-ignore
import cssStyles from './style.css?inline'

interface EpoxyStyle {
  id: string
  name: string
  category: string
  cover_image_url?: string
}

async function initWidget() {
  // Inject Styles
  if (!document.getElementById('sp-widget-styles')) {
    const styleEl = document.createElement('style');
    styleEl.id = 'sp-widget-styles';
    styleEl.innerHTML = cssStyles;
    document.head.appendChild(styleEl);
  }

  const container = document.getElementById('skisplace-widget');
  if (!container) {
    console.error('SkisPlace: Mount point #skisplace-widget not found');
    return;
  }

  // --- 1. Config & API ---
  let apiBase: string | null = null;
  let apiKey: string | null = null;
  let debugMode: boolean = false;

  // Check URL parameters first (for dashboard preview mode)
  const urlParams = new URLSearchParams(window.location.search);
  const projectKeyFromUrl = urlParams.get('projectKey');
  if (projectKeyFromUrl) {
    apiKey = projectKeyFromUrl;
  }

  const configScript = document.getElementById('skisplace-config');
  if (configScript) {
    apiBase = configScript.getAttribute('data-api-base');
    if (!apiKey) apiKey = configScript.getAttribute('data-api-key');
    debugMode = configScript.getAttribute('data-debug') === 'true';
  }

  // Script tag fallback/discovery
  let scriptEl: HTMLScriptElement | null = configScript as HTMLScriptElement;
  if (!scriptEl) {
    const scripts = document.querySelectorAll('script');
    for (const s of scripts) {
      if (s.src && s.src.includes('widget.js')) {
        scriptEl = s;
        break;
      }
    }
  }

  if (scriptEl) {
    if (!apiKey) apiKey = scriptEl.getAttribute('data-api-key');
    if (!apiBase) apiBase = scriptEl.getAttribute('data-api-base');
    if (!debugMode && (scriptEl.getAttribute('data-debug') === 'true' || scriptEl.getAttribute('data-debug') === '1')) {
      debugMode = true;
    }
  }

  const API_BASE = apiBase || 'http://localhost:8000/api/v1';

  // Fix 4B: Block style loading logic and config loading unless key exists
  if (!apiKey) {
    container.innerHTML = `<div class="sp-error">Configuration missing (API Key)</div>`;
    return;
  }

  // --- 2. State & Render ---
  let uploadedImageId: string | null = null;

  async function loadConfig() {
    try {
      const res = await fetch(`${API_BASE}/epoxy/config/public`, {
        headers: { 'X-API-KEY': apiKey! }
      });
      if (res.ok) {
        const config = await res.json();
        if (config && config.theme) {
          applyTheme(config.theme);
        }
      }
    } catch (e) {
      console.warn('SkisPlace: Failed to load module config', e);
    }
  }

  function applyTheme(theme: any) {
    if (!container) return;
    if (theme.accent) container.style.setProperty('--sp-accent', theme.accent);
    if (theme.font_family) container.style.setProperty('--sp-font-family', theme.font_family);
    if (theme.radius) container.style.setProperty('--sp-radius', theme.radius);
    // Optional mappings
    if (theme.surface) container.style.setProperty('--sp-surface', theme.surface);
    if (theme.text) container.style.setProperty('--sp-text', theme.text);
  }

  // Load config in background
  loadConfig();

  let state = {
    step: 'upload' as 'upload' | 'systems' | 'styles' | 'rendering' | 'result',
    uploadedImage: null as File | null,
    // ... (rest of state same)
    uploadedImageUrl: null as string | null,
    loadingStyles: false as boolean,
    styles: [] as EpoxyStyle[],
    selectedStyleId: null as string | null,
    selectedSystem: null as 'Flake' | 'Metallic' | 'Quartz' | null, // Starts null, user must choose
    resultUrl: null as string | null,
    maskUrl: null as string | null,
    debugData: null as any | null,
    error: null as string | null,
    maskEdit: {
      enabled: false,
      mode: 'add' as 'add' | 'remove',
      brushSize: 30,
      canvas: null as HTMLCanvasElement | null,
      ctx: null as CanvasRenderingContext2D | null,
      history: [] as ImageData[],
      historyIndex: -1,
      customMaskData: null as string | null
    },
    tuning: {
      blend_strength: 0.85,
      finish: 'satin' as 'gloss' | 'satin' | 'matte'
    }
  };

  async function render() {
    // ... (header/container logic kept same, simplified in diff)
    container!.innerHTML = '<div class="sp-box"></div>';
    const box = container!.querySelector('.sp-box')!;
    const header = document.createElement('div');
    header.className = 'sp-header';
    header.innerHTML = `<h3>Epoxy Visualizer${debugMode ? ' <span style="font-size:0.7em; color: orange;">(DEBUG)</span>' : ''}</h3>`;
    box.appendChild(header);
    const content = document.createElement('div');
    content.className = 'sp-content-body';
    box.appendChild(content);

    // Error Overlay... (kept same)
    if (state.error) {/*...*/ }

    if (state.step === 'upload') {
      // ... (Upload UI kept same)
      content.innerHTML = `
        <div class="sp-upload-zone">
          <p>Take a photo of your room or upload one to get started.</p>
          <input type="file" id="sp-file-input" accept="image/*" />
          <label for="sp-file-input" class="sp-btn primary">Select Photo</label>
          <div style="margin: 15px 0; color: #888; font-size: 0.8em; text-transform: uppercase;">OR</div>
          <button id="sp-sample-btn" class="sp-btn secondary">Load Sample Garage</button>
        </div>
      `;
      // ... (Event bindings)
      const input = content.querySelector('#sp-file-input') as HTMLInputElement;
      input.onchange = async (e: any) => { if (e.target.files && e.target.files[0]) handleFileSelect(e.target.files[0]); };
      const sampleBtn = content.querySelector('#sp-sample-btn') as HTMLButtonElement;
      sampleBtn.onclick = async () => { /* sample loading logic */
        // ...
        sampleBtn.disabled = true; sampleBtn.innerText = 'Loading...';
        try {
          const response = await fetch('/samples/garage1.jpg'); if (!response.ok) throw new Error('Sample not found');
          const blob = await response.blob(); handleFileSelect(new File([blob], "garage1.jpg", { type: "image/jpeg" }));
        } catch (e) { state.error = 'Failed to load sample'; render(); }
      };

      async function handleFileSelect(file: File) {
        state.uploadedImage = file;
        state.uploadedImageUrl = URL.createObjectURL(file);
        try {
          const upData = new FormData();
          upData.append('file', file);

          // CHANGE: Go to 'systems' step first
          state.step = 'systems';
          // Fix 4B: Only load styles if we have a key (we should, but safer)
          if (apiKey) {
            loadStyles();
          } else {
            console.error("No API key when starting upload flow?");
          }

          const res = await fetch(`${API_BASE}/epoxy/uploads`, {
            method: 'POST',
            headers: { 'X-API-KEY': apiKey! },
            body: upData
          });
          if (res.ok) {
            const data = await res.json();
            uploadedImageId = data.id;
          } else {
            state.error = 'Upload failed'; render();
          }
        } catch (err) { state.error = 'Upload failed'; }
      }
    }
    // NEW STEP: System Selection
    else if (state.step === 'systems') {
      if (state.uploadedImageUrl) {
        const preview = document.createElement('img');
        preview.src = state.uploadedImageUrl;
        preview.className = 'sp-mini-preview';
        content.appendChild(preview);
      }

      const title = document.createElement('h4');
      title.innerText = 'Select a System';
      content.appendChild(title);

      const systemGrid = document.createElement('div');
      systemGrid.className = 'sp-system-cards';

      // Define systems
      const systems = [
        { id: 'Flake', label: 'Flake System', desc: 'Decorative vinyl flakes' },
        { id: 'Metallic', label: 'Metallic', desc: 'Flowing, marble-like finish' },
        { id: 'Quartz', label: 'Quartz', desc: 'High durability & texture' }
      ];

      systems.forEach(sys => {
        const card = document.createElement('div');
        card.className = 'sp-system-card';
        card.innerHTML = `
            <div class="sp-sys-icon">✨</div>
            <div class="sp-sys-info">
                <div class="sp-sys-title">${sys.label}</div>
                <div class="sp-sys-desc">${sys.desc}</div>
            </div>
          `;
        card.onclick = () => {
          state.selectedSystem = sys.id as any;
          state.step = 'styles';
          render();
        };
        systemGrid.appendChild(card);
      });
      content.appendChild(systemGrid);

      // Back Action
      const actions = document.createElement('div');
      actions.className = 'sp-actions';
      const backBtn = document.createElement('button');
      backBtn.className = 'sp-btn text';
      backBtn.innerText = 'Back';
      backBtn.onclick = () => { state.step = 'upload'; state.uploadedImage = null; render(); };
      actions.appendChild(backBtn);
      content.appendChild(actions);
    }
    else if (state.step === 'styles') {
      // Preview Tiny
      if (state.uploadedImageUrl) {
        const preview = document.createElement('img');
        preview.src = state.uploadedImageUrl;
        preview.className = 'sp-mini-preview';
        content.appendChild(preview);
      }

      // Show selected system indicator instead of selector tabs
      const systemIndicator = document.createElement('div');
      systemIndicator.className = 'sp-system-indicator';
      systemIndicator.innerHTML = `System: <strong>${state.selectedSystem}</strong> <button class="sp-link-btn">(Change)</button>`;
      // Bind click to change
      const changeBtn = systemIndicator.querySelector('button');
      if (changeBtn) changeBtn.onclick = () => { state.step = 'systems'; render(); };
      content.appendChild(systemIndicator);

      const title = document.createElement('h4');
      title.innerText = `Choose a ${state.selectedSystem} Style`;
      content.appendChild(title);


      if (state.loadingStyles) {
        content.innerHTML += `
           <div class="sp-loading-container">
             <div class="sp-spinner"></div>
             <p>Loading styles...</p>
           </div>`;
      } else if (state.styles.length === 0) {
        content.innerHTML += `
          <div style="text-align:center; color:#888; padding:20px;">
            <p>No styles configured.</p>
            <button class="sp-btn secondary" id="sp-retry-styles" style="margin-top:10px;">Retry</button>
          </div>
        `;
        // Defer click handler attachment
        setTimeout(() => {
          const retry = content.querySelector('#sp-retry-styles') as HTMLButtonElement;
          if (retry) retry.onclick = () => loadStyles();
        }, 0);
      } else {
        // FILTER STYLES BY SYSTEM
        const filteredStyles = state.styles.filter(s => {
          const cat = s.category || 'Flake';
          return cat === state.selectedSystem;
        });

        if (filteredStyles.length === 0) {
          content.innerHTML += `<div style="text-align:center; color:#888; padding:30px;">No ${state.selectedSystem} styles found.</div>`;
        } else {
          const grid = document.createElement('div');
          grid.className = 'sp-style-grid';
          filteredStyles.forEach(style => {
            const card = document.createElement('div');
            card.className = `sp-style-card ${state.selectedStyleId === style.id ? 'selected' : ''}`;
            card.onclick = () => selectStyle(style.id);

            if (style.cover_image_url) {
              const img = document.createElement('img');
              try {
                const apiUrl = new URL(API_BASE);
                const origin = apiUrl.origin;
                img.src = style.cover_image_url.startsWith('http') ? style.cover_image_url : `${origin}${style.cover_image_url}`;
              } catch (e) {
                img.src = style.cover_image_url;
              }
              card.appendChild(img);
            } else {
              card.innerHTML = `<div class="sp-no-img"></div>`;
            }
            const name = document.createElement('div');
            name.className = 'sp-style-name';
            name.innerText = style.name;
            card.appendChild(name);
            grid.appendChild(card);
          });
          content.appendChild(grid);
        }
      }

      // Actions
      const actions = document.createElement('div');
      actions.className = 'sp-actions';

      const backBtn = document.createElement('button');
      backBtn.className = 'sp-btn text';
      backBtn.innerText = 'Back';
      backBtn.onclick = () => { state.step = 'systems'; state.selectedStyleId = null; render(); };
      actions.appendChild(backBtn);

      const nextBtn = document.createElement('button');
      nextBtn.className = 'sp-btn primary';
      nextBtn.disabled = !state.selectedStyleId || state.loadingStyles;
      nextBtn.innerText = 'Visualize';
      nextBtn.onclick = performRender;
      actions.appendChild(nextBtn);

      content.appendChild(actions);
    }
    // ... (Rest of render states - rendering, result - kept mostly same)
    else if (state.step === 'rendering') {
      content.innerHTML = `
             <div class="sp-loading-container">
               <div class="sp-spinner"></div>
               <p>Generating preview...</p>
             </div>
          `;
    }
    else if (state.step === 'result') {
      content.innerHTML = `
        <div class="sp-result-container">
          <div class="sp-view-toggle">
            <button class="sp-toggle-btn active" data-view="preview">Preview</button>
            <button class="sp-toggle-btn" data-view="original">Original</button>
            ${state.maskUrl ? '<button class="sp-toggle-btn" data-view="mask">Mask Only</button>' : ''}
            ${state.maskUrl ? '<button class="sp-toggle-btn" data-view="overlay">Mask Overlay</button>' : ''}
          </div>
          
          <div class="sp-img-display" id="sp-img-container">
            <div class="sp-img-stage" id="sp-img-stage">
              <img src="${state.resultUrl}" class="sp-main-img" id="sp-result-img" />
              ${state.maskUrl ? `<img src="${state.maskUrl}" class="sp-mask-overlay" id="sp-mask-overlay" style="display:none; opacity: 0.5;" />` : ''}
            </div>
          </div>

          ${debugMode ? `
          <div class="sp-debug-panel">
            <div class="sp-debug-header">Visual Debug</div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">Mask Source</span>
              <span class="sp-debug-value">${(() => {
            const src = state.debugData?.mask_source || 'unknown';
            const labels: { [key: string]: string } = {
              'user': 'User Edited',
              'ai': 'AI',
              'heuristic': 'Heuristic'
            };
            return labels[src] || src;
          })()}</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">Camera</span>
              <span class="sp-debug-value">${state.debugData?.camera_geometry || 'Unknown'}</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">AI Enabled</span>
              <span class="sp-debug-value">${state.debugData?.ai_config_resolved?.enabled ? '✓ Yes' : '✗ No'}</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">AI Model</span>
              <span class="sp-debug-value">${state.debugData?.ai_model_loaded ? '✓ Loaded' : '✗ Not Loaded'}</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">Blend Strength</span>
              <span class="sp-debug-value">${(state.tuning.blend_strength * 100).toFixed(0)}%</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">Finish Type</span>
              <span class="sp-debug-value">${state.tuning.finish.charAt(0).toUpperCase() + state.tuning.finish.slice(1)}</span>
            </div>
            ${state.debugData?.mask_stats ? `
            <div class="sp-debug-row">
              <span class="sp-debug-label">Mask Mean</span>
              <span class="sp-debug-value">${state.debugData.mask_stats.mean?.toFixed(1) || 'N/A'}</span>
            </div>
            <div class="sp-debug-row">
              <span class="sp-debug-label">White/Black</span>
              <span class="sp-debug-value">${state.debugData.mask_stats.pct_white?.toFixed(1) || '0'}% / ${state.debugData.mask_stats.pct_black?.toFixed(1) || '0'}%</span>
            </div>
            ` : ''}
            ${state.debugData?.probmap_url ? `
            <div class="sp-debug-row">
              <span class="sp-debug-label">Prob Map</span>
              <a href="${state.debugData.probmap_url}" target="_blank" class="sp-debug-value" style="color:#60a5fa;">View</a>
            </div>
            ` : ''}
            ${state.maskUrl ? `
            <div class="sp-debug-row">
              <span class="sp-debug-label">Mask Opacity</span>
              <input type="range" id="sp-mask-opacity" min="0" max="1" step="0.1" value="0.5" />
              <span id="sp-opacity-val">50%</span>
            </div>
            ` : ''}
          </div>
          ` : ''}
        </div>
      `;

      // Toggle Logic
      const imgEl = content.querySelector('#sp-result-img') as HTMLImageElement;
      const maskOverlay = content.querySelector('#sp-mask-overlay') as HTMLImageElement | null;
      const btns = content.querySelectorAll('.sp-toggle-btn');
      btns.forEach(btn => {
        (btn as HTMLButtonElement).onclick = () => {
          btns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const view = (btn as HTMLButtonElement).dataset.view;
          if (view === 'original') {
            imgEl.src = state.uploadedImageUrl!;
            if (maskOverlay) maskOverlay.style.display = 'none';
          } else if (view === 'mask') {
            imgEl.src = state.maskUrl!;
            if (maskOverlay) maskOverlay.style.display = 'none';
          } else if (view === 'overlay') {
            imgEl.src = state.uploadedImageUrl!;
            if (maskOverlay) maskOverlay.style.display = 'block';
          } else {
            imgEl.src = state.resultUrl!;
            if (maskOverlay) maskOverlay.style.display = 'none';
          }
        };
      });

      // Mask Opacity Slider
      if (debugMode && state.maskUrl) {
        const opacitySlider = content.querySelector('#sp-mask-opacity') as HTMLInputElement;
        const opacityVal = content.querySelector('#sp-opacity-val');
        if (opacitySlider && maskOverlay) {
          opacitySlider.oninput = () => {
            const val = parseFloat(opacitySlider.value);
            maskOverlay.style.opacity = val.toString();
            if (opacityVal) opacityVal.textContent = (val * 100).toFixed(0) + '%';
          };
        }
      }

      // Mask Editing UI
      if (state.maskUrl) {
        const editPanel = document.createElement('div');
        editPanel.className = 'sp-mask-edit-panel';

        // Determine Reset options based on mask_source
        const maskSource = state.debugData?.mask_source || 'heuristic';
        const showAIReset = maskSource.includes('ai');

        editPanel.innerHTML = `
          <div class="sp-edit-header">
            <button class="sp-btn ${state.maskEdit.enabled ? 'primary' : 'secondary'}" id="sp-toggle-edit">
              ${state.maskEdit.enabled ? '✓ Editing Area' : 'Edit Area'}
            </button>
          </div>
          ${state.maskEdit.enabled ? `
          <div class="sp-edit-tools">
            <div class="sp-brush-modes">
              <button class="sp-brush-btn ${state.maskEdit.mode === 'add' ? 'active' : ''}" data-mode="add">+ Add Epoxy</button>
              <button class="sp-brush-btn ${state.maskEdit.mode === 'remove' ? 'active' : ''}" data-mode="remove">− Remove</button>
            </div>
            <div class="sp-brush-size">
              <label>Brush</label>
              <input type="range" id="sp-brush-size" min="5" max="80" value="${state.maskEdit.brushSize}" />
              <span>${state.maskEdit.brushSize}px</span>
            </div>
            <div class="sp-edit-actions">
              <button class="sp-edit-btn" id="sp-undo" ${state.maskEdit.historyIndex <= 0 ? 'disabled' : ''}>Undo</button>
              <button class="sp-edit-btn" id="sp-redo" ${state.maskEdit.historyIndex >= state.maskEdit.history.length - 1 ? 'disabled' : ''}>Redo</button>
              ${showAIReset ? '<button class="sp-edit-btn" id="sp-reset-ai">Reset (AI)</button>' : ''}
              <button class="sp-edit-btn" id="sp-reset-heuristic">Reset (Auto)</button>
            </div>
            <button class="sp-btn primary" id="sp-apply-mask" style="width:100%; margin-top:8px;">Apply Changes</button>
          </div>
          ` : ''}
        `;
        content.appendChild(editPanel);

        // Canvas overlay for editing
        if (state.maskEdit.enabled) {
          setTimeout(() => initMaskEditor(), 50);
        }

        // Bind edit panel events
        setTimeout(() => {
          const toggleBtn = content.querySelector('#sp-toggle-edit') as HTMLButtonElement;
          if (toggleBtn) {
            toggleBtn.onclick = () => {
              state.maskEdit.enabled = !state.maskEdit.enabled;

              // Lock view to Original when editing
              if (state.maskEdit.enabled) {
                const imgEl = content.querySelector('#sp-result-img') as HTMLImageElement;
                if (imgEl && state.uploadedImageUrl) {
                  imgEl.src = state.uploadedImageUrl;
                }
              }

              render();
            };
          }

          if (state.maskEdit.enabled) {
            // Brush mode buttons
            content.querySelectorAll('.sp-brush-btn').forEach(btn => {
              (btn as HTMLButtonElement).onclick = () => {
                state.maskEdit.mode = (btn as HTMLButtonElement).dataset.mode as 'add' | 'remove';
                render();
              };
            });

            // Brush size slider
            const brushSlider = content.querySelector('#sp-brush-size') as HTMLInputElement;
            if (brushSlider) {
              brushSlider.oninput = () => {
                state.maskEdit.brushSize = parseInt(brushSlider.value);
                const span = brushSlider.nextElementSibling;
                if (span) span.textContent = state.maskEdit.brushSize + 'px';
              };
            }

            // Undo/Redo
            const undoBtn = content.querySelector('#sp-undo') as HTMLButtonElement;
            const redoBtn = content.querySelector('#sp-redo') as HTMLButtonElement;
            if (undoBtn) undoBtn.onclick = undoMaskEdit;
            if (redoBtn) redoBtn.onclick = redoMaskEdit;

            // Reset buttons (AI or Heuristic)
            const resetAIBtn = content.querySelector('#sp-reset-ai') as HTMLButtonElement;
            const resetHeuristicBtn = content.querySelector('#sp-reset-heuristic') as HTMLButtonElement;
            if (resetAIBtn) resetAIBtn.onclick = resetMaskToAuto; // Same function for now
            if (resetHeuristicBtn) resetHeuristicBtn.onclick = resetMaskToAuto;

            // Apply
            const applyBtn = content.querySelector('#sp-apply-mask') as HTMLButtonElement;
            if (applyBtn) applyBtn.onclick = applyMaskAndRender;
          }
        }, 0);
      }

      const actions = document.createElement('div');
      actions.className = 'sp-actions';
      const resetBtn = document.createElement('button');
      resetBtn.className = 'sp-btn secondary';
      resetBtn.innerText = 'Start Over';
      resetBtn.onclick = () => {
        state.step = 'upload';
        state.selectedStyleId = null;
        state.uploadedImage = null;
        state.maskUrl = null;
        state.debugData = null;
        state.maskEdit.enabled = false;
        state.maskEdit.history = [];
        state.maskEdit.historyIndex = -1;
        state.maskEdit.customMaskData = null;
        render();
      };
      const downloadBtn = document.createElement('a');
      downloadBtn.className = 'sp-btn primary';
      downloadBtn.innerText = 'Download';
      downloadBtn.href = state.resultUrl!;
      downloadBtn.download = 'epoxy_preview.jpg';
      downloadBtn.target = '_blank';
      actions.appendChild(resetBtn);
      actions.appendChild(downloadBtn);
      content.appendChild(actions);
    }
  }

  // --- Mask Editor Functions ---

  function initMaskEditor() {
    const stage = document.getElementById('sp-img-stage') || document.getElementById('sp-img-container');
    const baseImg = document.getElementById('sp-result-img') as HTMLImageElement;
    if (!stage || !baseImg) return;

    // Ensure image is loaded for correct dimensions
    if (!baseImg.complete) {
      baseImg.onload = initMaskEditor;
      return;
    }

    // Remove existing canvas
    let canvas = document.getElementById('sp-mask-canvas') as HTMLCanvasElement;
    if (canvas) canvas.remove();

    // Create canvas
    canvas = document.createElement('canvas');
    canvas.id = 'sp-mask-canvas';
    canvas.className = 'sp-mask-canvas';

    // Set BITMAP resolution to match natural image
    canvas.width = baseImg.naturalWidth || baseImg.width || 400;
    canvas.height = baseImg.naturalHeight || baseImg.height || 300;

    // CSS uses class (absolute, 100% w/h)

    stage.appendChild(canvas);

    const ctx = canvas.getContext('2d')!;
    state.maskEdit.canvas = canvas;
    state.maskEdit.ctx = ctx;

    // Load existing mask as background
    if (state.maskUrl) {
      const maskImg = new Image();
      maskImg.crossOrigin = 'anonymous';
      maskImg.onload = () => {
        ctx.drawImage(maskImg, 0, 0, canvas.width, canvas.height);
        saveToHistory();
      };
      maskImg.src = state.maskUrl;
    } else {
      // White = full epoxy
      ctx.fillStyle = 'white';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      saveToHistory();
    }

    // ResizeObserver to handle layout shifts
    const resizeObserver = new ResizeObserver(() => {
      // Should we re-init? Only if natural dimensions changed (unlikely for same src)
      // or if we were using display dimensions for bitmap (we aren't).
      // The main thing is that getBoundingClientRect in draw() will be fresh.
    });
    resizeObserver.observe(stage);

    // Drawing state
    let isDrawing = false;

    canvas.onmousedown = (e) => { isDrawing = true; draw(e); };
    canvas.onmousemove = (e) => { if (isDrawing) draw(e); };
    canvas.onmouseup = () => { if (isDrawing) { isDrawing = false; saveToHistory(); } };
    canvas.onmouseleave = () => { if (isDrawing) { isDrawing = false; } };

    // Touch support
    canvas.ontouchstart = (e) => { isDrawing = true; drawTouch(e); e.preventDefault(); };
    canvas.ontouchmove = (e) => { if (isDrawing) { drawTouch(e); e.preventDefault(); } };
    canvas.ontouchend = () => { if (isDrawing) { isDrawing = false; saveToHistory(); } };

    function draw(e: MouseEvent) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;
      brush(x, y);
    }

    function drawTouch(e: TouchEvent) {
      const touch = e.touches[0];
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const x = (touch.clientX - rect.left) * scaleX;
      const y = (touch.clientY - rect.top) * scaleY;
      brush(x, y);
    }

    function brush(x: number, y: number) {
      ctx.beginPath();
      ctx.arc(x, y, state.maskEdit.brushSize, 0, Math.PI * 2);
      ctx.fillStyle = state.maskEdit.mode === 'add' ? 'white' : 'black';
      ctx.fill();
    }
  }

  function saveToHistory() {
    if (!state.maskEdit.canvas || !state.maskEdit.ctx) return;
    const imageData = state.maskEdit.ctx.getImageData(
      0, 0,
      state.maskEdit.canvas.width,
      state.maskEdit.canvas.height
    );
    // Truncate future history
    state.maskEdit.history = state.maskEdit.history.slice(0, state.maskEdit.historyIndex + 1);
    state.maskEdit.history.push(imageData);
    state.maskEdit.historyIndex = state.maskEdit.history.length - 1;
  }

  function undoMaskEdit() {
    if (state.maskEdit.historyIndex > 0 && state.maskEdit.ctx) {
      state.maskEdit.historyIndex--;
      state.maskEdit.ctx.putImageData(state.maskEdit.history[state.maskEdit.historyIndex], 0, 0);
      render();
    }
  }

  function redoMaskEdit() {
    if (state.maskEdit.historyIndex < state.maskEdit.history.length - 1 && state.maskEdit.ctx) {
      state.maskEdit.historyIndex++;
      state.maskEdit.ctx.putImageData(state.maskEdit.history[state.maskEdit.historyIndex], 0, 0);
      render();
    }
  }

  function resetMaskToAuto() {
    if (!state.maskEdit.canvas || !state.maskEdit.ctx || !state.maskUrl) return;
    const ctx = state.maskEdit.ctx;
    const canvas = state.maskEdit.canvas;
    const maskImg = new Image();
    maskImg.crossOrigin = 'anonymous';
    maskImg.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(maskImg, 0, 0, canvas.width, canvas.height);
      saveToHistory();
    };
    maskImg.src = state.maskUrl;
  }

  async function applyMaskAndRender() {
    if (!state.maskEdit.canvas) return;
    // Export canvas as base64
    state.maskEdit.customMaskData = state.maskEdit.canvas.toDataURL('image/png');
    state.maskEdit.enabled = false;
    // Re-render with custom mask
    performRender();
  }

  // --- Logic ---

  async function loadStyles() {
    if (!apiKey) {
      console.warn("Skipping loadStyles - no API key");
      return;
    }
    state.loadingStyles = true;
    render();
    try {
      const res = await fetch(`${API_BASE}/epoxy/styles/public`, {
        headers: { 'X-API-KEY': apiKey! }
      });
      if (res.ok) {
        state.styles = await res.json();
      } else if (res.status === 401) {
        console.error('Failed to load styles: 401 Unauthorized');
        state.error = 'Preview token expired — please reopen from dashboard';
      } else {
        console.error('Failed to load styles', res.status);
        state.error = `Failed to load styles (${res.status})`;
      }
    } catch (e) {
      console.error(e);
      state.error = 'Network error loading styles';
    } finally {
      state.loadingStyles = false;
      render();
    }
  }

  function selectStyle(id: string) {
    state.selectedStyleId = id;
    render();
  }

  async function performRender() {
    state.step = 'rendering';
    render();

    try {
      const formData = new FormData();
      if (uploadedImageId) {
        formData.append('image_id', uploadedImageId);
      } else {
        throw new Error("Upload incomplete. Please wait.");
      }

      if (state.selectedStyleId) {
        formData.append('style_id', state.selectedStyleId);
      }

      // Pass Tuning Params
      formData.append('blend_strength', state.tuning.blend_strength.toString());
      formData.append('finish', state.tuning.finish);

      // Pass Debug Flag
      if (debugMode) {
        formData.append('debug', 'true');
      }

      // Pass Custom Mask
      if (state.maskEdit.customMaskData) {
        formData.append('custom_mask', state.maskEdit.customMaskData);
      }

      // Pass Project ID (from API key)
      // API Key format: proj_{projectId_last8}
      // But we need the full UUID?
      // Wait, the API Key (X-API-KEY) validates the project in deps.
      // But epoxy.py needs project_id to look up config.
      // The deps.get_project_from_api_key puts the project in request.state?
      // No... epoxy.py takes project_id as Form param.
      // We don't have the full UUID in the widget usually. the apiKey variable might be the JWT token or the short key.

      // Attempt to extract project_id if it was passed in init config
      // But we didn't save it in state. Let's look at initWidget.
      // The script tag usually has data-project-id.

      const scriptEl = document.getElementById('skisplace-config') || document.querySelector('script[src*="widget.js"]');
      const projectId = scriptEl?.getAttribute('data-project-id');
      if (projectId) {
        formData.append('project_id', projectId);
      } else {
        console.warn("SkisPlace: data-project-id not found, AI config may not load.");
      }

      // Call /epoxy/preview
      const res = await fetch(`${API_BASE}/epoxy/preview`, {
        method: 'POST',
        headers: {
          'X-API-KEY': apiKey!
        },
        body: formData
      });

      if (!res.ok) throw new Error('Render failed');
      const data = await res.json();

      state.resultUrl = data.result_url;

      // Capture Debug Info
      if (debugMode) {
        state.maskUrl = data.mask_url;
        state.debugData = data;
      }

      state.step = 'result';

    } catch (e: any) {
      console.error(e);
      state.error = e.message || 'Error generating preview';
    }
    render();
  }

  // Initial Render
  render();
}

initWidget();
