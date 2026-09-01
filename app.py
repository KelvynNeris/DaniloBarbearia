import hashlib
import hmac
import os
import re
import secrets
import smtplib
import time
import uuid
from datetime import datetime, date, timedelta, timezone
from email.mime.text import MIMEText
from urllib.parse import quote

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from conexao import Conexao

load_dotenv()

# Serviços padrão — usados apenas para popular a tabela `services` na primeira
# execução. Depois disso, os serviços de verdade vêm do banco e são
# gerenciáveis em /admin/servicos.
DEFAULT_SERVICES = [
    {'key': 'corte_social_barba', 'label': 'Corte social com barba', 'description': 'Acabamento social + barba modelada.', 'price': 50, 'image': 'images/corte_social_barba.svg'},
    {'key': 'corte_degrade_barba', 'label': 'Corte degradê com barba', 'description': 'Degradê personalizado + barba.', 'price': 52, 'image': 'images/corte_degrade_barba.svg'},
    {'key': 'corte_degrade', 'label': 'Corte degradê', 'description': 'Degradê limpo e bem marcado.', 'price': 32, 'image': 'images/corte_degrade.svg'},
    {'key': 'corte_social', 'label': 'Corte social', 'description': 'Corte social tradicional com finalização.', 'price': 27, 'image': 'images/corte_social.svg'},
    {'key': 'corte_maquina', 'label': 'Corte máquina', 'description': 'Corte rápido e preciso com máquina.', 'price': 22, 'image': 'images/corte_maquina.svg'},
    {'key': 'corte_navalhado', 'label': 'Corte navalhado', 'description': 'Acabamento com navalha para linhas definidas.', 'price': 32, 'image': 'images/corte_navalhado.svg'},
    {'key': 'barba', 'label': 'Barba', 'description': 'Modelagem, hidratação e finalização.', 'price': 27, 'image': 'images/barba.svg'},
    {'key': 'pezinho', 'label': 'Pezinho do cabelo', 'description': 'Ajuste nas laterais e nuca.', 'price': 17, 'image': 'images/pezinho.svg'},
    {'key': 'sobrancelha', 'label': 'Sobrancelha', 'description': 'Design e limpeza de sobrancelhas.', 'price': 10, 'image': 'images/sobrancelha.svg'},
    {'key': 'corte_tesoura', 'label': 'Corte só Tesoura', 'description': 'Corte apenas com tesoura para acabamento mais natural.', 'price': 32, 'image': 'images/corte_tesoura.svg'},
]

# Horário padrão — reproduz exatamente as regras que antes eram fixas no
# código. weekday: 0=segunda ... 6=domingo (padrão de date.weekday()).
DEFAULT_BUSINESS_HOURS = {
    0: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    1: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    2: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    3: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    4: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    5: {'is_closed': False, 'open': '08:00', 'close': '18:40', 'break_start': '11:00', 'break_end': '13:00'},
    6: {'is_closed': False, 'open': '09:00', 'close': '11:20', 'break_start': None, 'break_end': None},
}
SLOT_MINUTES = 20
WEEKDAY_LABELS_PT = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-dev")
app.secret_key = app.config["SECRET_KEY"]
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB por upload (fotos da galeria)

GALLERY_UPLOAD_DIR = os.path.join(app.root_path, 'static', 'uploads', 'gallery')
GALLERY_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# ---- Limitador simples de tentativas de login do admin (em memória) ----
# Protege contra força bruta sem precisar de infraestrutura extra (Redis etc).
# Funciona por processo: em produção com múltiplos workers cada um tem seu
# próprio contador, mas para o volume desta aplicação isso já é suficiente.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_LOCKOUT_SECONDS = 5 * 60
_login_attempts = {}


def _login_rate_key(username):
    ip = request.remote_addr or 'unknown'
    return f"{ip}:{(username or '').strip().lower()}"


def check_login_locked(key):
    """Retorna (bloqueado, segundos_restantes)."""
    info = _login_attempts.get(key)
    if not info:
        return False, 0
    locked_until = info.get('locked_until')
    if locked_until and time.time() < locked_until:
        return True, int(locked_until - time.time()) + 1
    return False, 0


def register_login_failure(key):
    now = time.time()
    info = _login_attempts.get(key)
    if not info or (now - info.get('first_attempt', now)) > LOGIN_WINDOW_SECONDS:
        info = {'count': 0, 'first_attempt': now, 'locked_until': None}
    info['count'] += 1
    if info['count'] >= LOGIN_MAX_ATTEMPTS:
        info['locked_until'] = now + LOGIN_LOCKOUT_SECONDS
    _login_attempts[key] = info


def clear_login_attempts(key):
    _login_attempts.pop(key, None)


# ---- Serviços e horário de funcionamento (gerenciáveis em /admin) ----

