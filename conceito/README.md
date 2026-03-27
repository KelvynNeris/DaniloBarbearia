Banco de dados (conceito) — Agendamentos

Objetivo
-------
Documento conceitual com o schema e instruções mínimas para a tabela de agendamentos da barbearia.

Requisitos funcionais atendidos
------------------------------
- Armazenar data e hora do agendamento (slot de 20 minutos).
- Armazenar dados do cliente (nome e número).
- Registrar qual serviço foi escolhido (chave do catálogo de serviços).
- Evitar duplo-agendamento para o mesmo slot (constraint única).
- Registrar momento da criação.

Tabela principal
----------------
Nome: agendamentos
Campos principais:
- id (PK autoincrement)
- date (DATE) — data no formato ISO YYYY-MM-DD
- time (TIME) — horário do slot (HH:MM)
- client_name (VARCHAR) — nome do cliente
- client_phone (VARCHAR) — telefone do cliente
- service_key (VARCHAR) — chave do serviço (ex.: 'corte_degrade')
- status (ENUM/TEXT) — 'confirmed' | 'cancelled' (padrão: 'confirmed')
- created_at (TIMESTAMP) — quando o registro foi criado

Restrições e índices
--------------------
- UNIQUE(date, time) — evita reservas duplas no mesmo slot.
- Índice em `date` para consultas por dia.
- Índice em `service_key` caso queira gerar relatórios por serviço.

Concorrência e reserva de slot
------------------------------
Para evitar condições de corrida (dois clientes reservando o mesmo slot ao mesmo tempo):
- Use transações com SELECT ... FOR UPDATE (MySQL InnoDB) ou equivalente.
- Fluxo sugerido: iniciar transação -> verificar se existe agendamento para date+time -> inserir -> commit.

Observações sobre capacidade
----------------------------
Se a barbearia tiver N cadeiras e quiser permitir até N agendamentos simultâneos por slot, não use a
constraint UNIQUE(date,time). Em vez disso:
- Adicione um campo `chair_id` ou `capacity` e torne a combinação (date,time,chair_id) única; OU
- Conte quantos agendamentos existem para (date,time) e permita inserção somente se COUNT < N.

Exemplos rápidos
----------------
- Criar tabela (veja `schema.sql` para o SQL completo).
- Verificar disponibilidade do slot (SQL):
  SELECT COUNT(*) FROM agendamentos WHERE date = 'YYYY-MM-DD' AND time = 'HH:MM';

Integração com a app Flask
--------------------------
- Use `conexao.py` (se existir) para abrir conexão com o DB.
- Ao confirmar um agendamento (`/confirmar`):
  1) Iniciar transação.
  2) Checar contagem para date+time.
  3) Se 0, inserir o agendamento e commitar.
  4) Se >0, retornar erro ao usuário informando que o slot foi ocupado.

Próximos passos possíveis
------------------------
- Implementar migração (ex.: arquivo alembic/Flask-Migrate se usar SQLAlchemy).
- Implementar a gravação efetiva no backend (`app.py`) usando `conexao.py` ou SQLAlchemy.
- Adicionar endpoint de listagem de agendamentos por dia e endpoint de cancelamento.

Se quiser, eu:
- gero o SQL de criação já adaptado para o seu `conexao.py` (MySQL) e adiciono a função de inserção/checagem no `app.py`;
- ou implemento uma versão simples usando SQLite e um pequeno módulo `db.py` para integração local rápida.
