import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import math
from datetime import datetime, date

# =========================================================================
# FUNÇÃO DE CONEXÃO (Corrigida para PostgreSQL)
# =========================================================================
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados PostgreSQL."""
    try:
        conn_string = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=st.secrets["postgres"]["PGUSER"],
            password=st.secrets["postgres"]["PGPASSWORD"],
            host=st.secrets["postgres"]["PGHOST"],
            port=st.secrets["postgres"]["PGPORT"],
            db=st.secrets["postgres"]["PGDATABASE"]
        )
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Erro crítico ao conectar ao banco de dados: {e}")
        st.info("Verifique se as credenciais [postgres] em seus 'Secrets' estão corretas.")
        return None

# =========================================================================
# CRIAÇÃO DE TABELAS (Corrigida para PostgreSQL)
# =========================================================================
def criar_tabelas_iniciais(conn):
    """Cria as tabelas com a sintaxe correta do PostgreSQL e nomes em minúsculas."""
    with conn.cursor() as cur:
        # Tabela Projetos (Sintaxe PostgreSQL)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id SERIAL PRIMARY KEY,
            projeto TEXT,
            descricao TEXT,
            agencia TEXT,
            tecnico TEXT,
            status TEXT,
            agendamento TIMESTAMP,
            data_abertura DATE,
            data_finalizacao DATE,
            observacao TEXT,
            demanda TEXT,
            log_agendamento JSONB,
            respostas_perguntas JSONB,
            etapas_concluidas JSONB
        );
        """)
        
        # Tabela Configuracoes
        cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            aba_nome TEXT PRIMARY KEY,
            dados_json JSONB
        );
        """)
        
        # Tabela Usuarios (Sintaxe PostgreSQL)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            email TEXT UNIQUE,
            senha TEXT
        );
        """)
    # Garante que as tabelas existam na primeira execução
    st.session_state['tabelas_verificadas'] = True

# Inicializa a conexão e verifica as tabelas
conn = get_db_connection()
if conn and 'tabelas_verificadas' not in st.session_state:
    criar_tabelas_iniciais(conn)

# =========================================================================
# FUNÇÃO DE AJUDA PARA NORMALIZAR CHAVES (Corrigida)
# =========================================================================
def normalize_key(key):
    """Normaliza uma chave para o padrão do banco: minúsculo, sem acentos, com underscore."""
    k = str(key).lower()
    k = k.replace('ç', 'c').replace('ê', 'e').replace('é', 'e').replace('ã', 'a')
    k = k.replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    k = k.replace(' de ', ' ')
    k = k.replace(' ', '_')
    # Remove caracteres especiais exceto underscore
    k = ''.join(c for c in k if c.isalnum() or c == '_')
    return k

# =========================================================================
# FUNÇÕES DO BANCO DE DADOS (PROJETOS - Corrigidas)
# =========================================================================
@st.cache_data(ttl=60)
def carregar_projetos_db():
    """Carrega projetos do banco de dados e renomeia colunas para exibição."""
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM projetos ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
        # Renomeia de minúsculo (banco) para maiúsculo/acentuado (exibição)
        df.rename(columns={
            'id': 'ID', 'projeto': 'Projeto', 'descricao': 'Descrição', 'agencia': 'Agência', 
            'tecnico': 'Técnico', 'status': 'Status', 'agendamento': 'Agendamento',
            'data_abertura': 'Data de Abertura', 'data_finalizacao': 'Data de Finalização', 
            'observacao': 'Observação', 'demanda': 'Demanda', 'log_agendamento': 'Log Agendamento',
            'respostas_perguntas': 'Respostas_Perguntas', 'etapas_concluidas': 'Etapas Concluidas'
        }, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

def sanitize_value(val):
    """Prepara valores para inserção segura no banco de dados."""
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    if isinstance(val, (int, float, bool, str)): return val
    if isinstance(val, (datetime, date)): return val
    try: return json.dumps(val)
    except Exception: return str(val)

def atualizar_projeto_db(project_id, updates: dict):
    """Atualiza um projeto no banco de dados."""
    if not conn: return False
    try:
        updates_normalized = {normalize_key(k): sanitize_value(v) for k, v in updates.items()}
        set_clause = ", ".join([f"{k} = %s" for k in updates_normalized.keys()])
        sql = f"UPDATE projetos SET {set_clause} WHERE id = %s"
        
        with conn.cursor() as cur:
            params = list(updates_normalized.values()) + [project_id]
            cur.execute(sql, params)
        st.cache_data.clear()
        st.toast("Projeto atualizado com sucesso!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥")
        return False

def adicionar_projeto_db(data: dict):
    """Adiciona um novo projeto ao banco de dados."""
    if not conn: return False
    try:
        db_data = {normalize_key(k): sanitize_value(v) for k, v in data.items()}
        cols_str = ', '.join(db_data.keys())
        placeholders = ', '.join(['%s'] * len(db_data))
        sql = f"INSERT INTO projetos ({cols_str}) VALUES ({placeholders})"
        
        with conn.cursor() as cur:
            cur.execute(sql, list(db_data.values()))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥")
        return False

def excluir_projeto_db(project_id):
    """Exclui um projeto do banco de dados."""
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # Placeholder %s para psycopg2
            cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear()
        st.toast("Projeto excluído!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥")
        return False

# (O restante das funções de config, usuários e utilitários seriam ajustadas de forma similar)
# ... (código restante do utils.py adaptado) ...
