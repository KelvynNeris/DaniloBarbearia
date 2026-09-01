-- Script de Inicialização do Banco de Dados - Danilo Barbearia
-- Execute este script no MySQL Workbench para criar o banco de dados localmente

-- Criar o banco de dados
CREATE DATABASE IF NOT EXISTS barbearia_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE barbearia_db;

-- Tabela de agendamentos
CREATE TABLE IF NOT EXISTS agendamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    client_phone VARCHAR(20) NOT NULL,
    service_key VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_datetime (date, time),
    INDEX idx_client_phone (client_phone),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela de administradores
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    first_login TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Inserir administrador padrão (usuário: adm, senha: 123)
-- IMPORTANTE: Após o primeiro login, altere esta senha!
INSERT INTO admins (username, name, phone, password_hash, first_login)
VALUES (
    'adm',
    'Administrador',
    '+5599999999999',
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3',
    0
) ON DUPLICATE KEY UPDATE username = username;

-- Verificar se as tabelas foram criadas
SHOW TABLES;

-- Verificar o administrador padrão
SELECT id, username, name, phone, first_login FROM admins;

-- Mensagem de sucesso
SELECT 'Banco de dados configurado com sucesso!' AS Status;
SELECT 'Use as credenciais abaixo para fazer login:' AS Info;
SELECT 'Usuário: adm' AS Usuario, 'Senha: 123' AS Senha, 'Telefone: (99) 99999-9999' AS Telefone;
