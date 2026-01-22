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

  const configScript = document.getElementById('skisplace-config');
  if (configScript) {
    apiBase = configScript.getAttribute('data-api-base');
    apiKey = configScript.getAttribute('data-api-key');
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
    // Also check attributes on the script tag itself if configScript wasn't found or attribute missing
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
    error: null as string | null
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
      // ... (Result view code kept same)
      content.innerHTML = `
             <div class="sp-result-container">
                <div class="sp-view-toggle">
                  <button class="sp-toggle-btn active" data-view="preview">Preview</button>
                  <button class="sp-toggle-btn" data-view="original">Original</button>
                  ${state.maskUrl ? '<button class="sp-toggle-btn" data-view="mask">Mask (Debug)</button>' : ''}
                </div>
                
                <div class="sp-img-display">
                   <img src="${state.resultUrl}" class="sp-main-img" id="sp-result-img" />
                </div>
             </div>
           `;
      // ... (Debug and Actions logic kept same but re-inserted for completeness if replace block covers it, 
      // but wait, I can target specific functions or blocks to be safe. 
      // The provided code is mostly monolithic in one file. I will target the `render` function and `loadStyles`.)
      // Actually, I'll just rewrite the `loadStyles` and `selectStyle` area to capture `render` changes in `styles` step.

      // Debug Data Section
      if (debugMode && state.debugData) {
        const debugBox = document.createElement('div');
        debugBox.style.marginTop = '20px';
        debugBox.style.padding = '10px';
        debugBox.style.background = '#f1f1f1';
        debugBox.style.border = '1px solid #ccc';
        debugBox.style.fontSize = '12px';
        debugBox.style.overflow = 'auto';
        debugBox.style.maxHeight = '200px';
        debugBox.innerHTML = `<strong>Debug Response:</strong><pre>${JSON.stringify(state.debugData, null, 2)}</pre>`;
        content.appendChild(debugBox);
      }

      // Toggle Logic
      const imgEl = content.querySelector('#sp-result-img') as HTMLImageElement;
      const btns = content.querySelectorAll('.sp-toggle-btn');
      btns.forEach(btn => {
        (btn as HTMLButtonElement).onclick = () => {
          btns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const view = (btn as HTMLButtonElement).dataset.view;
          if (view === 'original') imgEl.src = state.uploadedImageUrl!;
          else if (view === 'mask') imgEl.src = state.maskUrl!;
          else imgEl.src = state.resultUrl!;
        };
      });

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

  // --- Logic ---

  async function loadStyles() {
    state.loadingStyles = true;
    render();
    try {
      const res = await fetch(`${API_BASE}/styles/public`, {
        headers: { 'X-API-KEY': apiKey! }
      });
      if (res.ok) {
        state.styles = await res.json();
      } else {
        console.error('Failed to load styles', res.status);
      }
    } catch (e) {
      console.error(e);
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

      // Pass Debug Flag
      if (debugMode) {
        formData.append('debug', 'true');
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
