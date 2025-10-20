import streamlit as st
import pandas as pd
import psycopg2
import psycopg2.extras # Usado para inserções em massa
import os
from datetime import date, datetime
import re
import json
import math

# =========================================================================
# FUNÇÃO DE CONEXÃO (NOVA - POSTGRESQL)
# =========================================================================
@st.cache_resource
def get_db_connection():
    """
    Estabelece uma conexão com o banco de dados PostgreSQL no Railway.
    Usa o cache de recursos do Streamlit para manter a conexão viva.
    Também garante que as tabelas iniciais existam.
    """
    try:
        # Constrói a string de conexão a partir dos segredos
        conn_string = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=st.secrets["postgres"]["PGUSER"],
            password=st.secrets["postgres"]["PGPASSWORD"],
            host=st.secrets["postgres"]["PGHOST"],
            port=st.secrets["postgres"]["PGPORT"],
            db=st.secrets["postgres"]["PGDATABASE"]
        )
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True # Essencial para que os comandos sejam salvos sem conn.commit()
        
        # Garante que as tabelas existam antes de continuar
        criar_tabelas_iniciais(conn)
        
        return conn
    except KeyError as e:
        st.error(f"Erro Crítico: A credencial 'postgres.{e}' não foi encontrada nos 'Secrets' do Streamlit.")
        st.info("Por favor, adicione a seção [postgres] com todas as credenciais do Railway (PGHOST, PGUSER, etc).")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados PostgreSQL: {e}")
        st.stop()

