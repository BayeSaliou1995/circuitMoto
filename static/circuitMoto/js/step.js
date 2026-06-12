// === static/circuitMoto/js/step.js ===
(function () {
  function isMobile() {
    return window.matchMedia('(max-width:768px)').matches;
  }

  function focusFirstErrorField(form) {
    // Cherche la première erreur près d'un champ
    const errList = form.querySelector('.errorlist, .error-message');
    if (!errList) return;

    // Si c'est une errorlist liée à un champ
    let wrapper = errList.closest('.form-group, .checkbox-line, .step-section') || form;

    // Essaie de trouver un champ dans ce wrapper
    let field = wrapper.querySelector('input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])');

    // Fallback: premier champ du form
    if (!field) {
      field = form.querySelector('input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])');
    }

    if (field) {
      setTimeout(() => {
        try { field.focus({ preventScroll: true }); } catch (e) {}
        try { field.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {}
      }, 80);
    }
  }

  function autoGrowTextarea(textarea) {
    const resize = () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 420) + 'px';
    };
    resize();
    textarea.addEventListener('input', resize, { passive: true });
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 1) Mobile : centre automatiquement l'étape active dans le rail
    const rail = document.querySelector('.step-indicator');
    const active = document.querySelector('.step-indicator .step.active');
    if (rail && active && isMobile()) {
      try {
        active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      } catch (e) {}
    }

    // 2) Focus sur le 1er champ en erreur
    const form = document.querySelector('form.form-step');
    if (form) {
      focusFirstErrorField(form);
    }

    // 3) Medical: auto-grow notes textarea si présent
    const notes = document.querySelector('textarea[name="notes"], textarea#id_notes');
    if (notes) {
      autoGrowTextarea(notes);
    }
  });
})();


// ===============================
// Documents step (upload UX)
// ===============================
(function(){
  const byId = (id) => document.getElementById(id);

  const fmtBytes = (n) => {
    if (!n && n !== 0) return "";
    const units = ["octets","Ko","Mo","Go"];
    let i = 0, v = n;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(1)) + " " + units[i];
  };

  const getMaxMb = (inp) => {
    const v = parseInt(inp.getAttribute("data-max-mb") || "0", 10);
    return Number.isFinite(v) ? v : 0;
  };

  const allowedExt = (inp) => {
    const acc = (inp.getAttribute("accept") || "").toLowerCase();
    return acc.split(",").map(s => s.trim()).filter(Boolean);
  };

  const hasAllowedExt = (name, exts) => {
    const lower = (name || "").toLowerCase();
    return exts.length === 0 || exts.some(e => lower.endsWith(e));
  };

  function initDocumentsStep(){
    const docForm = document.getElementById("doc-form");
    if (!docForm) return; // pas sur la page documents

    // taille max globale
    const firstFile = docForm.querySelector('input[type="file"]');
    if (firstFile){
      const mm = getMaxMb(firstFile);
      const el = document.getElementById("js-max-mb");
      if (el && mm) el.textContent = String(mm);
    }

    // Remplacer -> reveal + click
    docForm.querySelectorAll(".js-replace").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-target");
        const input = byId(id);
        if (!input) return;
        const wrapper = input.closest(".file-upload");
        if (wrapper) wrapper.removeAttribute("data-collapsed");
        input.click();
      });
    });

    // Retirer
    docForm.querySelectorAll(".js-clear").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-target");
        const inp = byId(id);
        if (!inp) return;

        inp.value = "";

        const root = inp.closest(".file-upload");
        const nameBox = root?.querySelector(".file-name");
        if (nameBox) nameBox.textContent = "Aucun fichier sélectionné";

        const prev = docForm.querySelector(`.preview[data-for="${id}"]`);
        if (prev){
          prev.hidden = true;
          const img = prev.querySelector("img");
          const info = prev.querySelector(".preview-info");
          if (img) img.src = "";
          if (info) info.textContent = "";
        }

        const warn = docForm.querySelector(`.inline-warning[data-for="${id}"]`);
        if (warn){
          warn.hidden = true;
          warn.textContent = "";
        }
      });
    });

    // Change file -> validate + preview
    docForm.querySelectorAll('input[type="file"]').forEach(inp => {
      const root = inp.closest(".file-upload");
      const nameBox = root?.querySelector(".file-name");
      const preview = docForm.querySelector(`.preview[data-for="${inp.id}"]`);
      const prevImg = preview?.querySelector("img");
      const prevInfo = preview?.querySelector(".preview-info");
      const warn = docForm.querySelector(`.inline-warning[data-for="${inp.id}"]`);

      const maxMb = getMaxMb(inp);
      const exts = allowedExt(inp);

      // copie max près de chaque champ
      const maxSpan = root?.querySelector(".js-max-by-input");
      if (maxSpan && maxMb) maxSpan.textContent = String(maxMb);

      inp.addEventListener("change", () => {
        const noSel = "Aucun fichier sélectionné";

        if (warn){ warn.hidden = true; warn.textContent = ""; }
        if (preview){
          preview.hidden = true;
          if (prevImg) prevImg.src = "";
          if (prevInfo) prevInfo.textContent = "";
        }

        const f = inp.files && inp.files[0];
        if (!f){
          if (nameBox) nameBox.textContent = noSel;
          return;
        }
        if (nameBox) nameBox.textContent = f.name;

        // taille
        if (maxMb && f.size > maxMb * 1024 * 1024){
          if (warn){
            warn.hidden = false;
            warn.textContent = `Fichier trop volumineux (> ${maxMb} Mo).`;
          }
          inp.value = "";
          if (nameBox) nameBox.textContent = noSel;
          return;
        }

        // extension
        if (!hasAllowedExt(f.name, exts)){
          if (warn){
            warn.hidden = false;
            warn.textContent = `Extension non autorisée. Formats acceptés : ${exts.join(", ") || ".pdf,.jpg,.jpeg,.png"}`;
          }
          inp.value = "";
          if (nameBox) nameBox.textContent = noSel;
          return;
        }

        // warning nom long
        if (f.name.length > 80 && warn){
          warn.hidden = false;
          warn.textContent = "Nom de fichier très long : il sera éventuellement raccourci automatiquement lors de l'enregistrement.";
        }

        // preview image
        const isImg = /\.(png|jpg|jpeg)$/i.test(f.name);
        if (preview && prevInfo){
          if (isImg && prevImg){
            const url = URL.createObjectURL(f);
            prevImg.onload = () => URL.revokeObjectURL(url);
            prevImg.src = url;
            prevInfo.textContent = `Poids : ${fmtBytes(f.size)}`;
            preview.hidden = false;
          } else {
            prevInfo.textContent = `Fichier sélectionné (${fmtBytes(f.size)}). Aucun aperçu.`;
            preview.hidden = false;
          }
        }
      });
    });

    // submit state
    const submitBtn = document.getElementById("submit-btn");
    const uploading = document.getElementById("uploading");
    docForm.addEventListener("submit", () => {
      if (submitBtn){
        submitBtn.disabled = true;
        submitBtn.textContent = "Envoi…";
      }
      if (uploading) uploading.hidden = false;
    });
  }

  document.addEventListener("DOMContentLoaded", initDocumentsStep);
})();

