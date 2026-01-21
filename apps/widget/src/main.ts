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

  const configScript = document.getElementById('skisplace-config');
  if (configScript) {
    apiBase = configScript.getAttribute('data-api-base');
    apiKey = configScript.getAttribute('data-api-key');
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
    styles: [] as EpoxyStyle[],
    selectedStyleId: null as string | null,
    resultUrl: null as string | null,
    error: null as string | null
  };

  async function render() {
    // Clear container
    container!.innerHTML = '<div class="sp-box"></div>';
    const box = container!.querySelector('.sp-box')!;

    // Header
    const header = document.createElement('div');
    header.className = 'sp-header';
    header.innerHTML = `<h3>Epoxy Visualizer</h3>`;
    box.appendChild(header);

    // Content Body
    const content = document.createElement('div');
    content.className = 'sp-content-body';
    box.appendChild(content);

    // Error Overlay
    if (state.error) {
      content.innerHTML = `<div class="sp-error-msg">${state.error}</div>`;
      const btn = document.createElement('button');
      btn.className = 'sp-btn secondary';
      btn.innerText = 'Try Again';
      btn.onclick = () => { state.error = null; state.step = 'upload'; render(); };
      content.appendChild(btn);
      return;
    }

    if (state.step === 'upload') {
      content.innerHTML = `
        <div class="sp-upload-zone">
          <p>Take a photo of your room or upload one to get started.</p>
          <input type="file" id="sp-file-input" accept="image/*" />
          <label for="sp-file-input" class="sp-btn primary">Select Photo</label>
        </div>
      `;
      const input = content.querySelector('#sp-file-input') as HTMLInputElement;
      input.onchange = async (e: any) => {
        if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          state.uploadedImage = file;
          state.uploadedImageUrl = URL.createObjectURL(file);

          // Trigger Upload API
          try {
            const upData = new FormData();
            upData.append('file', file);

            // Optimistic move to styles while uploading in background? 
            // Or block? Let's block for MVP safety or add a loading spinner.
            // For now, let's just fire it and hope it finishes before they click "Visualize".
            // Better: move to styles, but disable "Visualize" until upload done.
            state.step = 'styles';
            loadStyles();

            const res = await fetch(`${API_BASE}/epoxy/uploads`, {
              method: 'POST',
              headers: { 'X-API-KEY': apiKey! },
              body: upData
            });
            if (res.ok) {
              const data = await res.json();
              uploadedImageId = data.id; // Store globally or in state
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
      };
    }
    else if (state.step === 'styles') {
      // Preview
      if (state.uploadedImageUrl) {
        const preview = document.createElement('img');
        preview.src = state.uploadedImageUrl;
        preview.className = 'sp-mini-preview';
        content.appendChild(preview);
      }

      const title = document.createElement('h4');
      title.innerText = 'Choose a Style';
      content.appendChild(title);

      if (state.styles.length === 0) {
        content.innerHTML += `<div class="sp-loading-sm">Loading styles...</div>`;
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
      nextBtn.disabled = !state.selectedStyleId;
      nextBtn.innerText = 'Visualize';
      nextBtn.onclick = performRender;
      actions.appendChild(nextBtn);

      content.appendChild(actions);
    }
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
             </div>
             
             <div class="sp-img-display">
                <img src="${state.resultUrl}" class="sp-main-img" id="sp-result-img" />
             </div>
          </div>
        `;

      // Toggle Logic
      const imgEl = content.querySelector('#sp-result-img') as HTMLImageElement;
      const btns = content.querySelectorAll('.sp-toggle-btn');

      btns.forEach(btn => {
        (btn as HTMLButtonElement).onclick = () => {
          btns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');

          const view = (btn as HTMLButtonElement).dataset.view;
          if (view === 'original') {
            imgEl.src = state.uploadedImageUrl!;
          } else {
            imgEl.src = state.resultUrl!;
          }
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
    render(); // Show loading state inside styles step
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
    }
    render();
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