# =========================================================================
# CRIAÇÃO DE TABELAS (NOVA - POSTGRESQL)
# =========================================================================
def criar_tabelas_iniciais(conn):
    """
    Cria as tabelas necessárias (projetos, configuracoes, usuarios)
    com a sintaxe correta para PostgreSQL se elas não existirem.
    """
    with conn.cursor() as cur:
        # Tabela Projetos: `SERIAL PRIMARY KEY` é o autoincremento do PostgreSQL
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            ID SERIAL PRIMARY KEY,
            Projeto TEXT,
            Descricao TEXT,
            Agencia TEXT,
            Tecnico TEXT,
            Status TEXT,
            Agendamento TEXT,
            Data_Abertura TEXT,
            Data_Finalizacao TEXT,
            Observacao TEXT,
            Demanda TEXT,
            Log_Agendamento TEXT,
            Respostas_Perguntas TEXT,
            Etapas_Concluidas TEXT
        );
        """)
        
        # Tabela Configuracoes
        cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            aba_nome TEXT PRIMARY KEY,
            dados_json TEXT
        );
        """)
        
        # Tabela Usuarios
        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            ID SERIAL PRIMARY KEY,
            Nome TEXT,
            Email TEXT UNIQUE,
            Senha TEXT
        );
        """)

# =========================================================================
# FUNÇÕES DO BANCO DE DADOS (PROJETOS - ADAPTADAS)
# =========================================================================

@st.cache_data(ttl=60)
def carregar_projetos_db():
    conn = get_db_connection()
    try:
        query = "SELECT * FROM projetos ORDER BY ID DESC"
        # O Pandas lê a conexão psycopg2 diretamente, é muito prático
        df = pd.read_sql_query(
            sql=query, con=conn,
            parse_dates={"Agendamento": {"errors": "coerce"},
                         "Data_Abertura": {"errors": "coerce"},
                         "Data_Finalizacao": {"errors": "coerce"}}
        )
        # Renomeia colunas para exibição (sem alterações aqui)
        df.rename(columns={
            'Descricao': 'Descrição', 'Agencia': 'Agência', 'Tecnico': 'Técnico',
            'Observacao': 'Observação', 'Data_Abertura': 'Data de Abertura',
            'Data_Finalizacao': 'Data de Finalização', 'Log_Agendamento': 'Log Agendamento',
            'Etapas_Concluidas': 'Etapas Concluidas'
        }, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

def adicionar_projeto_db(data: dict):
    conn = get_db_connection()
    try:
        db_data_normalized = {normalize_key(key): value for key, value in data.items()}
        db_data = {k: sanitize_value(v) for k, v in db_data_normalized.items()}
        
        cols_str = ', '.join([f'"{c}"' for c in db_data.keys()])
        # Placeholders para psycopg2 são %s, não :key
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
    conn = get_db_connection()
    try:
        updates_normalized = {normalize_key(key): val for key, val in updates.items()}
        updates_final = {k: sanitize_value(v) for k, v in updates_normalized.items()}
        
        # Placeholders para psycopg2 são %s
        set_clause = ", ".join([f'"{k}" = %s' for k in updates_final.keys()])
        sql = f'UPDATE projetos SET {set_clause} WHERE ID = %s'
        
        # A lista de valores deve estar na ordem correta, terminando com o ID
        params = list(updates_final.values()) + [project_id]
        
        with conn.cursor() as cur:
            cur.execute(sql, params)
        
        st.cache_data.clear()
        st.toast("Projeto atualizado com sucesso!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥")
        return False

def excluir_projeto_db(project_id):
    conn = get_db_connection()
    try:
        # Placeholder para psycopg2 é %s
        sql = 'DELETE FROM projetos WHERE ID = %s'
        with conn.cursor() as cur:
            cur.execute(sql, (project_id,)) # Passa os parâmetros como uma tupla
        
        st.cache_data.clear()
        st.toast("Projeto excluído!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥")
        return False

# =========================================================================
# FUNÇÕES DE CONFIG E USUÁRIOS (ADAPTADAS)
# =========================================================================

@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    conn = get_db_connection()
    try:
        # Usando %s como placeholder
        query = "SELECT dados_json FROM configuracoes WHERE aba_nome = %s"
        df_json = pd.read_sql_query(query, conn, params=(tab_name,))
        
        if not df_json.empty and df_json.iloc[0]['dados_json']:
            df = pd.read_json(df_json.iloc[0]['dados_json'], orient='records')
            return df.astype(str).replace('nan', '')
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar configuração '{tab_name}' do DB: {e}")
        return pd.DataFrame()

def salvar_config_db(df, tab_name):
    conn = get_db_connection()
    try:
        dados_json = df.to_json(orient='records')
        # `REPLACE INTO` não existe no PG. Usamos a sintaxe `ON CONFLICT ... DO UPDATE`
        query = """
        INSERT INTO configuracoes (aba_nome, dados_json)
        VALUES (%s, %s)
        ON CONFLICT (aba_nome) DO UPDATE SET
            dados_json = EXCLUDED.dados_json;
        """
        with conn.cursor() as cur:
            cur.execute(query, (tab_name, dados_json))
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração '{tab_name}' no DB: {e}")
        return False

@st.cache_data(ttl=600)
def carregar_usuarios_db():
    conn = get_db_connection()
    try:
        query = "SELECT * FROM usuarios"
        df = pd.read_sql_query(query, con=conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar usuários do DB: {e}")
        return pd.DataFrame(columns=["Nome", "Email", "Senha"])

def salvar_usuario_db(df):
    conn = get_db_connection()
    try:
        df_to_save = df.copy()
        if 'E-mail' in df_to_save.columns:
            df_to_save.rename(columns={'E-mail': 'Email'}, inplace=True)
            
        colunas_tabela = ['Nome', 'Email', 'Senha']
        df_final = df_to_save[[col for col in colunas_tabela if col in df_to_save.columns]]

        with conn.cursor() as cur:
            # Limpa a tabela antes de inserir tudo de novo (mantendo sua lógica original)
            cur.execute("DELETE FROM usuarios")
            
            # Insere todos os dados do DataFrame de uma vez (muito mais eficiente)
            if not df_final.empty:
                # Transforma o dataframe em uma lista de tuplas
                tuples = [tuple(x) for x in df_final.to_numpy()]
                # Cria a string de colunas
                cols = ','.join([f'"{col}"' for col in df_final.columns])
                # Usa a função `execute_values` para uma inserção rápida
                psycopg2.extras.execute_values(
                    cur,
                    f"INSERT INTO usuarios ({cols}) VALUES %s",
                    tuples
                )
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar usuários no DB: {e}")
        return False
        
# =========================================================================
# FUNÇÕES UTILITÁRIAS (Sem alterações, já estavam perfeitas)
# =========================================================================

def load_css():
    css_path = "style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""<style> .stButton>button { border-radius: 5px; } </style>""", unsafe_allow_html=True)

