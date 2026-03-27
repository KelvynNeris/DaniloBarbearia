-- Schema de exemplo para a tabela de agendamentos
-- Inclui variantes para MySQL e SQLite (conceito)

-- =======================
-- MySQL / MariaDB
-- =======================
-- Ajuste o CHARACTER SET / COLLATE conforme necessidade do projeto.

-- Cria o database usado pela aplicação (executar no Workbench antes/como parte deste script)
CREATE DATABASE IF NOT EXISTS bd_barbearia DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bd_barbearia;

-- Tabela: agendamentos
-- Campos:
-- id            : PK autoincrement
-- date          : data do agendamento (YYYY-MM-DD)
-- time          : horário do slot (HH:MM)
-- client_name   : nome do cliente
-- client_phone  : número de telefone (texto para preservar zeros e formatos)
-- service_key   : chave do serviço (referência para catálogo de serviços)
-- status        : status do agendamento (ex: confirmed, cancelled)
-- created_at    : data/hora de criação do registro

CREATE TABLE IF NOT EXISTS agendamentos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  date DATE NOT NULL,
  time TIME NOT NULL,
  client_name VARCHAR(255) NOT NULL,
  client_phone VARCHAR(50) NOT NULL,
  service_key VARCHAR(100) NOT NULL,
  status ENUM('confirmed','cancelled') NOT NULL DEFAULT 'confirmed',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- evita duplo agendamento no mesmo dia/horário
  CONSTRAINT uq_agendamento_unique_slot UNIQUE (date, time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices para consultas comuns
CREATE INDEX idx_agend_date ON agendamentos(date);
CREATE INDEX idx_agend_service ON agendamentos(service_key);

-- =======================
-- Tabela: admins (proprietário/administradores)
-- Campos:
-- id            : PK autoincrement
-- username      : identificador único para login (ex: email ou user)
-- name          : nome completo do administrador
-- phone         : telefone de contato (opcional, único)
-- password_hash : senha criptografada (bcrypt/werkzeug)
-- created_at    : timestamp de criação

CREATE TABLE IF NOT EXISTS admins (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(150) NOT NULL,
  name VARCHAR(255) NOT NULL,
  phone VARCHAR(50) DEFAULT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_admin_username UNIQUE (username),
  CONSTRAINT uq_admin_phone UNIQUE (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional: inserir um administrador pré-definido.
-- Observação importante: a aplicação (`app.py`) já contém uma rotina que cria
-- o administrador padrão com a senha corretamente 'hashada' por Python/werkzeug
-- (recomenda-se deixar que a aplicação crie o registro). Se preferir inserir
-- via SQL, gere primeiro o hash da senha com Python e cole o resultado abaixo
-- no lugar de <PASTE_HASH_HERE>.
-- Exemplo para gerar o hash localmente (execute na pasta do projeto):
--   python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('123'))"
-- Em seguida copie o valor retornado e substitua <PASTE_HASH_HERE> no INSERT abaixo.

-- Template de INSERT (execute após gerar o hash):
-- INSERT INTO admins (username, name, phone, password_hash)
-- VALUES ('adm', 'adm', '+55 (99) 99999-9999', '<PASTE_HASH_HERE>');
-- Se desejar apenas garantir a presença do registro sem gerar hash agora,
-- a aplicação criará o administrador padrão automaticamente ao iniciar.

-- INSERT gerado com hash da senha '123' (gerado via werkzeug)
INSERT INTO admins (username, name, phone, password_hash)
VALUES ('adm', 'adm', '+55 (99) 99999-9999', 'scrypt:32768:8:1$IDKMEqRzALJru5W3$0640f90d278e5e391e2f0b2aa90d402a4e50faf6745457d794d556ca817cef8b309cd9b85eaf72c20cca205c6b3c4cf21d2c225ba80eb206441fbd7fba2ae392');

-- Se desejar apenas garantir a presença do registro sem gerar hash agora,
-- a aplicação criará o administrador padrão automaticamente ao iniciar.


-- Exemplo de checagem/insert seguro com lock (pseudo):
-- START TRANSACTION;
-- SELECT COUNT(*) FROM agendamentos WHERE date = '2026-03-29' AND time = '09:20' FOR UPDATE;
-- -- se COUNT == 0, INSERT INTO agendamentos(...)
-- COMMIT;


-- =======================
-- SQLite
-- =======================
-- SQLite não tem TIME/DATE nativos robustos: armazenamos como TEXT (ISO formats)
-- Exemplo:

-- CREATE TABLE IF NOT EXISTS agendamentos (
--   id INTEGER PRIMARY KEY AUTOINCREMENT,
--   date TEXT NOT NULL,         -- 'YYYY-MM-DD'
--   time TEXT NOT NULL,         -- 'HH:MM'
--   client_name TEXT NOT NULL,
--   client_phone TEXT NOT NULL,
--   service_key TEXT NOT NULL,
--   status TEXT NOT NULL DEFAULT 'confirmed',
--   created_at TEXT NOT NULL DEFAULT (datetime('now'))
-- );
-- CREATE UNIQUE INDEX IF NOT EXISTS uq_agendamento_unique_slot ON agendamentos(date, time);
-- CREATE INDEX IF NOT EXISTS idx_agend_date ON agendamentos(date);

-- =======================
-- Observações / boas práticas
-- =======================
-- 1) Se for usar PostgreSQL, prefira types DATE and TIME (ou TIMESTAMP with time zone).
-- 2) Evitar armazenar números de telefone como INTEGER (perde zeros e sinais); usar VARCHAR/TEXT.
-- 3) A constraint UNIQUE(date,time) evita duplo-agendamento no mesmo slot. Se quiser permitir múltiplos
--    atendimentos simultâneos (ex.: 2 cadeiras), troque o unique por uma verificação de capacidade
--    ou adicione um campo `chair_id` e torne a combinação (date,time,chair_id) única.
-- 4) Para concorrência: use transações e locks adequados; no MySQL InnoDB um SELECT ... FOR UPDATE
--    dentro de uma transação funciona para checar e reservar atomically.
-- 5) Se o projeto aceitar timezone, guarde horários em UTC ou salve o timezone do estabelecimento e
--    normalize na aplicação.

-- =======================
-- Exemplos de uso (MySQL)
-- =======================
-- Inserir um agendamento (exemplo)
-- INSERT INTO agendamentos (date, time, client_name, client_phone, service_key)
-- VALUES ('2026-03-29', '09:20', 'João Silva', '+5511999999999', 'corte_degrade');

-- Verificar se slot livre
-- SELECT COUNT(*) AS booked FROM agendamentos WHERE date = '2026-03-29' AND time = '09:20';

-- Listar agendamentos de um dia
-- SELECT * FROM agendamentos WHERE date = '2026-03-29' ORDER BY time;
