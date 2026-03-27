from flask import Flask, render_template, request, redirect, session, flash
import uuid
from datetime import datetime

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

@app.route("/")
def inicio():
    # Garante CSRF token na sessão e passa para o template
    if 'csrf_token' not in session:
        session['csrf_token'] = str(uuid.uuid4())
    usuario = session.get('usuario')
    return render_template("index.html", csrf_token=session.get('csrf_token'), usuario=usuario)

@app.route("/cadastro", methods=["POST"])
def cadastro():
    nome = request.form.get("nome")
    numero = request.form.get("numero")
    # Salva dados na sessão e redireciona para a página de agendamento
    session['usuario'] = { 'nome': nome, 'numero': numero }
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
    return render_template('agendamento.html', usuario=usuario, csrf_token=session.get('csrf_token'), services=SERVICES)


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
    booking = {
        'usuario': usuario,
        'service_key': service_key,
        'service_label': svc['label'],
        'price': svc['price'],
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }
    # Armazena em session['bookings'] (lista)
    bookings = session.get('bookings', [])
    bookings.append(booking)
    session['bookings'] = bookings
    flash('Agendamento confirmado!')
    return redirect('/confirmacao')


@app.route('/confirmacao')
def confirmacao():
    bookings = session.get('bookings', [])
    if not bookings:
        flash('Nenhum agendamento encontrado.')
        return redirect('/')
    # Mostra o último agendamento realizado na sessão
    last = bookings[-1]
    return render_template('confirmacao.html', booking=last)


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