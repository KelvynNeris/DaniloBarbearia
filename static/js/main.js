// Script leve: menu hamburguer, ano no rodapé e validação simples para formulários
document.addEventListener('DOMContentLoaded', function(){
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.querySelector('.site-nav');
  if(toggle && nav){
    toggle.addEventListener('click', function(){
      var isOpen = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
    // Fechar menu ao clicar em um link
    nav.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click', function(){
        if(nav.classList.contains('open')){
          nav.classList.remove('open');
          toggle.setAttribute('aria-expanded','false');
        }
      })
    })
    // Botão de fechar dentro do nav
    var navClose = document.querySelector('.nav-close');
    if(navClose){
      navClose.addEventListener('click', function(){
        if(nav.classList.contains('open')){
          nav.classList.remove('open');
          toggle.setAttribute('aria-expanded','false');
        }
      });
    }
  }

  // Ano no rodapé
  var anoEl = document.getElementById('ano');
  if(anoEl) anoEl.textContent = new Date().getFullYear();

  // Formulário de contato (se existir): validação simples e simulação de envio
  var form = document.getElementById('contactForm');
  var status = document.getElementById('formStatus');
  if(form){
    form.addEventListener('submit', function(e){
      e.preventDefault();
      status.textContent = '';
      var nome = form.querySelector('#nome');
      var tel = form.querySelector('#telefone');
      if(!nome.value.trim() || !tel.value.trim()){
        status.textContent = 'Por favor, preencha nome e telefone.';
        return;
      }
      // Simula envio
      var btn = form.querySelector('button[type="submit"]');
      var prev = btn.textContent;
      btn.disabled = true; btn.textContent = 'Enviando...';
      setTimeout(function(){
        btn.disabled = false; btn.textContent = prev;
        status.textContent = 'Mensagem enviada! Entraremos em contato pelo telefone.';
        form.reset();
      },1200);
    })
  }

  /* Modal de agendamento */
  var openBtns = document.querySelectorAll('.open-modal');
  var modal = document.getElementById('bookingModal');
  var bookingForm = document.getElementById('bookingForm');
  var bookingStatus = document.getElementById('bookingStatus');
  var closeBtn = modal ? modal.querySelector('.modal-close') : null;
  var cancelBtn = document.getElementById('cancelBooking');
  var firstFocusable = bookingForm ? bookingForm.querySelector('#bNome') : null;
  var lastFocused = null;

  function openModal(trigger){
    if(!modal) return;
    lastFocused = trigger || document.activeElement;
    modal.setAttribute('aria-hidden','false');
    if(firstFocusable) firstFocusable.focus();
  }

  function closeModal(){
    if(!modal) return;
    modal.setAttribute('aria-hidden','true');
    bookingStatus.textContent = '';
    if(lastFocused) lastFocused.focus();
  }

  openBtns.forEach(function(b){ b.addEventListener('click', function(){ openModal(b); }) });

  if(closeBtn) closeBtn.addEventListener('click', closeModal);
  if(cancelBtn) cancelBtn.addEventListener('click', closeModal);

  // Fechar clicando fora do modal
  if(modal){
    modal.addEventListener('click', function(e){
      if(e.target === modal) closeModal();
    });
  }

  // Esc
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape'){
      closeModal();
      // também fecha o nav se estiver aberto
      if(nav && nav.classList.contains('open')){
        nav.classList.remove('open');
        if(toggle) toggle.setAttribute('aria-expanded','false');
      }
    }
  });

  // Submissão do booking (validação cliente) — permite submissão ao servidor para cadastro
  if(bookingForm){
    bookingForm.addEventListener('submit', function(e){
      bookingStatus.textContent = '';
      var nome = bookingForm.querySelector('#bNome');
      var tel = bookingForm.querySelector('#bTel');
      if(!nome.value.trim() || !tel.value.trim()){
        e.preventDefault();
        bookingStatus.textContent = 'Por favor, preencha nome e telefone.';
        return;
      }
      // Se passou na validação, deixar o form submeter normalmente ao servidor (/cadastro)
    });
  }

  // Service preview: combobox implementation (custom) - uses real images when available; fallback to generated SVG
  var combobox = document.getElementById('serviceCombobox');
  var comboToggle = combobox ? combobox.querySelector('.combobox-toggle') : null;
  var comboList = document.getElementById('serviceList');
  var comboItems = comboList ? Array.from(comboList.querySelectorAll('li')) : [];
  var serviceImage = document.getElementById('serviceImage');
  var serviceInfo = document.getElementById('serviceInfo');
  var selectedPrice = document.getElementById('selectedPrice');
  var serviceInput = document.getElementById('serviceInput');

  function makeServiceSVG(name, price){
    var width = 900, height = 500;
    var bg = '#0b1220';
    var accent = '#d97706';
    var escaped = name.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="'+width+'" height="'+height+'">'
      + '<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#071124"/><stop offset="1" stop-color="#0b1220"/></linearGradient></defs>'
      + '<rect width="100%" height="100%" fill="url(#g)" />'
      + '<text x="50%" y="45%" font-family="Arial, Helvetica, sans-serif" font-size="44" fill="white" text-anchor="middle">'+escaped+'</text>'
      + '<text x="50%" y="65%" font-family="Arial, Helvetica, sans-serif" font-size="28" fill="'+accent+'" text-anchor="middle">R$ '+price+'</text>'
      + '</svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  // Combobox helper functions
  function setActiveOption(index){
    comboItems.forEach(function(it, i){
      var sel = (i === index);
      it.setAttribute('aria-selected', sel ? 'true' : 'false');
      if(sel) it.scrollIntoView({block:'nearest'});
    });
  }

  function selectOption(index){
    var it = comboItems[index];
    if(!it) return;
    var value = it.getAttribute('data-value');
    var name = it.textContent || value;
    var price = it.getAttribute('data-price') || '';
    var img = it.getAttribute('data-image');
    // update hidden input
    if(serviceInput) serviceInput.value = value;
    // update label
    if(comboToggle){
      var lbl = comboToggle.querySelector('#comboboxLabel');
      if(lbl) lbl.textContent = name;
    }
    // update preview
    if(serviceImage){ serviceImage.src = img ? img : makeServiceSVG(name, price); }
    if(serviceInfo){ serviceInfo.textContent = name; }
    if(selectedPrice){ selectedPrice.textContent = price ? 'Preço: R$ ' + price : ''; }
    // close
    closeCombobox();
  }

  function openCombobox(){
    if(!combobox) return;
    combobox.classList.add('open');
    combobox.setAttribute('aria-expanded','true');
    if(comboToggle) comboToggle.setAttribute('aria-expanded','true');
    comboList.style.display = 'block';
  }

  function closeCombobox(){
    if(!combobox) return;
    combobox.classList.remove('open');
    combobox.setAttribute('aria-expanded','false');
    if(comboToggle) comboToggle.setAttribute('aria-expanded','false');
    if(comboList) comboList.style.display = 'none';
  }

  if(comboToggle && comboList){
    var current = 0;
    // initial select: choose first
    if(comboItems.length > 0){
      selectOption(0);
      current = 0;
    }

    comboToggle.addEventListener('click', function(e){
      var expanded = combobox.classList.contains('open');
      if(expanded) closeCombobox(); else openCombobox();
      // set active
      setActiveOption(current);
    });

    // option clicks
    comboItems.forEach(function(it, i){
      it.addEventListener('click', function(){ selectOption(i); current = i; });
      it.addEventListener('mouseenter', function(){ setActiveOption(i); current = i; });
    });

    // keyboard navigation
    comboToggle.addEventListener('keydown', function(e){
      if(e.key === 'ArrowDown'){ e.preventDefault(); openCombobox(); current = Math.min(comboItems.length-1, current+1); setActiveOption(current); }
      else if(e.key === 'ArrowUp'){ e.preventDefault(); openCombobox(); current = Math.max(0, current-1); setActiveOption(current); }
      else if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); openCombobox(); }
    });

    comboList.addEventListener('keydown', function(e){
      if(e.key === 'ArrowDown'){ e.preventDefault(); current = Math.min(comboItems.length-1, current+1); setActiveOption(current); }
      else if(e.key === 'ArrowUp'){ e.preventDefault(); current = Math.max(0, current-1); setActiveOption(current); }
      else if(e.key === 'Enter'){ e.preventDefault(); selectOption(current); }
      else if(e.key === 'Escape'){ e.preventDefault(); closeCombobox(); comboToggle.focus(); }
    });

    // close on outside click
    document.addEventListener('click', function(e){ if(combobox && !combobox.contains(e.target)) closeCombobox(); });
  }
});
