import streamlit as st
import pandas as pd
import psycopg2
import json
import math
import os
import re
from datetime import datetime, date
from io import StringIO

# =========================================================================
# FUNÇÃO DE CONEXÃO E CRIAÇÃO DE TABELAS
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

def criar_tabelas_iniciais(conn):
    """Cria as tabelas com a sintaxe correta do PostgreSQL e nomes em minúsculas."""
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id SERIAL PRIMARY KEY, projeto TEXT, descricao TEXT, agencia TEXT,
            tecnico TEXT, status TEXT, agendamento TIMESTAMP, data_abertura DATE,
            data_finalizacao DATE, observacao TEXT, demanda TEXT, log_agendamento JSONB,
            respostas_perguntas JSONB, etapas_concluidas JSONB
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            aba_nome TEXT PRIMARY KEY, dados_json JSONB
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, senha TEXT
        );""")
    st.session_state['tabelas_verificadas'] = True

# Inicializa a conexão e verifica as tabelas na primeira execução
conn = get_db_connection()
if conn and 'tabelas_verificadas' not in st.session_state:
    criar_tabelas_iniciais(conn)

# =========================================================================
# FUNÇÕES DO BANCO DE DADOS (PROJETOS)
# =========================================================================
@st.cache_data(ttl=60)
def carregar_projetos_db():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM projetos ORDER BY id DESC", conn)
        df.rename(columns={
            'id': 'ID', 'projeto': 'Projeto', 'descricao': 'Descrição', 'agencia': 'Agência', 
            'tecnico': 'Técnico', 'status': 'Status', 'agendamento': 'Agendamento',
            'data_abertura': 'Data de Abertura', 'data_finalizacao': 'Data de Finalização', 
            'observacao': 'Observação', 'demanda': 'Demanda'
        }, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

def adicionar_projeto_db(data: dict):
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

def atualizar_projeto_db(project_id, updates: dict):
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

def excluir_projeto_db(project_id):
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear()
        st.toast("Projeto excluído!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥")
        return False

# =========================================================================
# FUNÇÕES DO BANCO (CONFIGURAÇÕES E USUÁRIOS)
# =========================================================================
@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT dados_json FROM configuracoes WHERE aba_nome = %s"
        df_raw = pd.read_sql_query(query, conn, params=(tab_name.lower(),))
        if not df_raw.empty and df_raw['dados_json'][0]:
            json_data = df_raw['dados_json'][0]
            if isinstance(json_data, str):
                return pd.read_json(StringIO(json_data))
            else:
                return pd.DataFrame(json_data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar config '{tab_name}': {e}")
        return pd.DataFrame()

def salvar_config_db(df, tab_name):
    if not conn: return False
    try:
        tab_name = tab_name.lower()
        dados_json = df.to_json(orient='records')
        sql = """
        INSERT INTO configuracoes (aba_nome, dados_json)
        VALUES (%s, %s)
        ON CONFLICT (aba_nome) DO UPDATE SET
            dados_json = EXCLUDED.dados_json;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (tab_name, dados_json))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração '{tab_name}': {e}")
        return False

@st.cache_data(ttl=600)
def carregar_usuarios_db():
    if not conn: return pd.DataFrame()
    try:
        return pd.read_sql_query("SELECT * FROM usuarios", conn)
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame()
        
# =========================================================================
# FUNÇÕES UTILITÁRIAS
# =========================================================================
def load_css():
    """Carrega o arquivo CSS para estilização."""
    css_path = "style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- FUNÇÃO ADICIONADA DE VOLTA ---
def clean_key(text):
    """Limpa um texto para ser usado como chave segura em widgets."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())
# --- FIM DA ADIÇÃO ---

def normalize_key(key):
    """Normaliza uma chave para o padrão do banco: minúsculo, sem acentos, com underscore."""
    k = str(key).lower().replace('ç', 'c').replace('ê', 'e').replace('é', 'e')
    k = k.replace('ã', 'a').replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    k = k.replace(' de ', ' ').replace(' ', '_')
    return ''.join(c for c in k if c.isalnum() or c == '_')

def sanitize_value(val):
    """Prepara valores para inserção segura no banco de dados."""
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    if isinstance(val, (int, float, bool, str, datetime, date)): return val
    try: return json.dumps(val)
    except Exception: return str(val)

def autenticar_direto(email):
    df = carregar_usuarios_db()
    if df.empty: return None
    user = df[df["email"].astype(str).str.lower() == str(email).lower()]
    return user.iloc[0]["nome"] if not user.empty else None

def get_status_color(status):
    s = (status or "").strip().lower()
    if 'finalizad' in s: return "#66BB6A" # Verde
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726" # Laranja
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5" # Cinza
    elif 'cancelad' in s: return "#EF5350" # Vermelho
    elif 'pausad' in s: return "#FFEE58" # Amarelo
    else: return "#64B5F6" # Azul

def calcular_sla(projeto_row, df_sla):
    data_agendamento = pd.to_datetime(projeto_row.get("Agendamento"), errors='coerce')
    data_finalizacao = pd.to_datetime(projeto_row.get("Data de Finalização"), errors='coerce')
    
    if pd.isna(data_agendamento):
        return "SLA: N/D (sem agendamento)", "gray"
    
    # Esta parte do código precisará ser revisada para funcionar com o df_sla carregado
    return "SLA: N/A", "gray" # Placeholder