def sanitize_value(val):
    if val is None: return None
    if isinstance(val, float) and math.isnan(val): return None
    if isinstance(val, (int, float, bool)): return val
    if isinstance(val, datetime): return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, date): return val.strftime('%Y-%m-%d')
    if isinstance(val, str): return val
    try: return json.dumps(val)
    except Exception: return str(val)

def normalize_key(key):
    k = str(key).lower()
    k = k.replace('ç', 'c').replace('ê', 'e').replace('é', 'e').replace('ã', 'a')
    k = k.replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    k = k.replace(' de ', ' ')
    k = k.replace(' ', '_')
    if k == 'data_abertura': return 'Data_Abertura'
    if k == 'data_finalizacao': return 'Data_Finalizacao'
    if k == 'log_agendamento': return 'Log_Agendamento'
    if k == 'etapas_concluidas': return 'Etapas_Concluidas'
    if k == 'respostas_perguntas': return 'Respostas_Perguntas'
    return k.capitalize()

def autenticar_direto(email):
    df = carregar_usuarios_db()
    if df.empty: return None
    user = df[df["Email"].astype(str).str.lower() == str(email).lower()]
    if not user.empty:
        return user.iloc[0]["Nome"]
    else:
        return None

def get_status_color(status):
    s = (status or "").strip().lower()
    if 'finalizad' in s: return "#66BB6A"
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726"
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5"
    elif 'cancelad' in s: return "#EF5350"
    elif 'pausad' in s: return "#FFEE58"
    else: return "#64B5F6"

def calcular_sla(projeto_row, df_sla):
    data_agendamento = pd.to_datetime(projeto_row.get("Agendamento"), errors='coerce')
    data_finalizacao = pd.to_datetime(projeto_row.get("Data de Finalização"), errors='coerce')
    projeto_nome = projeto_row.get("Projeto", "")
    demanda = projeto_row.get("Demanda", "")
    if pd.isna(data_agendamento):
        return "SLA: N/D (sem agendamento)", "gray"
    if df_sla.empty:
        return "SLA: N/A (Regras não carregadas)", "gray"
    rule = df_sla[(df_sla["Nome do Projeto"] == projeto_nome) & (df_sla["Demanda"] == demanda)]
    if rule.empty:
        rule = df_sla[(df_sla["Nome do Projeto"] == projeto_nome) & (df_sla["Demanda"].astype(str).isin(['', 'nan']))]
    if rule.empty:
        return "SLA: N/A", "gray"
    try:
        prazo_dias = int(rule.iloc[0]["Prazo (dias)"])
    except (ValueError, TypeError):
        return "SLA: Inválido", "red"
    start_date = data_agendamento.date()
    if pd.notna(data_finalizacao):
        end_date = data_finalizacao.date()
        dias_corridos = (end_date - start_date).days
        if dias_corridos <= prazo_dias:
            return f"Finalizado no Prazo ({dias_corridos}d)", "#66BB6A"
        else:
            atraso = dias_corridos - prazo_dias
            return f"Finalizado com Atraso ({atraso}d)", "#EF5350"
    else:
        end_date = date.today()
        dias_corridos = (end_date - start_date).days
        dias_restantes = prazo_dias - dias_corridos
        if dias_restantes < 0:
            return f"Atrasado em {-dias_restantes}d", "#EF5350"
        elif dias_restantes == 0:
            return "SLA Vence Hoje!", "#FFA726"
        else:
            return f"SLA: {dias_restantes}d restantes", "#66BB6F"
