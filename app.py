from flask import Flask, render_template, request, redirect, session, flash, jsonify
import mysql.connector
import uuid
from datetime import datetime, date
from conexao import Conexao

# Serviços disponíveis (chave -> rótulo, preço e imagem)
SERVICES = {
    'corte_social_barba': {'label': 'Corte social com barba', 'price': 50, 'image': 'images/corte_social_barba.svg'},
    'corte_degrade_barba': {'label': 'Corte degradê com barba', 'price': 52, 'image': 'images/corte_degrade_barba.svg'},
    'corte_degrade': {'label': 'Corte degradê', 'price': 32, 'image': 'images/corte_degrade.svg'},
    'corte_social': {'label': 'Corte social', 'price': 27, 'image': 'images/corte_social.svg'},
    'corte_maquina': {'label': 'Corte máquina', 'price': 22, 'image': 'images/corte_maquina.svg'},
    'corte_navalhado': {'label': 'Corte navalhado', 'price': 32, 'image': 'images/corte_navalhado.svg'},
    'barba': {'label': 'Barba', 'price': 27, 'image': 'images/barba.svg'},
    'pezinho': {'label': 'Pezinho do cabelo', 'price': 17, 'image': 'images/pezinho.svg'},
    'sobrancelha': {'label': 'Sobrancelha', 'price': 10, 'image': 'images/sobrancelha.svg'},
    'corte_tesoura': {'label': 'Corte só Tesoura', 'price': 32, 'image': 'images/corte_tesoura.svg'},
}

app = Flask(__name__)
app.secret_key = '0000'  # Chave secreta para gerenciamento de sessões


def generate_allowed_slots_for_date_obj(d):
    """Return list of allowed 'HH:MM' slots for a date object d.
    Rules: Sunday 09:00-11:20 (20m). Other days 08:00-18:40 excluding 11:00-12:59.
    If d is today, caller should filter past slots using current time if desired.
    """
    slots = []
    is_sunday = (d.weekday() == 6)
    if is_sunday:
        for h in range(9, 12):
            for m in (0, 20, 40):
                if h == 11 and m > 20:
                    continue
                slots.append(f"{h:02d}:{m:02d}")
    else:
        for h in range(8, 19):
            for m in (0, 20, 40):
                if h >= 11 and h < 13:
                    continue
                if h == 18 and m > 40:
                    continue
                slots.append(f"{h:02d}:{m:02d}")
    return slots


def normalize_phone(raw):
    """Normalize phone numbers to a canonical form for storage and comparison.
    Rules (simple): strip non-digits. If 10 or 11 digits, prefix with +55.
    If already includes country (more than 11 and starts with 55), prefix with +.
    Returns normalized string starting with '+' and digits, or original trimmed if empty.
    """
    if not raw:
        return ''
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not digits:
        return ''
    if len(digits) in (10, 11):
        return '+55' + digits
    if len(digits) > 11 and digits.startswith('55'):
        return '+' + digits
    return '+' + digits

@app.route("/")
def inicio():
    # Garante CSRF token na sessão e passa para o template
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    usuario = session.get('usuario')
    return render_template("index.html", csrf_token=session.get('csrf_token'), usuario=usuario)


@app.route('/ocupados')
def ocupados():
    # retorna JSON com lista de horários ocupados para uma data YYYY-MM-DD
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'missing date'}), 400
    occupied = []
    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        cur.execute("SELECT time FROM agendamentos WHERE date = %s", (date_str,))
        rows = cur.fetchall()
        for r in rows:
            # r may be tuple
            t = r[0] if isinstance(r, (list, tuple)) else r
            # time might come as datetime.time; convert to HH:MM
            try:
                s = t.strftime('%H:%M')
            except Exception:
                s = str(t)
            # normalize to 'HH:MM'
            occupied.append(s[:5])
        cur.close(); conn.close()
    except Exception:
        # on DB error, return empty array (frontend will still show available slots)
        occupied = []
    return jsonify({'occupied': occupied})