def ensure_services_table(conn=None):
    """Cria a tabela `services` se não existir e a popula com os serviços
    padrão na primeira vez (preservando o comportamento original)."""
    close_conn = False
    if conn is None:
        conn = Conexao.conectar()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `key` VARCHAR(64) UNIQUE NOT NULL,
                label VARCHAR(255) NOT NULL,
                description VARCHAR(500) NULL,
                price INT NOT NULL,
                image VARCHAR(255) NULL,
                active TINYINT(1) NOT NULL DEFAULT 1,
                sort_order INT NOT NULL DEFAULT 0
            )
        ''')
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM services')
        (count,) = cur.fetchone()
        if count == 0:
            for i, svc in enumerate(DEFAULT_SERVICES):
                cur.execute(
                    'INSERT INTO services (`key`, label, description, price, image, active, sort_order) VALUES (%s,%s,%s,%s,%s,1,%s)',
                    (svc['key'], svc['label'], svc['description'], svc['price'], svc['image'], i)
                )
            conn.commit()
        cur.close()
    finally:
        if close_conn:
            conn.close()


def load_services(active_only=True):
    """Retorna os serviços do banco como {key: {label, description, price, image}},
    na ordem de exibição. Cria/popula a tabela automaticamente se necessário."""
    try:
        conn = Conexao.conectar()
        ensure_services_table(conn)
        cur = conn.cursor(dictionary=True)
        if active_only:
            cur.execute('SELECT `key`, label, description, price, image, active FROM services WHERE active = 1 ORDER BY sort_order, id')
        else:
            cur.execute('SELECT `key`, label, description, price, image, active FROM services ORDER BY sort_order, id')
        rows = cur.fetchall()
        cur.close(); conn.close()
    except Exception:
        # Banco indisponível: cai para os serviços padrão em memória, para o
        # site continuar funcionando mesmo com o banco fora do ar.
        rows = [dict(svc, active=1) for svc in DEFAULT_SERVICES]

    services = {}
    for r in rows:
        services[r['key']] = {
            'label': r['label'],
            'description': r.get('description') or '',
            'price': r['price'],
            'image': r.get('image') or '',
            'active': bool(r.get('active', 1)),
        }
    return services


def ensure_business_hours_table(conn=None):
    """Cria a tabela `business_hours` se não existir e a popula com o
    horário padrão (equivalente ao que antes era fixo no código)."""
    close_conn = False
    if conn is None:
        conn = Conexao.conectar()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS business_hours (
                weekday TINYINT PRIMARY KEY,
                is_closed TINYINT(1) NOT NULL DEFAULT 0,
                open_time TIME NULL,
                close_time TIME NULL,
                break_start TIME NULL,
                break_end TIME NULL
            )
        ''')
        conn.commit()
        cur.execute('SELECT COUNT(*) FROM business_hours')
        (count,) = cur.fetchone()
        if count == 0:
            for weekday, h in DEFAULT_BUSINESS_HOURS.items():
                cur.execute(
                    'INSERT INTO business_hours (weekday, is_closed, open_time, close_time, break_start, break_end) VALUES (%s,%s,%s,%s,%s,%s)',
                    (weekday, int(h['is_closed']), h['open'], h['close'], h['break_start'], h['break_end'])
                )
            conn.commit()
        cur.close()
    finally:
        if close_conn:
            conn.close()


def load_business_hours():
    """Retorna o horário de funcionamento como {weekday: {is_closed, open, close, break_start, break_end}}
    (valores de horário já normalizados para 'HH:MM' ou None)."""
    try:
        conn = Conexao.conectar()
        ensure_business_hours_table(conn)
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT weekday, is_closed, open_time, close_time, break_start, break_end FROM business_hours ORDER BY weekday')
        rows = cur.fetchall()
        cur.close(); conn.close()
    except Exception:
        rows = [dict(weekday=w, **h) for w, h in DEFAULT_BUSINESS_HOURS.items()]
        for r in rows:
            r['is_closed'] = r.pop('is_closed')
            r['open_time'] = r.pop('open')
            r['close_time'] = r.pop('close')

    hours = {}
    for r in rows:
        hours[int(r['weekday'])] = {
            'is_closed': bool(r.get('is_closed')),
            'open': format_time_value(r.get('open_time')) or None,
            'close': format_time_value(r.get('close_time')) or None,
            'break_start': format_time_value(r.get('break_start')) or None,
            'break_end': format_time_value(r.get('break_end')) or None,
        }
    return hours


def _hhmm_to_minutes(hhmm):
    if not hhmm:
        return None
    parts = str(hhmm).split(':')
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_hhmm(total_minutes):
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def generate_slots_from_hours(open_hhmm, close_hhmm, break_start_hhmm, break_end_hhmm, slot_minutes=SLOT_MINUTES):
    """Gera os horários 'HH:MM' disponíveis entre open e close (inclusive),
    pulando o intervalo [break_start, break_end) quando informado."""
    start = _hhmm_to_minutes(open_hhmm)
    end = _hhmm_to_minutes(close_hhmm)
    if start is None or end is None:
        return []
    bstart = _hhmm_to_minutes(break_start_hhmm)
    bend = _hhmm_to_minutes(break_end_hhmm)
    slots = []
    m = start
    while m <= end:
        if bstart is None or bend is None or not (bstart <= m < bend):
            slots.append(_minutes_to_hhmm(m))
        m += slot_minutes
    return slots


def generate_allowed_slots_for_date_obj(d):
    """Retorna os horários 'HH:MM' permitidos para a data d, de acordo com o
    horário de funcionamento configurado em /admin/horarios.
    Se d for hoje, quem chamar deve filtrar os horários já passados.
    """
    hours = load_business_hours()
    day = hours.get(d.weekday())
    if not day or day.get('is_closed'):
        return []
    return generate_slots_from_hours(day.get('open'), day.get('close'), day.get('break_start'), day.get('break_end'))


