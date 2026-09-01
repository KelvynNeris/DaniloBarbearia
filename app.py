import os
import uuid
from datetime import datetime, date, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from conexao import Conexao

load_dotenv()

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
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-dev")
app.secret_key = app.config["SECRET_KEY"]


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


def normalize_name(raw):
    """Normalize a person's name so each word (and hyphenated subword) starts with an uppercase
    letter and the rest are lowercase. Example: 'joão da silva' -> 'João Da Silva'.

    This intentionally preserves the established project convention for apostrophes and repeated
    separators: the first letter of each word is uppercased, while the remainder is lowercased.
    """
    if raw is None:
        return ''

    s = str(raw).strip()
    if not s:
        return ''

    normalized_parts = []
    for part in s.split():
        normalized_subparts = []
        for subpart in part.split('-'):
            if not subpart:
                continue
            normalized_subparts.append(subpart[:1].upper() + subpart[1:].lower())
        normalized_parts.append('-'.join(normalized_subparts))

    return ' '.join(normalized_parts)

@app.route("/")
def inicio():
    # Garante CSRF token na sessão e passa para o template
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    usuario = session.get('usuario')
    return render_template("index.html", csrf_token=session.get('csrf_token'), usuario=usuario)


@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    # Ensure CSRF
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())

    if request.method == 'GET':
        return render_template('admin_login.html', csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))

    # POST: process login
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/login')

    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    phone_raw = request.form.get('phone') or ''
    if not username or not password or not phone_raw.strip():
        flash('Preencha usuário, telefone e senha.')
        return redirect('/admin/login')
    phone = normalize_phone(phone_raw)

    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        # include first_login flag in query
        cur.execute('SELECT id, username, name, phone, password_hash, IFNULL(first_login,0) AS first_login FROM admins WHERE username = %s LIMIT 1', (username,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            flash('Usuário/senha inválidos.')
            return redirect('/admin/login')
        if not check_password_hash(row.get('password_hash',''), password):
            flash('Usuário/senha inválidos.')
            return redirect('/admin/login')
        # validate phone matches stored admin phone
        stored_phone = row.get('phone') or ''
        # normalize stored phone before comparing so formats like '+55 (11) 91234-5678' match
        try:
            stored_phone_norm = normalize_phone(stored_phone) if (stored_phone and str(stored_phone).strip()) else ''
        except Exception:
            stored_phone_norm = stored_phone
        if phone != stored_phone_norm:
            flash('Telefone inválido para este usuário.')
            return redirect('/admin/login')

        # login successful: store admin id in session
        session['admin_id'] = row.get('id')
        session['admin_username'] = row.get('username')

        # If admin hasn't completed first-login actions, redirect to change page
        try:
            if int(row.get('first_login') or 0) == 0:
                flash('Primeiro login detectado — por favor atualize seus dados.')
                return redirect('/admin/change')
        except Exception:
            pass

        flash('Login de administrador bem-sucedido.')
        return redirect('/admin/agendas')
    except Exception:
        flash('Erro ao verificar credenciais (banco).')
        return redirect('/admin/login')


@app.route('/admin/change', methods=['GET','POST'])
def admin_change():
    # allow logged-in admin to change name, phone and password
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    # fetch admin first_login flag to determine access
    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT id, username, name, phone, IFNULL(first_login,0) AS first_login FROM admins WHERE id = %s', (admin_id,))
        admin_row = cur.fetchone()
        cur.close(); conn.close()
    except Exception:
        flash('Erro ao acessar o banco.')
        return redirect('/')

    if not admin_row:
        flash('Administrador não encontrado.')
        return redirect('/admin/login')

    # if first_login == 1, make this page inaccessible
    try:
        if int(admin_row.get('first_login') or 0) == 1:
            flash('A página de alteração não está disponível após o primeiro login.')
            return redirect('/admin/agendas')
    except Exception:
        pass

    if request.method == 'GET':
        return render_template('admin_change.html', admin=admin_row, csrf_token=session.get('csrf_token'))

    # POST: apply changes
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/change')

    name_raw = request.form.get('name') or ''
    phone_raw = request.form.get('phone') or ''
    password = request.form.get('password') or ''
    password2 = request.form.get('password2') or ''

    if not password:
        flash('Senha obrigatória.')
        return redirect('/admin/change')
    if password != password2:
        flash('As senhas não coincidem.')
        return redirect('/admin/change')

    name = normalize_name(name_raw) if name_raw.strip() else None
    phone = normalize_phone(phone_raw) if phone_raw.strip() else None

    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        # mark first_login = 1 after admin updates their info
        if password:
            pwd_hash = generate_password_hash(password)
            cur.execute('UPDATE admins SET name=%s, phone=%s, password_hash=%s, first_login=1 WHERE id = %s', (name, phone, pwd_hash, admin_id))
        else:
            cur.execute('UPDATE admins SET name=%s, phone=%s, first_login=1 WHERE id = %s', (name, phone, admin_id))
        conn.commit(); cur.close(); conn.close()
        flash('Dados do administrador atualizados.')
        return redirect('/admin/agendas')
    except Exception:
        flash('Erro ao atualizar admin (banco).')
        return redirect('/admin/change')


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
    nome_raw = request.form.get("nome")
    nome = normalize_name(nome_raw)
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
        'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
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


@app.route('/admin/agendas')
def admin_agendas():
    # página para administrador ver todas as agendas detalhadamente
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    agendas = []
    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, date, time, client_name, client_phone, service_key, created_at FROM agendamentos ORDER BY date DESC, time DESC")
        rows = cur.fetchall()
        for r in rows:
            svc = SERVICES.get(r.get('service_key'), {})
            agendas.append({
                'id': r.get('id'),
                'date': r.get('date'),
                'time': r.get('time'),
                'service_label': svc.get('label', r.get('service_key')),
                'price': svc.get('price'),
                'client_name': r.get('client_name'),
                'client_phone': r.get('client_phone'),
                'created_at': r.get('created_at')
            })
        cur.close(); conn.close()
    except Exception:
        flash('Erro ao acessar agendamentos (banco).')

    return render_template('admin_agendas.html', agendas=agendas, csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))


@app.route('/admin/relatorio')
def admin_relatorio():
    # relatório administrativo: serviço mais agendado, receita por período e por dia
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    # período (desde start até end). Parâmetros: ?start=YYYY-MM-DD&end=YYYY-MM-DD
    try:
        end_date = request.args.get('end') or date.today().isoformat()
        start_date = request.args.get('start') or (date.today() - timedelta(days=30)).isoformat()
    except Exception:
        start_date = (date.today() - timedelta(days=30)).isoformat()
        end_date = date.today().isoformat()

    most_booked = None
    per_day = {}
    total_revenue = 0
    bookings_count = 0
    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        # counts per service in period
        cur.execute("SELECT service_key, COUNT(*) AS cnt FROM agendamentos WHERE date BETWEEN %s AND %s GROUP BY service_key", (start_date, end_date))
        rows = cur.fetchall()
        svc_counts = {}
        for r in rows:
            key = r[0]
            cnt = int(r[1])
            svc_counts[key] = cnt

        if svc_counts:
            best = max(svc_counts.items(), key=lambda x: x[1])
            most_booked = {'service_key': best[0], 'label': SERVICES.get(best[0], {}).get('label', best[0]), 'count': best[1]}

        # revenue per day (group by date and service_key, then multiply by price)
        cur.execute("SELECT date, service_key, COUNT(*) FROM agendamentos WHERE date BETWEEN %s AND %s GROUP BY date, service_key ORDER BY date ASC", (start_date, end_date))
        rows = cur.fetchall()
        for r in rows:
            d = r[0]
            key = r[1]
            cnt = int(r[2])
            price = SERVICES.get(key, {}).get('price', 0)
            rev = cnt * price
            per_day.setdefault(str(d), {'revenue': 0, 'bookings': 0})
            per_day[str(d)]['revenue'] += rev
            per_day[str(d)]['bookings'] += cnt
            total_revenue += rev
            bookings_count += cnt

        cur.close(); conn.close()
    except Exception:
        flash('Erro ao gerar relatório (banco).')

    # convert per_day to sorted list
    per_day_list = sorted([{'date': k, 'revenue': v['revenue'], 'bookings': v['bookings']} for k, v in per_day.items()], key=lambda x: x['date'])
    max_bookings = max((item['bookings'] for item in per_day_list), default=0)
    max_revenue = max((item['revenue'] for item in per_day_list), default=0)

    # determine the single day with most bookings (date string 'YYYY-MM-DD')
    most_day = None
    try:
        if per_day_list:
            best = max(per_day_list, key=lambda x: int(x.get('bookings', 0)))
            try:
                dt = datetime.strptime(best['date'], '%Y-%m-%d').date()
                weekdays_pt = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
                months_pt = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
                # datetime.weekday(): Monday=0
                weekday_name = weekdays_pt[dt.weekday()]
                month_name = months_pt[dt.month - 1]
                most_day = {
                    'date': best['date'],
                    'day_num': dt.day,
                    'month': month_name,
                    'month_num': dt.month,
                    'weekday': weekday_name,
                    'bookings': int(best.get('bookings', 0)),
                    'revenue': best.get('revenue', 0)
                }
            except Exception:
                most_day = {'date': best.get('date'), 'bookings': int(best.get('bookings', 0)), 'revenue': best.get('revenue', 0)}
    except Exception:
        most_day = None

    return render_template('admin_relatorio.html', most=most_booked, per_day=per_day_list, max_bookings=max_bookings, max_revenue=max_revenue, most_day=most_day, total_revenue=total_revenue, bookings_count=bookings_count, start=start_date, end=end_date, csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))