@app.route("/cadastro", methods=["POST"])
def cadastro():
    nome = request.form.get("nome")
    raw_num = request.form.get("numero")
    numero = normalize_phone(raw_num)
    # Salva dados na sessão (telefone normalizado) e redireciona para a página de agendamento
    session['usuario'] = { 'nome': nome, 'numero': numero }
    # Se já existir agendamento para esse número no banco ou na sessão, redirecionar ao usuário
    # checar sessão primeiro
    bookings = session.get('bookings', [])
    for b in bookings:
        u = b.get('usuario') if isinstance(b, dict) else None
        if u and normalize_phone(u.get('numero')) == numero:
            return redirect('/meus_agendamentos')


        @app.route('/ocupados')
        def ocupados():
            # retorna JSON com lista de horários ocupados para uma data YYYY-MM-DD
            date_str = request.args.get('date')
            if not date_str:
                return jsonify({'error': 'missing date'}), 400
            occupied = []
            try:
                conn = Conexao.conectar()
                cur = conn.cursor()
                cur.execute("SELECT time FROM agendamentos WHERE date = %s", (date_str,))
                rows = cur.fetchall()
                for r in rows:
                    # r may be tuple
                    t = r[0] if isinstance(r, (list, tuple)) else r
                    # time might come as datetime.time; convert to HH:MM
                    try:
                        s = t.strftime('%H:%M')
                    except Exception:
                        s = str(t)
                    # normalize to 'HH:MM'
                    occupied.append(s[:5])
                cur.close(); conn.close()
            except Exception:
                # on DB error, return empty array (frontend will still show available slots)
                occupied = []
            return jsonify({'occupied': occupied})

    # checar no banco
    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        cur.execute("SELECT id FROM agendamentos WHERE client_phone = %s LIMIT 1", (numero,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return redirect('/meus_agendamentos')
    except Exception:
        # se o banco não estiver disponível, apenas seguir para agendamento
        pass
    return redirect('/agendamento')


@app.route('/agendamento')
def agendamento():
    usuario = session.get('usuario')
    if not usuario:
        # Se não há usuário cadastrado, volta para a página inicial
        return redirect('/')
    # Garantir CSRF token presente e passá-lo para o template
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    # passar a data mínima (hoje) para o template
    today = date.today().isoformat()
    return render_template('agendamento.html', usuario=usuario, csrf_token=session.get('csrf_token'), services=SERVICES, today=today)


@app.route('/confirmar', methods=['POST'])
def confirmar():
    # Confirma agendamento: valida CSRF e grava o agendamento na sessão
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/agendamento')
    usuario = session.get('usuario')
    if not usuario:
        flash('Usuário não autenticado.')
        return redirect('/')
    service_key = request.form.get('service')
    svc = SERVICES.get(service_key)
    if not svc:
        flash('Serviço inválido.')
        return redirect('/agendamento')

    # validar data e horário
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    if not date_str or not time_str:
        flash('Por favor escolha data e horário.')
        return redirect('/agendamento')

    # parse date
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        flash('Data inválida.')
        return redirect('/agendamento')

    # não permitir datas no passado
    if selected_date < date.today():
        flash('Não é possível agendar em uma data passada.')
        return redirect('/agendamento')

    # gerar slots permitidos para a data e validar o horário
    allowed = generate_allowed_slots_for_date_obj(selected_date)
    # se for hoje, filtrar horários já passados
    if selected_date == date.today():
        now = datetime.now()
        allowed = [t for t in allowed if datetime(now.year, now.month, now.day, int(t.split(':')[0]), int(t.split(':')[1])) > now]
    if time_str not in allowed:
        flash('Horário indisponível. Escolha outro horário.')
        return redirect('/agendamento')
    booking = {
        'usuario': usuario,
        'service_key': service_key,
        'service_label': svc['label'],
        'price': svc['price'],
        'date': date_str,
        'time': time_str,
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }

    # Tentar persistir no banco MySQL (conceito). Se falhar, cai para armazenamento em sessão.
    try:
        conn = None
        cur = None
        conn = Conexao.conectar()
        cur = conn.cursor()
        # iniciar transação explicitamente
        try:
            conn.start_transaction()
        except Exception:
            pass

        # checar limite de agendamentos por cliente (DB + sessão)
        # contar agendamentos no DB
        cur.execute("SELECT COUNT(*) FROM agendamentos WHERE client_phone = %s", (usuario.get('numero'),))
        row_count = cur.fetchone()
        db_count = int(row_count[0]) if row_count else 0
        # contar agendamentos em sessão para esse telefone (comparar telefones normalizados)
        sess_count = 0
        for b in session.get('bookings', []):
            p = None
            if isinstance(b, dict):
                u = b.get('usuario')
                if u and isinstance(u, dict):
                    p = u.get('numero')
                else:
                    p = b.get('client_phone')
            if normalize_phone(p) == usuario.get('numero'):
                sess_count += 1
        if (db_count + sess_count) >= 2:
            cur.close(); conn.close()
            flash('Limite de 2 agendamentos por cliente atingido.')
            return redirect('/agendamento')

        # checar disponibilidade com lock
        cur.execute("SELECT COUNT(*) FROM agendamentos WHERE date = %s AND time = %s FOR UPDATE", (date_str, time_str))
        row = cur.fetchone()
        count = row[0] if row else 0
        if count and int(count) > 0:
            conn.rollback()
            cur.close()
            conn.close()
            flash('Desculpe — este horário já foi reservado. Escolha outro.')
            return redirect('/agendamento')

        # inserir
        cur.execute(
            "INSERT INTO agendamentos (date, time, client_name, client_phone, service_key) VALUES (%s,%s,%s,%s,%s)",
            (date_str, time_str, usuario.get('nome'), usuario.get('numero'), service_key)
        )
        booking_id = cur.lastrowid if hasattr(cur, 'lastrowid') else None
        conn.commit()
        cur.close()
        conn.close()

        # adicionar id no registro local para referência
        if booking_id:
            booking['id'] = booking_id
        # store last booking id in session so /confirmacao can show it
        if booking_id:
            session['last_booking_id'] = booking_id

        flash('Agendamento confirmado e salvo no banco!')
        return redirect('/confirmacao')
    except Exception as e:
        # fechar conexões abertas quando possível
        try:
            cur and cur.close()
            conn and conn.close()
        except Exception:
            pass
        # Se o erro for violação de unique (duplicate entry), considerar o slot ocupado
        is_duplicate = False
        try:
            if isinstance(e, mysql.connector.errors.IntegrityError):
                # duplicate key or other integrity problems
                # MySQL duplicate entry errno is 1062
                if hasattr(e, 'errno') and e.errno == 1062:
                    is_duplicate = True
        except Exception:
            # fallback to string check
            if 'Duplicate' in str(e) or '1062' in str(e):
                is_duplicate = True

        if is_duplicate:
            flash('Desculpe — este horário já foi reservado. Escolha outro.')
            return redirect('/agendamento')
        # Para outros erros (conexão ou inesperados), não salvar localmente — DB é a fonte de verdade.
        # Informe o usuário e peça para tentar novamente.
        flash('Erro ao salvar o agendamento no banco. Tente novamente em instantes.')
        return redirect('/agendamento')


@app.route('/confirmacao')
def confirmacao():
    # Try to show the last booking saved in DB (session stores last_booking_id)
    last_id = session.get('last_booking_id')
    booking = None
    if last_id:
        try:
            conn = Conexao.conectar()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, date, time, client_name, client_phone, service_key FROM agendamentos WHERE id = %s", (last_id,))
            r = cur.fetchone()
            cur.close(); conn.close()
            if r:
                svc = SERVICES.get(r.get('service_key')) or {}
                booking = {
                    'id': r.get('id'),
                    'date': r.get('date'),
                    'time': r.get('time'),
                    'service_label': svc.get('label', r.get('service_key')),
                    'price': svc.get('price'),
                    'usuario': {'nome': r.get('client_name'), 'numero': r.get('client_phone')}
                }
        except Exception:
            booking = None

    # fallback: if no booking found, try last session booking (rare)
    if not booking:
        bookings = session.get('bookings', [])
        if bookings:
            booking = bookings[-1]

    if not booking:
        flash('Nenhum agendamento encontrado.')
        return redirect('/')

    return render_template('confirmacao.html', booking=booking, usuario=session.get('usuario'), csrf_token=session.get('csrf_token'))


@app.route('/meus_agendamentos')
def meus_agendamentos():
    usuario = session.get('usuario')
    if not usuario:
        flash('Faça o cadastro para ver seus agendamentos.')
        return redirect('/')
    all_bookings = []
    # buscar no banco os agendamentos deste telefone
    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, date, time, service_key, created_at FROM agendamentos WHERE client_phone = %s ORDER BY date, time", (usuario.get('numero'),))
        rows = cur.fetchall()
        for r in rows:
            svc = SERVICES.get(r['service_key'], {})
            all_bookings.append({
                'id': r['id'], 'date': r['date'], 'time': r['time'], 'service_label': svc.get('label', r['service_key']), 'usuario': usuario, 'client_phone': usuario.get('numero')
            })
        cur.close()
        conn.close()
    except Exception:
        # DB falhou; seguir apenas com sessão
        pass

    # também incluir agendamentos em sessão (sem id)
    sess = session.get('bookings', [])
    for b in sess:
        if isinstance(b, dict):
            u = b.get('usuario')
            phone = None
            if u and isinstance(u, dict):
                phone = u.get('numero')
            else:
                phone = b.get('client_phone')
            if normalize_phone(phone) == usuario.get('numero'):
                # avoid duplicates: skip session booking if a DB booking with same date/time exists
                exists = False
                for dbb in all_bookings:
                    try:
                        if dbb.get('date') == b.get('date') and dbb.get('time') == b.get('time'):
                            exists = True
                            break
                    except Exception:
                        continue
                if not exists:
                    all_bookings.append({
                        'date': b.get('date'), 'time': b.get('time'), 'service_label': b.get('service_label'), 'usuario': b.get('usuario'), 'client_phone': phone
                    })

    return render_template('meus_agendamentos.html', bookings=all_bookings, csrf_token=session.get('csrf_token'), usuario=usuario)


@app.route('/cancelar', methods=['POST'])
def cancelar():
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/meus_agendamentos')
    usuario = session.get('usuario')
    if not usuario:
        flash('Usuário não autenticado.')
        return redirect('/')
    btype = request.form.get('booking_type')
    if btype == 'db':
        bid = request.form.get('booking_id')
        try:
            conn = Conexao.conectar()
            cur = conn.cursor()
            cur.execute("DELETE FROM agendamentos WHERE id = %s AND client_phone = %s", (bid, usuario.get('numero')))
            conn.commit()
            cur.close()
            conn.close()
            # also remove from session if present
            newb = []
            for b in session.get('bookings', []):
                if b.get('id') and str(b.get('id')) == str(bid):
                    continue
                newb.append(b)
            session['bookings'] = newb
            flash('Agendamento cancelado.')
        except Exception:
            flash('Erro ao cancelar (banco indisponível).')
        return redirect('/meus_agendamentos')
    else:
        # session cancellation
        idx = request.form.get('session_idx')
        try:
            idx = int(idx)
            b_list = session.get('bookings', [])
            if 0 <= idx < len(b_list):
                b_list.pop(idx)
                session['bookings'] = b_list
                flash('Agendamento cancelado (sessão).')
        except Exception:
            flash('Falha ao cancelar.')
        return redirect('/meus_agendamentos')


# Note: the /alterar route and template were removed — editing of bookings is now handled via /meus_agendamentos
@app.route('/alterar', methods=['GET','POST'])
def alterar():
    usuario = session.get('usuario')
    if not usuario:
        flash('Faça login para alterar seu agendamento.')
        return redirect('/')

    if request.method == 'GET':
        btype = request.args.get('type')
        if btype == 'db':
            bid = request.args.get('id')
            try:
                conn = Conexao.conectar()
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT id, date, time, service_key FROM agendamentos WHERE id = %s AND client_phone = %s", (bid, usuario.get('numero')))
                r = cur.fetchone()
                cur.close(); conn.close()
                if not r:
                    flash('Agendamento não encontrado.')
                    return redirect('/meus_agendamentos')
                svc = SERVICES.get(r['service_key'], {})
                booking = {'id': r['id'], 'date': r['date'], 'time': r['time'], 'service_label': svc.get('label', r['service_key'])}
                return render_template('alterar.html', booking=booking, booking_type='db', booking_id=bid, csrf_token=session.get('csrf_token'), usuario=usuario)
            except Exception:
                flash('Erro ao acessar o banco.')
                return redirect('/meus_agendamentos')
        else:
            # session-based booking: just redirect to meus_agendamentos (no change inline)
            return redirect('/meus_agendamentos')

    # POST -> apply change
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/meus_agendamentos')

    btype = request.form.get('booking_type')
    new_date = request.form.get('date')
    new_time = request.form.get('time')
    # validate
    try:
        selected_date = datetime.strptime(new_date, '%Y-%m-%d').date()
    except Exception:
        flash('Data inválida.')
        return redirect('/meus_agendamentos')
    allowed = generate_allowed_slots_for_date_obj(selected_date)
    if selected_date == date.today():
        now = datetime.now()
        allowed = [t for t in allowed if datetime(now.year, now.month, now.day, int(t.split(':')[0]), int(t.split(':')[1])) > now]
    if new_time not in allowed:
        flash('Horário inválido para essa data.')
        return redirect('/meus_agendamentos')

    if btype == 'db':
        bid = request.form.get('booking_id')
        try:
            conn = Conexao.conectar()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM agendamentos WHERE date = %s AND time = %s AND id != %s FOR UPDATE", (new_date, new_time, bid))
            row = cur.fetchone()
            cnt = row[0] if row else 0
            if cnt and int(cnt) > 0:
                conn.rollback(); cur.close(); conn.close()
                flash('Horário já reservado.')
                return redirect('/meus_agendamentos')
            cur.execute("UPDATE agendamentos SET date=%s, time=%s WHERE id = %s AND client_phone = %s", (new_date, new_time, bid, usuario.get('numero')))
            conn.commit(); cur.close(); conn.close()
            flash('Horário alterado com sucesso.')
        except Exception:
            flash('Erro ao alterar horário (banco).')
        return redirect('/meus_agendamentos')
    else:
        return redirect('/meus_agendamentos')


@app.route('/logout', methods=['POST'])
def logout():
    # Valida token CSRF e remove o usuário da sessão
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/')
    session.pop('usuario', None)
    # Opcional: renovar o csrf_token
    session['csrf_token'] = str(uuid.uuid4())
    flash('Você saiu com sucesso.')
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)