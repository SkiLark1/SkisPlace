import './style.css'

interface EpoxyStyle {
  id: string
  name: string
  cover_image_url?: string
}

async function initWidget() {
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

  if (!apiKey) {
    container.innerHTML = `<div class="sp-error">Configuration missing (API Key)</div>`;
    return;
  }

  // --- 2. State & Render ---
  let uploadedImageId: string | null = null;

  let state = {
    step: 'upload' as 'upload' | 'styles' | 'rendering' | 'result',
    uploadedImage: null as File | null,
    uploadedImageUrl: null as string | null,
    loadingStyles: false as boolean,
    styles: [] as EpoxyStyle[],
    selectedStyleId: null as string | null,
    resultUrl: null as string | null,
    maskUrl: null as string | null,
    debugData: null as any | null,
    error: null as string | null,
    // User Tuning (session-scoped)
    tuning: {
      blend_strength: 0.85,
      finish: 'satin' as 'gloss' | 'satin' | 'matte'
    },
    // Mask Editing (session-scoped)
    maskEdit: {
      enabled: false,
      mode: 'add' as 'add' | 'remove',
      brushSize: 30,
      canvas: null as HTMLCanvasElement | null,
      ctx: null as CanvasRenderingContext2D | null,
      history: [] as ImageData[],
      historyIndex: -1,
      customMaskData: null as string | null  // Base64 PNG
    }
  };

  async function render() {
    // ... (Container clearing and Header setup - kept same)
    container!.innerHTML = '<div class="sp-box"></div>';
    const box = container!.querySelector('.sp-box')!;

    // Header
    const header = document.createElement('div');
    header.className = 'sp-header';
    header.innerHTML = `<h3>Epoxy Visualizer${debugMode ? ' <span style="font-size:0.7em; color: orange;">(DEBUG)</span>' : ''}</h3>`;
    box.appendChild(header);

    // Content Body
    const content = document.createElement('div');
    content.className = 'sp-content-body';
    box.appendChild(content);

    // Error Overlay
    if (state.error) {
      // ... (Error render code kept same)
      content.innerHTML = `<div class="sp-error-msg">${state.error}</div>`;
      const btn = document.createElement('button');
      btn.className = 'sp-btn secondary';
      btn.innerText = 'Try Again';
      btn.onclick = () => { state.error = null; state.step = 'upload'; render(); };
      content.appendChild(btn);
      return;
    }

    if (state.step === 'upload') {
      // ... (Upload step kept same until handleFileSelect)
      content.innerHTML = `
        <div class="sp-upload-zone">
          <p>Take a photo of your room or upload one to get started.</p>
          <input type="file" id="sp-file-input" accept="image/*" />
          <label for="sp-file-input" class="sp-btn primary">Select Photo</label>
          
          <div style="margin: 15px 0; color: #888; font-size: 0.8em; text-transform: uppercase;">OR</div>
          
          <button id="sp-sample-btn" class="sp-btn secondary">Load Sample Garage</button>
        </div>
      `;

      const input = content.querySelector('#sp-file-input') as HTMLInputElement;
      input.onchange = async (e: any) => {
        if (e.target.files && e.target.files[0]) {
          handleFileSelect(e.target.files[0]);
        }
      };

      const sampleBtn = content.querySelector('#sp-sample-btn') as HTMLButtonElement;
      sampleBtn.onclick = async () => {
        sampleBtn.disabled = true;
        sampleBtn.innerText = 'Loading...';

        try {
          const response = await fetch('/samples/garage1.jpg');
          if (!response.ok) throw new Error('Sample not found');
          const blob = await response.blob();
          const file = new File([blob], "garage1.jpg", { type: "image/jpeg" });
          handleFileSelect(file);
        } catch (error) {
          console.error(error);
          state.error = 'Failed to load sample';
          render();
        }
      };

      async function handleFileSelect(file: File) {
        state.uploadedImage = file;
        state.uploadedImageUrl = URL.createObjectURL(file);

        try {
          const upData = new FormData();
          upData.append('file', file);

          state.step = 'styles';
          loadStyles(); // Will trigger re-render with loading state

          const res = await fetch(`${API_BASE}/epoxy/uploads`, {
            method: 'POST',
            headers: { 'X-API-KEY': apiKey! },
            body: upData
          });
          if (res.ok) {
            const data = await res.json();
            uploadedImageId = data.id;
            console.log('Upload complete:', uploadedImageId);
          } else {
            console.error('Upload failed');
            state.error = 'Upload failed';
            render();
          }

        } catch (err) {
          console.error(err);
          state.error = 'Upload failed';
        }
      }
    }
    else if (state.step === 'styles') {
      // Preview Tiny
      if (state.uploadedImageUrl) {
        const preview = document.createElement('img');
        preview.src = state.uploadedImageUrl;
        preview.className = 'sp-mini-preview';
        content.appendChild(preview);
      }

      const title = document.createElement('h4');
      title.innerText = 'Choose a Style';
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
            <p>No styles configured for this project.</p>
            <button class="sp-btn secondary" id="sp-retry-styles" style="margin-top:10px;">Retry</button>
          </div>
        `;
        // Defer click handler attachment
        setTimeout(() => {
          const retry = content.querySelector('#sp-retry-styles') as HTMLButtonElement;
          if (retry) retry.onclick = loadStyles;
        }, 0);
      } else {
        const grid = document.createElement('div');
        grid.className = 'sp-style-grid';
        state.styles.forEach(style => {
          const card = document.createElement('div');
          card.className = `sp-style-card ${state.selectedStyleId === style.id ? 'selected' : ''}`;
          card.onclick = () => selectStyle(style.id);

          if (style.cover_image_url) {
            const img = document.createElement('img');
            img.src = style.cover_image_url;
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

      // Tuning Panel (show when style selected)
      if (state.selectedStyleId) {
        const tuningPanel = document.createElement('div');
        tuningPanel.className = 'sp-tuning-panel';
        tuningPanel.innerHTML = `
          <div class="sp-tuning-header">Adjust Settings</div>
          <div class="sp-tuning-row">
            <label>Strength</label>
            <input type="range" id="sp-strength-slider" min="0.3" max="1.0" step="0.05" value="${state.tuning.blend_strength}" />
            <span id="sp-strength-val">${(state.tuning.blend_strength * 100).toFixed(0)}%</span>
          </div>
          <div class="sp-tuning-row">
            <label>Finish</label>
            <div class="sp-finish-btns">
              <button class="sp-finish-btn ${state.tuning.finish === 'gloss' ? 'active' : ''}" data-finish="gloss">Gloss</button>
              <button class="sp-finish-btn ${state.tuning.finish === 'satin' ? 'active' : ''}" data-finish="satin">Satin</button>
              <button class="sp-finish-btn ${state.tuning.finish === 'matte' ? 'active' : ''}" data-finish="matte">Matte</button>
            </div>
          </div>
        `;
        content.appendChild(tuningPanel);

        // Bind events after DOM insert
        setTimeout(() => {
          const slider = document.getElementById('sp-strength-slider') as HTMLInputElement;
          const valSpan = document.getElementById('sp-strength-val');
          if (slider) {
            slider.oninput = () => {
              state.tuning.blend_strength = parseFloat(slider.value);
              if (valSpan) valSpan.innerText = (state.tuning.blend_strength * 100).toFixed(0) + '%';
            };
          }
          const finishBtns = document.querySelectorAll('.sp-finish-btn');
          finishBtns.forEach((btn) => {
            (btn as HTMLButtonElement).onclick = () => {
              state.tuning.finish = (btn as HTMLButtonElement).dataset.finish as any;
              render();
            };
          });
        }, 0);
      }

      // Actions
      const actions = document.createElement('div');
      actions.className = 'sp-actions';

      const backBtn = document.createElement('button');
      backBtn.className = 'sp-btn text';
      backBtn.innerText = 'Back';
      backBtn.onclick = () => { state.step = 'upload'; state.selectedStyleId = null; render(); };
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
              ${state.maskUrl ? `<div class="sp-mask-tint" id="sp-mask-tint" style="display:none; opacity: 0.5; -webkit-mask-image: url('${state.maskUrl}'); mask-image: url('${state.maskUrl}');"></div>` : ''}
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
              'heuristic': 'Heuristic',
              'heuristic_vignette': 'Heuristic (Vignette)',
              'ai_direct': 'AI (Direct)',
              'ai_refined': 'AI (Refined)',
              'ai_hybrid_fallback': 'AI (Hybrid)',
              'user': 'User Edited'
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
      const maskTint = content.querySelector('#sp-mask-tint') as HTMLDivElement | null;
      const btns = content.querySelectorAll('.sp-toggle-btn');
      btns.forEach(btn => {
        (btn as HTMLButtonElement).onclick = () => {
          btns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const view = (btn as HTMLButtonElement).dataset.view;
          if (view === 'original') {
            imgEl.src = state.uploadedImageUrl!;
            if (maskTint) maskTint.style.display = 'none';
          } else if (view === 'mask') {
            imgEl.src = state.maskUrl!;
            if (maskTint) maskTint.style.display = 'none';
          } else if (view === 'overlay') {
            imgEl.src = state.uploadedImageUrl!;
            if (maskTint) maskTint.style.display = 'block';
          } else {
            imgEl.src = state.resultUrl!;
            if (maskTint) maskTint.style.display = 'none';
          }
        };
      });

      // Mask Opacity Slider
      if (debugMode && state.maskUrl) {
        const opacitySlider = document.getElementById('sp-mask-opacity') as HTMLInputElement;
        const opacityVal = document.getElementById('sp-opacity-val');
        if (opacitySlider && maskTint) {
          opacitySlider.oninput = () => {
            const val = parseFloat(opacitySlider.value);
            maskTint.style.opacity = val.toString();
            if (opacityVal) opacityVal.innerText = (val * 100).toFixed(0) + '%';
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
          const toggleBtn = document.getElementById('sp-toggle-edit');
          if (toggleBtn) {
            toggleBtn.onclick = () => {
              state.maskEdit.enabled = !state.maskEdit.enabled;

              // Lock view to Original when editing
              if (state.maskEdit.enabled) {
                const imgEl = document.getElementById('sp-result-img') as HTMLImageElement;
                if (imgEl && state.uploadedImageUrl) {
                  imgEl.src = state.uploadedImageUrl;
                }
              }

              render();
            };
          }

          if (state.maskEdit.enabled) {
            // Brush mode buttons
            document.querySelectorAll('.sp-brush-btn').forEach(btn => {
              (btn as HTMLButtonElement).onclick = () => {
                state.maskEdit.mode = (btn as HTMLButtonElement).dataset.mode as 'add' | 'remove';
                render();
              };
            });

            // Brush size slider
            const brushSlider = document.getElementById('sp-brush-size') as HTMLInputElement;
            if (brushSlider) {
              brushSlider.oninput = () => {
                state.maskEdit.brushSize = parseInt(brushSlider.value);
                const span = brushSlider.nextElementSibling;
                if (span) span.textContent = state.maskEdit.brushSize + 'px';
              };
            }

            // Undo/Redo
            const undoBtn = document.getElementById('sp-undo');
            const redoBtn = document.getElementById('sp-redo');
            if (undoBtn) undoBtn.onclick = undoMaskEdit;
            if (redoBtn) redoBtn.onclick = redoMaskEdit;

            // Reset buttons (AI or Heuristic)
            const resetAIBtn = document.getElementById('sp-reset-ai');
            const resetHeuristicBtn = document.getElementById('sp-reset-heuristic');
            if (resetAIBtn) resetAIBtn.onclick = resetMaskToAuto; // Same function for now
            if (resetHeuristicBtn) resetHeuristicBtn.onclick = resetMaskToAuto;

            // Apply
            const applyBtn = document.getElementById('sp-apply-mask');
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
