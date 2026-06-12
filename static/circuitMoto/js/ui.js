// === static/circuitMoto/js/ui.js ===

(function(w){
  const $ = (sel,root=document)=>root.querySelector(sel);

  // —— TOAST
  function toast(message, {type='success', title, duration=2800}={}){
    const wrap = document.createElement('div');
    wrap.className = `toast-center type-${type}`;
    wrap.innerHTML = `
      <div class="toast-card" role="alertdialog" aria-live="polite">
        <div class="toast-ico" aria-hidden="true">${icon(type)}</div>
        <div class="toast-content">
          <div class="toast-title">${title || label(type)}</div>
          <div class="toast-msg">${message || ''}</div>
        </div>
        <button class="toast-close" type="button" aria-label="Fermer">×</button>
      </div>`;
    document.body.appendChild(wrap);
    document.body.classList.add('layer-open');
    wrap.classList.add('show');

    const close = ()=>{ wrap.classList.remove('show'); wrap.remove(); document.body.classList.remove('layer-open'); };
    $('.toast-close', wrap).addEventListener('click', close);
    wrap.addEventListener('click', (e)=>{ if(e.target===wrap) close(); });
    document.addEventListener('keydown', function esc(e){ if(e.key==='Escape'){ close(); document.removeEventListener('keydown', esc);} });
    if(duration>0) setTimeout(close, duration);
  }

  // —— MODAL (confirm)
  function confirm(message, {title='Confirmer', type='warning', confirmText='Continuer', cancelText='Annuler'}={}){
    return new Promise(resolve=>{
      const ov = document.createElement('div');
      ov.className = `modal-overlay type-${type}`;
      ov.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="modal-head">
            <div class="modal-ico" aria-hidden="true">${icon(type)}</div>
            <h3 id="modal-title" class="modal-title">${title}</h3>
          </div>
          <div class="modal-body">${message||''}</div>
          <div class="modal-actions">
            <button data-act="cancel" class="btn btn-secondary" type="button">${cancelText}</button>
            <button data-act="ok" class="btn btn-primary" type="button">${confirmText}</button>
          </div>
        </div>`;
      document.body.appendChild(ov);
      ov.classList.add('active');
      document.body.classList.add('layer-open');

      const ok = ov.querySelector('[data-act="ok"]');
      const ko = ov.querySelector('[data-act="cancel"]');
      ok.focus();

      function cleanup(v){ ov.remove(); document.body.classList.remove('layer-open'); resolve(v); }
      ok.addEventListener('click', ()=>cleanup(true));
      ko.addEventListener('click', ()=>cleanup(false));
      ov.addEventListener('click', (e)=>{ if(e.target===ov) cleanup(false); });
      document.addEventListener('keydown', function esc(e){ if(e.key==='Escape'){ cleanup(false); document.removeEventListener('keydown', esc);} });
    });
  }

  function icon(type){
    if(type==='success') return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M22 11.1V12A10 10 0 1 1 12 2"/><path d="m9 12 2 2 4-4"/></svg>';
    if(type==='warning') return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="m12 9 0 4"/><path d="m12 17 .01 0"/><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>';
    if(type==='error')   return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>';
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>';
  }
  function label(type){
    return type==='success' ? 'Succès' : type==='error' ? 'Erreur' : type==='warning' ? 'Attention' : 'Information';
  }

  // static/circuitMoto/js/ui.js
  document.addEventListener('DOMContentLoaded', () => {
    const rail = document.querySelector('.step-indicator');
    const active = document.querySelector('.step-indicator .step.active');
    if (rail && active && window.matchMedia('(max-width:768px)').matches) {
      active.scrollIntoView({behavior:'smooth', inline:'center', block:'nearest'});
    }
  });


  w.UI = { toast, confirm };
})(window);