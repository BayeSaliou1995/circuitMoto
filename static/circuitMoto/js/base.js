// === static/circuitMoto/js/base.js ===
(function(){
  // Fermer les messages inline + optionnel: toast auto pour erreurs/avertissements
  document.addEventListener('DOMContentLoaded', ()=>{
    document.querySelectorAll('.msg-close').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const card = btn.closest('.msg-card'); if(card) card.style.display='none';
      });
    });

    if(window.UI && typeof UI.toast==='function'){
      document.querySelectorAll('.msg-card').forEach(card=>{
        const type = card.classList.contains('error') ? 'error'
                  : card.classList.contains('warning') ? 'warning'
                  : card.classList.contains('success') ? 'success' : 'info';
        const text = card.querySelector('.msg-text')?.textContent?.trim();
        if((type==='error' || type==='warning') && text){
          UI.toast(text, {type, duration: 3800});
        }
      });
    }

    // File input: nom du fichier
    document.querySelectorAll('.file-upload-input').forEach(input=>{
      input.addEventListener('change', function(){
        const name = this.files?.[0]?.name || 'Aucun fichier sélectionné';
        const wrap = this.closest('.file-upload');
        const out  = wrap?.querySelector('.file-name') || wrap?.querySelector('.helptext');
        if(out){ out.textContent = name; out.style.color = this.files?.[0] ? 'var(--primary)' : 'var(--text-light)'; }
      });
    });


    document.addEventListener('mousedown', e => {
      const b = e.target.closest('.btn'); if(!b) return;
      b.style.transform = 'translateY(0) scale(.99)';
    });
    document.addEventListener('mouseup',  e => {
      const b = e.target.closest('.btn'); if(!b) return;
      b.style.transform = '';
    });


    // Floating CTA (si présent)
    const cta = document.querySelector('.floating-btn');
    if(cta){
      let lastY = window.pageYOffset || 0;
      window.addEventListener('scroll', ()=>{
        const curY = window.pageYOffset || 0;
        cta.style.transform = curY > lastY ? 'translateY(100px)' : 'translateY(0)';
        lastY = curY;
      }, {passive:true});
    }
  });
})();