# ---- Galeria de fotos (gerenciável em /admin/galeria) ----

def ensure_gallery_table(conn=None):
    close_conn = False
    if conn is None:
        conn = Conexao.conectar()
        close_conn = True
    try:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS gallery_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sort_order INT NOT NULL DEFAULT 0
            )
        ''')
        conn.commit()
        cur.close()
    finally:
        if close_conn:
            conn.close()


def load_gallery_images():
    try:
        conn = Conexao.conectar()
        ensure_gallery_table(conn)
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT id, filename FROM gallery_images ORDER BY sort_order, id')
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Exception:
        return []


def normalize_phone(raw):
    """Normalize phone numbers to a canonical form for storage and comparison.
    Rules: strip non-digits, then ensure a single +55 prefix.
    - 10 digits -> +55 + digits
    - 11 digits starting with 55 -> + + digits
    - 11 digits without 55 -> +55 + digits
    - >11 digits starting with 55 -> + + digits
    """
    if not raw:
        return ''
    digits = ''.join(ch for ch in str(raw) if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('55'):
        return '+' + digits
    if len(digits) == 10:
        return '+55' + digits
    if len(digits) == 11:
        return '+55' + digits
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


def format_date_value(d):
    """Normaliza um valor de data vindo do banco (date/str/None) para 'YYYY-MM-DD'."""
    if d is None:
        return ''
    try:
        return d.isoformat()
    except Exception:
        return str(d)[:10]


def format_time_value(t):
    """Normaliza um valor de hora vindo do banco (time/timedelta/str/None) para 'HH:MM'."""
    if t is None:
        return ''
    try:
        return t.strftime('%H:%M')
    except Exception:
        pass
    try:
        total_seconds = int(t.total_seconds())
        h, rem = divmod(total_seconds, 3600)
        m, _ = divmod(rem, 60)
        return f"{h:02d}:{m:02d}"
    except Exception:
        return str(t)[:5]


def format_date_br(date_str):
    """Converte 'YYYY-MM-DD' para 'DD/MM/YYYY' (uso em mensagens ao cliente)."""
    try:
        return datetime.strptime(str(date_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return str(date_str) if date_str else ''


def get_barber_whatsapp_number():
    """Retorna o telefone (só dígitos, com DDI) do barbeiro cadastrado como admin,
    para uso em links wa.me. Retorna None se não houver telefone configurado."""
    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT phone FROM admins ORDER BY id ASC LIMIT 1')
        row = cur.fetchone()
        cur.close(); conn.close()
    except Exception:
        return None
    phone = row.get('phone') if row else None
    if not phone:
        return None
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    return digits or None


def format_phone_display(phone):
    """Formata um telefone armazenado ('+55DDDNUMERO' ou similar) para exibição
    amigável '(DD) NNNNN-NNNN'."""
    if not phone:
        return ''
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith('55') and len(digits) > 11:
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return phone


def build_whatsapp_confirmation_link(booking):
    """Monta um link wa.me para o cliente avisar o barbeiro do agendamento,
    já com a mensagem pronta — o cliente só precisa clicar em enviar."""
    barber_phone = get_barber_whatsapp_number()
    if not barber_phone or not booking:
        return None
    usuario = booking.get('usuario') or {}
    msg = (
        "Olá! Acabei de agendar um horário na Danilo Barbearia:\n"
        f"💈 Serviço: {booking.get('service_label')}\n"
        f"📅 Data: {format_date_br(booking.get('date'))}\n"
        f"⏰ Horário: {booking.get('time')}\n"
        f"🙋 Nome: {usuario.get('nome', '')}"
    )
    return f"https://wa.me/{barber_phone}?text={quote(msg)}"


def send_admin_booking_notification(booking):
    """Envia um e-mail para o admin avisando de um novo agendamento — não
    depende do cliente fazer nada. Configurável via variáveis de ambiente
    (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ADMIN_NOTIFY_EMAIL).
    Se não estiver configurado, simplesmente não faz nada (o agendamento
    continua funcionando normalmente sem essa notificação).
    """
    smtp_host = os.getenv('SMTP_HOST')
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    notify_email = os.getenv('ADMIN_NOTIFY_EMAIL') or smtp_user
    if not smtp_host or not smtp_user or not smtp_password or not notify_email:
        return  # notificação por e-mail não configurada — segue sem erro

    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_from = os.getenv('SMTP_FROM') or smtp_user
    usuario = (booking or {}).get('usuario') or {}

    body = (
        "Novo agendamento na Danilo Barbearia:\n\n"
        f"Serviço: {booking.get('service_label')}\n"
        f"Data: {format_date_br(booking.get('date'))}\n"
        f"Horário: {booking.get('time')}\n"
        f"Cliente: {usuario.get('nome', '')}\n"
        f"Telefone: {usuario.get('numero', '')}\n"
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f"Novo agendamento — {usuario.get('nome', 'cliente')} ({booking.get('time')})"
    msg['From'] = smtp_from
    msg['To'] = notify_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [notify_email], msg.as_string())
        app.logger.info(f"E-mail de notificação enviado para {notify_email} (agendamento de {usuario.get('nome','')}).")
    except Exception:
        # Nunca deixar a notificação por e-mail derrubar o fluxo de agendamento —
        # mas registra o erro real no log pra dar pra diagnosticar depois
        # (ex.: provedor de hospedagem bloqueando conexões SMTP de saída).
        app.logger.exception("Falha ao enviar e-mail de notificação de agendamento.")


def hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of the password."""
    if password is None:
        password = ''
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify a password against a stored hash.
    Supports SHA-256 and legacy Werkzeug hashes for compatibility.
    """
    if not stored_hash:
        return False
    if stored_hash.startswith('scrypt:') or stored_hash.startswith('pbkdf2:') or stored_hash.startswith('argon2:') or stored_hash.startswith('md5:'):
        try:
            return check_password_hash(stored_hash, password)
        except Exception:
            return False
    return hash_password(password) == stored_hash


def generate_recovery_code():
    """Gera um código de recuperação legível, ex: 'AB3D-9KLM-2QRT-7XYZ'.
    Evita caracteres ambíguos (0/O, 1/I/L)."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    raw = ''.join(secrets.choice(alphabet) for _ in range(16))
    return '-'.join(raw[i:i + 4] for i in range(0, 16, 4))


def hash_recovery_code(code):
    normalized = (code or '').strip().upper().replace(' ', '')
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def ensure_recovery_code_column(conn=None):
    """Cria a coluna recovery_code_hash na tabela admins se ainda não existir."""
    close_conn = False
    if conn is None:
        conn = Conexao.conectar()
        close_conn = True
    try:
        cur = conn.cursor()
        try:
            cur.execute('SHOW COLUMNS FROM admins')
            columns = [str(col[0]).lower() for col in cur.fetchall()]
            if 'recovery_code_hash' not in columns:
                try:
                    cur.execute('ALTER TABLE admins ADD COLUMN recovery_code_hash VARCHAR(255) NULL')
                    conn.commit()
                except Exception:
                    pass
        finally:
            cur.close()
    finally:
        if close_conn:
            conn.close()


def ensure_first_login_column(conn=None):
    """Create the first_login column if the admins table is older and missing it.
    This preserves the first-login flow without breaking legacy schemas.
    """
    close_conn = False
    if conn is None:
        conn = Conexao.conectar()
        close_conn = True

    try:
        cur = conn.cursor()
        try:
            cur.execute('SHOW COLUMNS FROM admins')
            columns = [str(col[0]).lower() for col in cur.fetchall()]
            if 'first_login' not in columns:
                try:
                    cur.execute('ALTER TABLE admins ADD COLUMN first_login TINYINT(1) NOT NULL DEFAULT 0')
                    conn.commit()
                except Exception:
                    pass
        finally:
            cur.close()
    finally:
        if close_conn:
            conn.close()


def ensure_admin_schema(conn):
    """Garante as colunas opcionais da tabela admins (first_login, recovery_code_hash)."""
    ensure_first_login_column(conn)
    ensure_recovery_code_column(conn)


def fetch_admin(conn, username=None, admin_id=None):
    """Fetch an admin row by username or id, tolerating admins tables that
    don't have the 'first_login' column yet (older/legacy schema).

    Always uses a fresh cursor for the fallback query so a failed SELECT
    never leaves a stale/aborted cursor around for the next statement.
    """
    if username is None and admin_id is None:
        return None
    where_col = 'username' if username is not None else 'id'
    where_val = username if username is not None else admin_id

    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f'SELECT id, username, name, phone, password_hash, first_login, recovery_code_hash FROM admins WHERE {where_col} = %s LIMIT 1',
            (where_val,)
        )
        row = cur.fetchone()
    except Exception:
        cur.close()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            f'SELECT id, username, name, phone, password_hash FROM admins WHERE {where_col} = %s LIMIT 1',
            (where_val,)
        )
        row = cur.fetchone()
        if row is not None:
            row['first_login'] = 0
            row['recovery_code_hash'] = None
    finally:
        cur.close()
    return row


@app.route("/")
def inicio():
    # Garante CSRF token na sessão e passa para o template
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    usuario = session.get('usuario')
    barber_phone_digits = get_barber_whatsapp_number()
    barber_phone_display = format_phone_display(barber_phone_digits) if barber_phone_digits else None
    return render_template(
        "index.html",
        csrf_token=session.get('csrf_token'),
        usuario=usuario,
        barber_phone_digits=barber_phone_digits,
        barber_phone_display=barber_phone_display,
        services=load_services(active_only=True),
        gallery_images=load_gallery_images(),
    )


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
    if not username or not password:
        flash('Preencha usuário e senha.')
        return redirect('/admin/login')

    rate_key = _login_rate_key(username)
    locked, seconds_left = check_login_locked(rate_key)
    if locked:
        minutes = max(1, seconds_left // 60)
        flash(f'Muitas tentativas de login. Tente novamente em {minutes} minuto(s).')
        return redirect('/admin/login')

    try:
        conn = Conexao.conectar()
        ensure_admin_schema(conn)
        row = fetch_admin(conn, username=username)
        conn.close()
        if not row:
            register_login_failure(rate_key)
            flash('Usuário/senha inválidos.')
            return redirect('/admin/login')
        if not verify_password(row.get('password_hash', ''), password):
            register_login_failure(rate_key)
            flash('Usuário/senha inválidos.')
            return redirect('/admin/login')

        clear_login_attempts(rate_key)

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
    # Página "Minha conta": permite ao admin logado atualizar nome, telefone e senha
    # sempre que quiser — deixou de ser bloqueada após o primeiro acesso.
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    try:
        conn = Conexao.conectar()
        ensure_admin_schema(conn)
        admin_row = fetch_admin(conn, admin_id=admin_id)
        conn.close()
    except Exception:
        flash('Erro ao acessar o banco.')
        return redirect('/')

    if not admin_row:
        flash('Administrador não encontrado.')
        return redirect('/admin/login')

    is_first_login = int(admin_row.get('first_login') or 0) == 0
    has_recovery_code = bool(admin_row.get('recovery_code_hash'))

    if request.method == 'GET':
        return render_template('admin_change.html', admin=admin_row, is_first_login=is_first_login, has_recovery_code=has_recovery_code, csrf_token=session.get('csrf_token'))

    # POST: apply changes
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/change')

    name_raw = request.form.get('name') or ''
    phone_raw = request.form.get('phone') or ''
    password = request.form.get('password') or ''
    password2 = request.form.get('password2') or ''

    # No primeiro login exigimos uma senha nova (a senha padrão não deve continuar em uso).
    # Depois disso, a senha só é alterada se o admin preencher os campos de propósito.
    if is_first_login and not password:
        flash('Defina uma senha para continuar.')
        return redirect('/admin/change')
    if password or password2:
        if len(password) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.')
            return redirect('/admin/change')
        if password != password2:
            flash('As senhas não coincidem.')
            return redirect('/admin/change')

    name = normalize_name(name_raw) if name_raw.strip() else admin_row.get('name')
    phone = normalize_phone(phone_raw) if phone_raw.strip() else admin_row.get('phone')

    try:
        conn = Conexao.conectar()
        ensure_admin_schema(conn)
        cur = conn.cursor()
        if password:
            pwd_hash = hash_password(password)
            cur.execute('UPDATE admins SET name=%s, phone=%s, password_hash=%s, first_login=1 WHERE id = %s', (name, phone, pwd_hash, admin_id))
        else:
            cur.execute('UPDATE admins SET name=%s, phone=%s, first_login=1 WHERE id = %s', (name, phone, admin_id))
        conn.commit(); cur.close(); conn.close()
        flash('Dados atualizados com sucesso.')
        return redirect('/admin/agendas')
    except Exception:
        flash('Erro ao atualizar admin (banco).')
        return redirect('/admin/change')


@app.route('/admin/recovery-code/gerar', methods=['POST'])
def admin_gerar_codigo_recuperacao():
    # Gera (ou substitui) o código de recuperação do admin logado. Mostrado
    # apenas uma vez nesta resposta — só o hash fica salvo no banco.
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/change')

    code = generate_recovery_code()
    try:
        conn = Conexao.conectar()
        ensure_admin_schema(conn)
        cur = conn.cursor()
        cur.execute('UPDATE admins SET recovery_code_hash=%s WHERE id = %s', (hash_recovery_code(code), admin_id))
        conn.commit(); cur.close(); conn.close()
    except Exception:
        flash('Erro ao gerar o código de recuperação (banco).')
        return redirect('/admin/change')

    return render_template('admin_recovery_code.html', code=code, csrf_token=session.get('csrf_token'))


@app.route('/admin/recuperar', methods=['GET', 'POST'])
def admin_recuperar():
    # Recuperação de senha sem depender de e-mail/SMS: usa o código de
    # recuperação gerado previamente em "Minha conta".
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())

    if request.method == 'GET':
        return render_template('admin_recuperar.html', csrf_token=session.get('csrf_token'))

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/recuperar')

    username = (request.form.get('username') or '').strip()
    code = request.form.get('code') or ''
    password = request.form.get('password') or ''
    password2 = request.form.get('password2') or ''

    if not username or not code or not password:
        flash('Preencha usuário, código de recuperação e a nova senha.')
        return redirect('/admin/recuperar')
    if len(password) < 6:
        flash('A nova senha deve ter pelo menos 6 caracteres.')
        return redirect('/admin/recuperar')
    if password != password2:
        flash('As senhas não coincidem.')
        return redirect('/admin/recuperar')

    rate_key = 'recovery:' + _login_rate_key(username)
    locked, seconds_left = check_login_locked(rate_key)
    if locked:
        minutes = max(1, seconds_left // 60)
        flash(f'Muitas tentativas. Tente novamente em {minutes} minuto(s).')
        return redirect('/admin/recuperar')

    try:
        conn = Conexao.conectar()
        ensure_admin_schema(conn)
        row = fetch_admin(conn, username=username)
    except Exception:
        flash('Erro ao acessar o banco.')
        return redirect('/admin/recuperar')

    stored_hash = row.get('recovery_code_hash') if row else None
    if not row or not stored_hash or not hmac.compare_digest(stored_hash, hash_recovery_code(code)):
        register_login_failure(rate_key)
        conn.close()
        flash('Usuário ou código de recuperação inválidos.')
        return redirect('/admin/recuperar')

    clear_login_attempts(rate_key)

    # Redefine a senha e já gera um novo código (o antigo deixa de valer)
    new_code = generate_recovery_code()
    try:
        cur = conn.cursor()
        cur.execute(
            'UPDATE admins SET password_hash=%s, recovery_code_hash=%s WHERE id = %s',
            (hash_password(password), hash_recovery_code(new_code), row.get('id'))
        )
        conn.commit(); cur.close(); conn.close()
    except Exception:
        flash('Erro ao redefinir a senha (banco).')
        return redirect('/admin/recuperar')

    flash('Senha redefinida com sucesso. Guarde o novo código de recuperação abaixo.')
    return render_template('admin_recovery_code.html', code=new_code, csrf_token=session.get('csrf_token'))


@app.route('/ocupados')
def ocupados():
    # Retorna JSON com os horários ocupados E os horários permitidos (segundo o
    # horário de funcionamento configurado em /admin/horarios) para uma data.
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'missing date'}), 400

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        allowed = generate_allowed_slots_for_date_obj(selected_date)
        if selected_date == date.today():
            now = datetime.now()
            allowed = [
                t for t in allowed
                if datetime(now.year, now.month, now.day, int(t.split(':')[0]), int(t.split(':')[1])) > now
            ]
    except Exception:
        allowed = []

    occupied = []
    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        cur.execute("SELECT time FROM agendamentos WHERE date = %s", (date_str,))
        rows = cur.fetchall()
        for r in rows:
            t = r[0] if isinstance(r, (list, tuple)) else r
            occupied.append(format_time_value(t))
        cur.close(); conn.close()
    except Exception:
        # on DB error, return empty array (frontend will still show available slots)
        occupied = []
    return jsonify({'occupied': occupied, 'allowed': allowed})

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
    return render_template('agendamento.html', usuario=usuario, csrf_token=session.get('csrf_token'), services=load_services(active_only=True), today=today)


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
    svc = load_services(active_only=True).get(service_key)
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

        # Avisa o admin por e-mail (se configurado). Nunca deve quebrar o
        # agendamento em si — send_admin_booking_notification já se protege.
        send_admin_booking_notification(booking)

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
                svc = load_services(active_only=False).get(r.get('service_key')) or {}
                booking = {
                    'id': r.get('id'),
                    'date': format_date_value(r.get('date')),
                    'time': format_time_value(r.get('time')),
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

    whatsapp_link = build_whatsapp_confirmation_link(booking)

    return render_template('confirmacao.html', booking=booking, usuario=session.get('usuario'), csrf_token=session.get('csrf_token'), whatsapp_link=whatsapp_link)


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
        services_map = load_services(active_only=False)
        for r in rows:
            svc = services_map.get(r['service_key'], {})
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
                svc = load_services(active_only=False).get(r['service_key'], {})
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


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    # Valida token CSRF e remove o admin da sessão
    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/login')
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    # Renovar o csrf_token
    session['csrf_token'] = str(uuid.uuid4())
    flash('Você saiu com sucesso.')
    return redirect('/')


@app.route('/admin/cancelar', methods=['POST'])
def admin_cancelar():
    # Permite ao administrador cancelar qualquer agendamento diretamente pelo dashboard
    # (diferente de /cancelar, que só permite ao próprio cliente cancelar o seu).
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/agendas')

    bid = request.form.get('booking_id')
    if not bid:
        flash('Agendamento inválido.')
        return redirect('/admin/agendas')

    try:
        conn = Conexao.conectar()
        cur = conn.cursor()
        cur.execute("DELETE FROM agendamentos WHERE id = %s", (bid,))
        deleted = cur.rowcount
        conn.commit()
        cur.close(); conn.close()
        if deleted:
            flash('Agendamento cancelado.')
        else:
            flash('Agendamento não encontrado (já pode ter sido cancelado).')
    except Exception:
        flash('Erro ao cancelar o agendamento (banco).')

    return redirect('/admin/agendas')


def slugify_service_key(label, existing_keys):
    """Gera uma chave única (slug) a partir do rótulo de um serviço novo."""
    base = re.sub(r'[^a-z0-9]+', '_', (label or '').strip().lower()).strip('_') or 'servico'
    key = base
    i = 2
    while key in existing_keys:
        key = f"{base}_{i}"
        i += 1
    return key


@app.route('/admin/servicos', methods=['GET'])
def admin_servicos():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')
    services = load_services(active_only=False)
    return render_template('admin_servicos.html', services=services, csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))


@app.route('/admin/servicos/adicionar', methods=['POST'])
def admin_servicos_adicionar():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/servicos')

    label = (request.form.get('label') or '').strip()
    description = (request.form.get('description') or '').strip()
    price_raw = (request.form.get('price') or '').strip()

    if not label or not price_raw:
        flash('Preencha o nome e o preço do serviço.')
        return redirect('/admin/servicos')
    try:
        price = int(round(float(price_raw.replace(',', '.'))))
        if price < 0:
            raise ValueError
    except ValueError:
        flash('Preço inválido.')
        return redirect('/admin/servicos')

    try:
        conn = Conexao.conectar()
        ensure_services_table(conn)
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT `key` FROM services')
        existing_keys = {r['key'] for r in cur.fetchall()}
        new_key = slugify_service_key(label, existing_keys)
        cur.execute('SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM services')
        next_order = cur.fetchone()['next_order']
        cur.execute(
            'INSERT INTO services (`key`, label, description, price, image, active, sort_order) VALUES (%s,%s,%s,%s,NULL,1,%s)',
            (new_key, label, description or None, price, next_order)
        )
        conn.commit(); cur.close(); conn.close()
        flash(f'Serviço "{label}" adicionado.')
    except Exception:
        flash('Erro ao adicionar o serviço (banco).')

    return redirect('/admin/servicos')


@app.route('/admin/servicos/atualizar', methods=['POST'])
def admin_servicos_atualizar():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/servicos')

    key = request.form.get('key')
    label = (request.form.get('label') or '').strip()
    description = (request.form.get('description') or '').strip()
    price_raw = (request.form.get('price') or '').strip()
    active = 1 if request.form.get('active') == 'on' else 0

    if not key or not label or not price_raw:
        flash('Preencha o nome e o preço do serviço.')
        return redirect('/admin/servicos')
    try:
        price = int(round(float(price_raw.replace(',', '.'))))
        if price < 0:
            raise ValueError
    except ValueError:
        flash('Preço inválido.')
        return redirect('/admin/servicos')

    try:
        conn = Conexao.conectar()
        ensure_services_table(conn)
        cur = conn.cursor()
        cur.execute(
            'UPDATE services SET label=%s, description=%s, price=%s, active=%s WHERE `key`=%s',
            (label, description or None, price, active, key)
        )
        conn.commit(); cur.close(); conn.close()
        flash('Serviço atualizado.')
    except Exception:
        flash('Erro ao atualizar o serviço (banco).')

    return redirect('/admin/servicos')


@app.route('/admin/horarios', methods=['GET'])
def admin_horarios():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')
    hours = load_business_hours()
    days = [
        {'weekday': w, 'label': WEEKDAY_LABELS_PT[w], **hours.get(w, {})}
        for w in range(7)
    ]
    return render_template('admin_horarios.html', days=days, csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))


@app.route('/admin/horarios/salvar', methods=['POST'])
def admin_horarios_salvar():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/horarios')

    time_pattern = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

    def clean_time(value):
        value = (value or '').strip()
        return value if time_pattern.match(value) else None

    try:
        conn = Conexao.conectar()
        ensure_business_hours_table(conn)
        cur = conn.cursor()
        for weekday in range(7):
            is_closed = 1 if request.form.get(f'closed_{weekday}') == 'on' else 0
            open_time = clean_time(request.form.get(f'open_{weekday}'))
            close_time = clean_time(request.form.get(f'close_{weekday}'))
            break_start = clean_time(request.form.get(f'break_start_{weekday}'))
            break_end = clean_time(request.form.get(f'break_end_{weekday}'))
            # intervalo só vale se ambos os limites forem informados
            if not (break_start and break_end):
                break_start = None
                break_end = None
            cur.execute(
                '''UPDATE business_hours
                   SET is_closed=%s, open_time=%s, close_time=%s, break_start=%s, break_end=%s
                   WHERE weekday=%s''',
                (is_closed, open_time, close_time, break_start, break_end, weekday)
            )
        conn.commit(); cur.close(); conn.close()
        flash('Horário de funcionamento atualizado.')
    except Exception:
        flash('Erro ao salvar o horário (banco).')

    return redirect('/admin/horarios')


@app.route('/admin/galeria', methods=['GET'])
def admin_galeria():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')
    images = load_gallery_images()
    return render_template('admin_galeria.html', images=images, csrf_token=session.get('csrf_token'), usuario=session.get('usuario'))


@app.route('/admin/galeria/upload', methods=['POST'])
def admin_galeria_upload():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/galeria')

    file = request.files.get('photo')
    if not file or not file.filename:
        flash('Escolha uma foto para enviar.')
        return redirect('/admin/galeria')

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in GALLERY_ALLOWED_EXTENSIONS:
        flash('Formato não suportado. Envie uma imagem JPG, PNG ou WEBP.')
        return redirect('/admin/galeria')

    try:
        os.makedirs(GALLERY_UPLOAD_DIR, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{ext}"
        file.save(os.path.join(GALLERY_UPLOAD_DIR, filename))

        conn = Conexao.conectar()
        ensure_gallery_table(conn)
        cur = conn.cursor()
        cur.execute('SELECT COALESCE(MAX(sort_order), -1) + 1 FROM gallery_images')
        (next_order,) = cur.fetchone()
        cur.execute('INSERT INTO gallery_images (filename, sort_order) VALUES (%s, %s)', (filename, next_order))
        conn.commit(); cur.close(); conn.close()
        flash('Foto adicionada à galeria.')
    except Exception:
        flash('Erro ao enviar a foto.')

    return redirect('/admin/galeria')


@app.route('/admin/galeria/excluir', methods=['POST'])
def admin_galeria_excluir():
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('csrf_token'):
        flash('Requisição inválida (CSRF).')
        return redirect('/admin/galeria')

    image_id = request.form.get('image_id')
    if not image_id:
        flash('Imagem inválida.')
        return redirect('/admin/galeria')

    try:
        conn = Conexao.conectar()
        ensure_gallery_table(conn)
        cur = conn.cursor(dictionary=True)
        cur.execute('SELECT filename FROM gallery_images WHERE id = %s', (image_id,))
        row = cur.fetchone()
        cur.execute('DELETE FROM gallery_images WHERE id = %s', (image_id,))
        conn.commit(); cur.close(); conn.close()
        if row:
            try:
                os.remove(os.path.join(GALLERY_UPLOAD_DIR, row['filename']))
            except OSError:
                pass
            flash('Foto removida.')
        else:
            flash('Foto não encontrada.')
    except Exception:
        flash('Erro ao remover a foto (banco).')

    return redirect('/admin/galeria')


@app.route('/admin/agendas')
def admin_agendas():
    # Dashboard do administrador: KPIs, agenda do dia, tendência e distribuição
    # por serviço, além da lista completa e pesquisável de agendamentos.
    admin_id = session.get('admin_id')
    if not admin_id:
        flash('Faça login como administrador.')
        return redirect('/admin/login')

    agendas = []
    services_map = load_services(active_only=False)
    try:
        conn = Conexao.conectar()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, date, time, client_name, client_phone, service_key, created_at FROM agendamentos ORDER BY date DESC, time DESC")
        rows = cur.fetchall()
        for r in rows:
            svc = services_map.get(r.get('service_key'), {})
            agendas.append({
                'id': r.get('id'),
                'date': format_date_value(r.get('date')),
                'time': format_time_value(r.get('time')),
                'service_key': r.get('service_key'),
                'service_label': svc.get('label', r.get('service_key')),
                'price': svc.get('price'),
                'client_name': r.get('client_name'),
                'client_phone': r.get('client_phone'),
                'created_at': r.get('created_at')
            })
        cur.close(); conn.close()
    except Exception:
        flash('Erro ao acessar agendamentos (banco).')

    # ---- Agregações do dashboard (calculadas em cima da lista já buscada,
    # sem novas consultas ao banco) ----
    today = date.today()
    today_str = today.isoformat()
    now_hhmm = datetime.now().strftime('%H:%M')
    week_start_str = (today - timedelta(days=today.weekday())).isoformat()
    month_prefix = today.strftime('%Y-%m')

    today_list = sorted([a for a in agendas if a['date'] == today_str], key=lambda a: a['time'])
    week_list = [a for a in agendas if a['date'] >= week_start_str]
    month_list = [a for a in agendas if a['date'].startswith(month_prefix)]
    month_revenue = sum(a['price'] or 0 for a in month_list)
    unique_clients = len(set(a['client_phone'] for a in agendas if a.get('client_phone')))

    svc_counts = {}
    for a in agendas:
        k = a.get('service_key')
        if k:
            svc_counts[k] = svc_counts.get(k, 0) + 1
    top_service = None
    if svc_counts:
        best_key = max(svc_counts.items(), key=lambda x: x[1])[0]
        top_service = {'label': services_map.get(best_key, {}).get('label', best_key), 'count': svc_counts[best_key]}

    upcoming = None
    for a in sorted(agendas, key=lambda a: (a['date'], a['time'])):
        if a['date'] > today_str or (a['date'] == today_str and a['time'] >= now_hhmm):
            upcoming = a
            break

    stats = {
        'today_count': len(today_list),
        'week_count': len(week_list),
        'month_revenue': month_revenue,
        'total_count': len(agendas),
        'unique_clients': unique_clients,
        'top_service': top_service,
        'upcoming': upcoming,
    }

    # Série dos últimos 14 dias para o gráfico de tendência
    days_series = []
    for i in range(13, -1, -1):
        d_str = (today - timedelta(days=i)).isoformat()
        day_bookings = [a for a in agendas if a['date'] == d_str]
        days_series.append({
            'date': d_str,
            'bookings': len(day_bookings),
            'revenue': sum(a['price'] or 0 for a in day_bookings),
        })
    max_day_bookings = max((d['bookings'] for d in days_series), default=0)

    # Distribuição por serviço (top 5 + "Outros"), já pronta como conic-gradient
    palette = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']
    dist_sorted = sorted(svc_counts.items(), key=lambda x: -x[1])
    top_dist = dist_sorted[:5]
    rest_count = sum(c for _, c in dist_sorted[5:])
    slices = []
    for i, (key, cnt) in enumerate(top_dist):
        slices.append({'label': services_map.get(key, {}).get('label', key), 'count': cnt, 'color': palette[i % len(palette)]})
    if rest_count:
        slices.append({'label': 'Outros', 'count': rest_count, 'color': 'var(--muted)'})

    total_slices = sum(s['count'] for s in slices) or 1
    cursor_pct = 0.0
    gradient_parts = []
    for s in slices:
        pct = s['count'] / total_slices * 100
        s['pct'] = round(pct, 1)
        gradient_parts.append(f"{s['color']} {cursor_pct:.2f}% {cursor_pct + pct:.2f}%")
        cursor_pct += pct
    donut_gradient = ', '.join(gradient_parts) if gradient_parts else 'var(--surface-2) 0% 100%'

    return render_template(
        'admin_agendas.html',
        agendas=agendas,
        csrf_token=session.get('csrf_token'),
        usuario=session.get('usuario'),
        today_str=today_str,
        stats=stats,
        today_list=today_list,
        days_series=days_series,
        max_day_bookings=max_day_bookings,
        service_slices=slices,
        donut_gradient=donut_gradient,
    )


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
    services_map = load_services(active_only=False)
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
            most_booked = {'service_key': best[0], 'label': services_map.get(best[0], {}).get('label', best[0]), 'count': best[1]}

        # revenue per day (group by date and service_key, then multiply by price)
        cur.execute("SELECT date, service_key, COUNT(*) FROM agendamentos WHERE date BETWEEN %s AND %s GROUP BY date, service_key ORDER BY date ASC", (start_date, end_date))
        rows = cur.fetchall()
        for r in rows:
            d = r[0]
            key = r[1]
            cnt = int(r[2])
            price = services_map.get(key, {}).get('price', 0)
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
                pwd_hash = hash_password(default_password)
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