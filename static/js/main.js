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
    // normalize phone before submit
    function normalizePhoneForSubmit(raw){
      if(!raw) return '';
      var digits = raw.replace(/\D/g,'');
      // if starts with country code (e.g., '55' + rest) and length > 11, keep +
      if(digits.length === 10 || digits.length === 11){
        return '+55' + digits;
      }
      if(digits.length > 11 && digits.indexOf('55') === 0){
        return '+' + digits;
      }
      // fallback: return digits prefixed with + if looks international
      return '+' + digits;
    }

    // normalize name: first letter of each name/surname uppercase, rest lowercase
    function formatName(raw){
      if(!raw) return '';
      // trim and collapse multiple spaces
      var s = String(raw).trim().replace(/\s+/g, ' ');
      if(!s) return '';
      // handle hyphenated parts too (e.g., anna-maria => Anna-Maria)
      var parts = s.split(' ');
      var out = parts.map(function(part){
        return part.split('-').map(function(p){
          if(!p) return p;
          var lower = p.toLowerCase();
          return lower.charAt(0).toUpperCase() + lower.slice(1);
        }).join('-');
      }).join(' ');
      return out;
    }

    bookingForm.addEventListener('submit', function(e){
      bookingStatus.textContent = '';
      var nome = bookingForm.querySelector('#bNome');
      // ensure name is formatted before validation/submission
      if(nome && nome.value) nome.value = formatName(nome.value);
      var tel = bookingForm.querySelector('#bTel');
      if(!nome.value.trim() || !tel.value.trim()){
        e.preventDefault();
        bookingStatus.textContent = 'Por favor, preencha nome e telefone.';
        return;
      }
      // validate and normalize phone input before submit
      var raw = tel.value.trim();
      var digits = raw.replace(/\D/g,'');
      // require 11 digits (DD + 9-digit local) for the (xx) xxxxx-xxxx format
      if(digits.length !== 11){
        e.preventDefault();
        bookingStatus.textContent = 'Telefone inválido. Use o formato (xx) xxxxx-xxxx.';
        return;
      }
      tel.value = normalizePhoneForSubmit(raw);
      // allow form to submit
    });
  }

  // attach formatting on blur to the booking name input (if present)
  (function(){
    var nameEl = document.getElementById('bNome');
    if(!nameEl) return;
    nameEl.addEventListener('blur', function(){
      if(nameEl.value) nameEl.value = formatName(nameEl.value);
    });
  })();

  // Phone input masking for modal (format: (xx) xxxxx-xxxx)
  (function(){
    var telEl = document.getElementById('bTel');
    if(!telEl) return;
    function formatBRPhone(v){
      var digits = v.replace(/\D/g,'').slice(0,11);
      if(digits.length <= 2) return '(' + digits;
      if(digits.length <= 6) return '(' + digits.slice(0,2) + ') ' + digits.slice(2);
      if(digits.length <= 10) return '(' + digits.slice(0,2) + ') ' + digits.slice(2,6) + '-' + digits.slice(6);
      // 11 digits
      return '(' + digits.slice(0,2) + ') ' + digits.slice(2,7) + '-' + digits.slice(7);
    }
    telEl.addEventListener('input', function(e){
      var cur = telEl.value;
      var pos = telEl.selectionStart;
      var before = cur.slice(0,pos);
      telEl.value = formatBRPhone(cur);
      // try to restore caret near end
      telEl.setSelectionRange(telEl.value.length, telEl.value.length);
    });
    telEl.addEventListener('blur', function(e){
      // on blur, ensure fully formatted or clear
      var digits = telEl.value.replace(/\D/g,'');
      if(digits.length === 0){ telEl.value = ''; return; }
      if(digits.length !== 11){
        // leave as-is but user will be prevented on submit
        telEl.classList.add('invalid');
      } else {
        telEl.classList.remove('invalid');
        telEl.value = formatBRPhone(digits);
      }
    });
  })();

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

  /* Time slots combobox: generate 20-minute slots from 08:00 to 18:40 excluding 11:00-12:59 */
  var timeCombobox = document.getElementById('timeCombobox');
  var timeToggle = timeCombobox ? timeCombobox.querySelector('.combobox-toggle') : null;
  var timeList = document.getElementById('timeList');
  var timeItems = timeList ? Array.from(timeList.querySelectorAll('li')) : [];
  var timeInput = document.getElementById('timeInput');
  var dateInput = document.getElementById('dateInput');

  function generateSlotsForDate(dateStr){
    // returns array of 'HH:MM' strings allowed for the given yyyy-mm-dd date
    var parts = dateStr.split('-');
    if(parts.length !== 3) return [];
    var y = parseInt(parts[0],10), m = parseInt(parts[1],10)-1, d = parseInt(parts[2],10);
    var now = new Date();
    var isToday = (now.getFullYear() === y && now.getMonth() === m && now.getDate() === d);
    var dateObj = new Date(y, m, d);
    var isSunday = (dateObj.getDay() === 0);
    var slots = [];
    if(isSunday){
      // Sunday: 09:00 - 11:20 (20-min steps)
      for(var h=9; h<=11; h++){
        for(var mi of [0,20,40]){
          if(h === 11 && mi > 20) continue; // cap at 11:20
          var hh = (h<10? '0'+h: ''+h);
          var mm = (mi<10? '0'+mi: ''+mi);
          var t = hh + ':' + mm;
          if(isToday){
            var slotDate = new Date(y, m, d, h, mi, 0);
            if(slotDate <= now) continue;
          }
          slots.push(t);
        }
      }
    } else {
      // Weekdays: 08:00 - 18:40 excluding lunch 11:00-12:59
      for(var h=8; h<=18; h++){
        for(var mi of [0,20,40]){
          // skip lunch 11:00 - 12:59
          if(h >=11 && h <13) continue;
          // last allowed start is 18:40
          if(h === 18 && mi > 40) continue;
          var hh = (h<10? '0'+h: ''+h);
          var mm = (mi<10? '0'+mi: ''+mi);
          var t = hh + ':' + mm;
          if(isToday){
            var slotDate = new Date(y, m, d, h, mi, 0);
            if(slotDate <= now) continue; // skip past slots
          }
          slots.push(t);
        }
      }
    }
    return slots;
  }

  function populateTimeList(dateStr){
    if(!timeList) return;
    // clear
    timeList.innerHTML = '';
    var slots = generateSlotsForDate(dateStr);
    // helper: normalize time strings to HH:MM
    function normalizeTimeString(s){
      if(!s) return '';
      var m = String(s).match(/(\d{1,2}:\d{2})/);
      if(!m) return '';
      var parts = m[0].split(':');
      var hh = parts[0].padStart(2,'0');
      var mm = parts[1];
      return hh + ':' + mm;
    }

    // fetch occupied slots from server (cache-busted)
    fetch('/ocupados?date='+encodeURIComponent(dateStr)+'&_='+Date.now(), {cache:'no-store'}).then(function(res){
      if(!res.ok) return {occupied:[]};
      return res.json();
    }).then(function(data){
      var occupiedRaw = (data && data.occupied) ? data.occupied : [];
      var occupied = occupiedRaw.map(normalizeTimeString);
      // render all slots, marking occupied ones
      if(slots.length === 0){
        var li = document.createElement('li'); li.textContent = 'Nenhum horário disponível'; li.setAttribute('aria-disabled','true'); li.style.opacity = 0.7; timeList.appendChild(li); timeItems = [li]; return;
      }
      slots.forEach(function(t){
        var li = document.createElement('li');
        li.setAttribute('role','option');
        li.setAttribute('data-value', t);
        li.textContent = t;
        if(occupied.indexOf(normalizeTimeString(t)) !== -1){
          li.classList.add('occupied');
          li.setAttribute('aria-disabled','true');
          li.title = 'Ocupado';
        } else {
          li.addEventListener('click', function(){
            var idx = Array.from(timeList.querySelectorAll('li')).indexOf(li);
            selectTimeOption(idx);
            currentTimeIndex = idx;
          });
          li.addEventListener('mouseenter', function(){ var idx = Array.from(timeList.querySelectorAll('li')).indexOf(li); setActiveTimeOption(idx); currentTimeIndex = idx; });
        }
        timeList.appendChild(li);
      });
          timeItems = Array.from(timeList.querySelectorAll('li'));
          // after building items, refresh selection and keyboard state
          try{ if(typeof updateTimeItemsState === 'function') updateTimeItemsState(); }catch(e){ /* ignore */ }
    }).catch(function(){
      // on error, render local slots as enabled
      if(slots.length === 0){
        var li = document.createElement('li'); li.textContent = 'Nenhum horário disponível'; li.setAttribute('aria-disabled','true'); li.style.opacity = 0.7; timeList.appendChild(li); timeItems = [li]; return;
      }
      slots.forEach(function(t){
        var li = document.createElement('li');
        li.setAttribute('role','option');
        li.setAttribute('data-value', t);
        li.textContent = t;
        li.addEventListener('click', function(){ var idx = Array.from(timeList.querySelectorAll('li')).indexOf(li); selectTimeOption(idx); currentTimeIndex = idx; });
        li.addEventListener('mouseenter', function(){ var idx = Array.from(timeList.querySelectorAll('li')).indexOf(li); setActiveTimeOption(idx); currentTimeIndex = idx; });
        timeList.appendChild(li);
      });
      timeItems = Array.from(timeList.querySelectorAll('li'));
          // after building items, refresh selection and keyboard state
          try{ if(typeof updateTimeItemsState === 'function') updateTimeItemsState(); }catch(e){ /* ignore */ }
    });
  }

  // Update timeItems state after populate: mark occupied items as non-focusable
  function updateTimeItemsState(){
    timeItems = timeList ? Array.from(timeList.querySelectorAll('li')) : [];
    // mark occupied items non-focusable
    timeItems.forEach(function(li){
      var isOcc = li.classList.contains('occupied') || li.getAttribute('aria-disabled') === 'true';
      if(isOcc){
        li.setAttribute('aria-disabled','true');
        try{ li.tabIndex = -1; }catch(e){}
      } else {
        li.removeAttribute('aria-disabled');
        try{ li.tabIndex = 0; }catch(e){}
      }
    });

    // preserve already-selected time if still available
    var chosen = (timeInput && timeInput.value) ? timeInput.value : null;
    if(chosen){
      var idx = timeItems.findIndex(function(it){ return it.getAttribute('data-value') === chosen; });
      if(idx !== -1){
        var it = timeItems[idx];
        if(!(it.classList.contains('occupied') || it.getAttribute('aria-disabled') === 'true')){
          // still available
          if(timeToggle){ var lbl = timeToggle.querySelector('#comboboxTimeLabel'); if(lbl) lbl.textContent = chosen; }
          currentTimeIndex = idx;
          return;
        } else {
          // chosen became occupied -> clear selection
          if(timeInput) timeInput.value = '';
          if(timeToggle){ var lbl = timeToggle.querySelector('#comboboxTimeLabel'); if(lbl) lbl.textContent = 'Selecione um horário'; }
        }
      }
    }

    // select first available
    var firstAvail = -1;
    for(var i=0;i<timeItems.length;i++){
      if(!(timeItems[i].classList.contains('occupied') || timeItems[i].getAttribute('aria-disabled') === 'true')){ firstAvail = i; break; }
    }
    if(firstAvail !== -1){ selectTimeOption(firstAvail); currentTimeIndex = firstAvail; }
    else {
      // no available slots
      if(timeToggle){ var lbl = timeToggle.querySelector('#comboboxTimeLabel'); if(lbl) lbl.textContent = 'Nenhum horário disponível'; }
      if(timeInput) timeInput.value = '';
      currentTimeIndex = 0;
    }
  }

  function setActiveTimeOption(index){
    timeItems.forEach(function(it, i){
      var sel = (i === index);
      it.setAttribute('aria-selected', sel ? 'true' : 'false');
      if(sel) it.scrollIntoView({block:'nearest'});
    });
  }

  function selectTimeOption(index){
    var it = timeItems[index];
    if(!it) return;
    var value = it.getAttribute('data-value');
    if(timeInput) timeInput.value = value;
    if(timeToggle){
      var lbl = timeToggle.querySelector('#comboboxTimeLabel'); if(lbl) lbl.textContent = value;
    }
    closeTimeCombobox();
  }

  function openTimeCombobox(){ if(!timeCombobox) return; timeCombobox.classList.add('open'); timeCombobox.setAttribute('aria-expanded','true'); if(timeToggle) timeToggle.setAttribute('aria-expanded','true'); timeList.style.display='block'; }
  function closeTimeCombobox(){ if(!timeCombobox) return; timeCombobox.classList.remove('open'); timeCombobox.setAttribute('aria-expanded','false'); if(timeToggle) timeToggle.setAttribute('aria-expanded','false'); if(timeList) timeList.style.display='none'; }

  var currentTimeIndex = 0;
  if(dateInput){
    // set min to today in case template didn't
    var today = new Date().toISOString().slice(0,10);
    if(!dateInput.getAttribute('min')) dateInput.setAttribute('min', today);
    // initial populate
    populateTimeList(dateInput.value || today);
    dateInput.addEventListener('change', function(){
      populateTimeList(dateInput.value);
      // reset hidden value and label
      if(timeInput) timeInput.value = '';
      if(timeToggle){ var lbl = timeToggle.querySelector('#comboboxTimeLabel'); if(lbl) lbl.textContent = 'Selecione um horário'; }
    });
  }

  // Pre-submit check: verify chosen time is still available by querying /ocupados
  var agendamentoForm = document.querySelector('form.service-select-row');
  if(agendamentoForm){
    agendamentoForm.addEventListener('submit', function(e){
      var dateVal = (dateInput && dateInput.value) ? dateInput.value : '';
      var timeVal = (timeInput && timeInput.value) ? timeInput.value : '';
      if(!dateVal || !timeVal){
        e.preventDefault();
        alert('Por favor escolha uma data e horário disponíveis antes de confirmar.');
        return;
      }
      // prevent immediate submit and re-check availability
      e.preventDefault();
      // normalize helper (same as in populateTimeList)
      function normalizeTimeString(s){ if(!s) return ''; var m = String(s).match(/(\d{1,2}:\d{2})/); if(!m) return ''; var parts = m[0].split(':'); return parts[0].padStart(2,'0')+':'+parts[1]; }
      var timeValNorm = normalizeTimeString(timeVal);
      fetch('/ocupados?date='+encodeURIComponent(dateVal)+'&_='+Date.now(), {cache:'no-store'}).then(function(res){
        if(!res.ok) return {occupied:[]};
        return res.json();
      }).then(function(data){
        var occupiedRaw = (data && data.occupied) ? data.occupied : [];
        var occupied = occupiedRaw.map(normalizeTimeString);
        if(occupied.indexOf(timeValNorm) !== -1){
          alert('Desculpe — este horário já foi reservado. Escolha outro.');
          // refresh the time list to reflect current occupied slots
          populateTimeList(dateVal);
          return;
        }
        // still available -> submit the form normally
        agendamentoForm.submit();
      }).catch(function(){
        // on error consult server-side, allow submit (server enforces uniqueness)
        agendamentoForm.submit();
      });
    });
  }

  if(timeToggle && timeList){
    // ensure timeItems is current
    timeItems = timeList ? Array.from(timeList.querySelectorAll('li')) : [];
    // helper to detect occupied
    function isTimeItemOccupied(li){ return li.classList.contains('occupied') || li.getAttribute('aria-disabled') === 'true'; }
    function findNextAvailableIndex(start, dir){ var i = start; while(i >= 0 && i < timeItems.length){ if(!isTimeItemOccupied(timeItems[i])) return i; i += dir; } return -1; }

    if(timeItems.length > 0){
      var firstAvail = findNextAvailableIndex(0, 1);
      if(firstAvail === -1){ currentTimeIndex = 0; }
      else { selectTimeOption(firstAvail); currentTimeIndex = firstAvail; }
    }

    timeToggle.addEventListener('click', function(e){ var expanded = timeCombobox.classList.contains('open'); if(expanded) closeTimeCombobox(); else openTimeCombobox(); setActiveTimeOption(currentTimeIndex); });

    timeToggle.addEventListener('keydown', function(e){
      if(e.key === 'ArrowDown'){
        e.preventDefault(); openTimeCombobox(); var next = findNextAvailableIndex(currentTimeIndex+1, 1); if(next !== -1) currentTimeIndex = next; setActiveTimeOption(currentTimeIndex);
      }
      else if(e.key === 'ArrowUp'){
        e.preventDefault(); openTimeCombobox(); var prev = findNextAvailableIndex(currentTimeIndex-1, -1); if(prev !== -1) currentTimeIndex = prev; setActiveTimeOption(currentTimeIndex);
      }
      else if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); openTimeCombobox(); }
    });

    timeList.addEventListener('keydown', function(e){
      if(e.key === 'ArrowDown'){
        e.preventDefault(); var next = findNextAvailableIndex(currentTimeIndex+1, 1); if(next !== -1) currentTimeIndex = next; setActiveTimeOption(currentTimeIndex);
      }
      else if(e.key === 'ArrowUp'){
        e.preventDefault(); var prev = findNextAvailableIndex(currentTimeIndex-1, -1); if(prev !== -1) currentTimeIndex = prev; setActiveTimeOption(currentTimeIndex);
      }
      else if(e.key === 'Enter'){
        e.preventDefault(); if(!isTimeItemOccupied(timeItems[currentTimeIndex])) selectTimeOption(currentTimeIndex);
      }
      else if(e.key === 'Escape'){ e.preventDefault(); closeTimeCombobox(); timeToggle.focus(); }
    });

    document.addEventListener('click', function(e){ if(timeCombobox && !timeCombobox.contains(e.target)) closeTimeCombobox(); });
  }
});