// ===============================
// Décharge step (signature + lock submit)
// ===============================
(function(){
  function initDechargeStep(){
    const form = document.querySelector("form.js-decharge-form");
    if (!form) return;

    const canvas = document.getElementById("sigPad");
    const clearBtn = form.querySelector(".js-sig-clear");
    const hiddenId = form.getAttribute("data-sign-target");
    const hidden = hiddenId ? document.getElementById(hiddenId) : null;

    // --- Submit lock (anti double submit + loader)
    const submitBtn = form.querySelector(".js-submit-lock");
    function setLoading(){
      if (!submitBtn || submitBtn.disabled) return;
      submitBtn.disabled = true;
      submitBtn.setAttribute("aria-busy", "true");
      submitBtn.classList.add("is-loading");
      submitBtn.innerHTML = `<span class="btn-spinner" aria-hidden="true"></span><span> Envoi…</span>`;
      form.querySelectorAll('button[name="wizard_goto_step"]').forEach(b => b.disabled = true);
    }

    // --- Signature
    if (!canvas || !hidden) {
      // même si pas de canvas, on garde le lock pro
      form.addEventListener("submit", () => {
        if (form.checkValidity && !form.checkValidity()) return;
        setTimeout(setLoading, 0);
      });
      return;
    }

    const ctx = canvas.getContext("2d");
    let drawing = false;
    let hasStroke = false;
    let last = null;

    function setCtxStyle(){
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      const textColor = getComputedStyle(document.documentElement).getPropertyValue("--text").trim();
      ctx.strokeStyle = textColor || "#111";
    }

    // Retina resize (sans casser la signature sur resize)
    function resizeCanvas(){
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      const rect = canvas.getBoundingClientRect();

      const tmp = document.createElement("canvas");
      tmp.width = canvas.width;
      tmp.height = canvas.height;
      const tctx = tmp.getContext("2d");
      if (canvas.width && canvas.height) tctx.drawImage(canvas, 0, 0);

      canvas.width = Math.floor(rect.width * ratio);
      canvas.height = Math.floor(rect.height * ratio);

      ctx.setTransform(1,0,0,1,0,0);
      ctx.scale(ratio, ratio);
      setCtxStyle();

      // re-draw previous
      if (tmp.width && tmp.height) {
        ctx.drawImage(tmp, 0, 0, rect.width, rect.height);
      } else {
        ctx.clearRect(0,0,rect.width,rect.height);
      }
    }

    function pos(e){
      const r = canvas.getBoundingClientRect();
      if (e.touches && e.touches.length){
        const t = e.touches[0];
        return { x: t.clientX - r.left, y: t.clientY - r.top };
      }
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    }

    function start(e){
      e.preventDefault();
      drawing = true;
      last = pos(e);
    }

    function move(e){
      if (!drawing) return;
      const p = pos(e);
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      last = p;
      hasStroke = true;
    }

    function end(){
      drawing = false;
      last = null;
    }

    // Init sizes
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Events mouse
    canvas.addEventListener("mousedown", start);
    canvas.addEventListener("mousemove", move);
    canvas.addEventListener("mouseup", end);
    canvas.addEventListener("mouseleave", end);

    // Events touch
    canvas.addEventListener("touchstart", start, { passive:false });
    canvas.addEventListener("touchmove", move, { passive:false });
    canvas.addEventListener("touchend", end);

    // Clear
    if (clearBtn){
      clearBtn.addEventListener("click", () => {
        const r = canvas.getBoundingClientRect();
        ctx.clearRect(0,0,r.width,r.height);
        hidden.value = "";
        hasStroke = false;
      });
    }

    // Submit: export PNG base64 + lock button
    form.addEventListener("submit", () => {
      if (form.checkValidity && !form.checkValidity()) return;

      if (hasStroke){
        try{
          hidden.value = canvas.toDataURL("image/png");
        }catch(e){
          // ignore
        }
      }else{
        // si pas signé, on laisse hidden vide (Django gère si required)
        hidden.value = hidden.value || "";
      }

      setTimeout(setLoading, 0);
    });
  }

  document.addEventListener("DOMContentLoaded", initDechargeStep);
})();