if __name__ == "__main__":
    # Ensure a default predefined admin exists (username 'adm', name 'adm', phone '+55 (99) 99999-9999', password '123')
    def ensure_default_admin():
        default_username = 'adm'
        default_name = 'adm'
        default_phone_raw = '+55 (99) 99999-9999'
        default_password = '123'
        try:
            conn = Conexao.conectar()
            cur = conn.cursor()
            # ensure first_login column exists (MySQL 8+ supports IF NOT EXISTS)
            try:
                cur.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS first_login TINYINT(1) DEFAULT 0")
            except Exception:
                # fallback: attempt to add column without IF NOT EXISTS (ignore errors)
                try:
                    cur.execute("ALTER TABLE admins ADD COLUMN first_login TINYINT(1) DEFAULT 0")
                except Exception:
                    pass

            cur.execute('SELECT id FROM admins WHERE username = %s LIMIT 1', (default_username,))
            row = cur.fetchone()
            if not row:
                pwd_hash = generate_password_hash(default_password)
                phone_norm = normalize_phone(default_phone_raw)
                name_norm = normalize_name(default_name)
                cur.execute('INSERT INTO admins (username, name, phone, password_hash, first_login) VALUES (%s,%s,%s,%s,0)',
                            (default_username, name_norm, phone_norm, pwd_hash))
                conn.commit()
            cur.close(); conn.close()
        except Exception:
            try:
                cur and cur.close(); conn and conn.close()
            except Exception:
                pass

    ensure_default_admin()
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )