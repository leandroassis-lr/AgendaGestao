import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html
import psycopg2
from psycopg2 import sql
import io # Necessário para a exportação para Excel

# --- Conexão com o Banco de Dados (PostgreSQL) ---
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados PostgreSQL."""
    try:
        conn = psycopg2.connect(**st.secrets["postgres"])
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

conn = get_db_connection()

# --- Função de Criação de Tabelas ---
def criar_tabelas_iniciais():
    """Cria as tabelas se não existirem, adicionando as novas colunas 'analista' e 'gestor'."""
    if not conn: return
    try:
        with conn.cursor() as cur:
            # Tabela de Projetos
            cur.execute("""
            CREATE TABLE IF NOT EXISTS projetos (
                id SERIAL PRIMARY KEY,
                projeto TEXT,
                descricao TEXT,
                agencia TEXT,
                tecnico TEXT,
                status TEXT,
                agendamento DATE,
                data_abertura DATE,
                data_finalizacao DATE,
                observacao TEXT,
                demanda TEXT,
                log_agendamento TEXT,
                respostas_perguntas JSONB,
                etapas_concluidas TEXT,
                analista TEXT,
                gestor TEXT
            );
            """)
            # Adiciona colunas se não existirem (para compatibilidade com versões antigas)
            for col in ['analista', 'gestor']:
                cur.execute("""
                DO $$
                BEGIN
                    BEGIN
                        ALTER TABLE projetos ADD COLUMN %s TEXT;
                    EXCEPTION
                        WHEN duplicate_column THEN
                            -- A coluna já existe, não faz nada.
                    END;
                END;
                $$
                """, (sql.Identifier(col),))

            # Tabela de Configurações
            cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracoes (
                aba_nome TEXT PRIMARY KEY,
                dados_json JSONB
            );
            """)
            # Tabela de Usuários
            cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                nome TEXT,
                email TEXT UNIQUE,
                senha TEXT
            );
            """)
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabelas: {e}")

# --- Funções do Banco de Dados (Projetos) ---
@st.cache_data(ttl=60)
def carregar_projetos_db():
    """Carrega todos os projetos do banco de dados e renomeia as colunas para exibição."""
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM projetos ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
        # Renomeia as colunas para um formato mais amigável
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura',
            'data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento',
            'etapas_concluidas': 'Etapas Concluidas',
            # Capitaliza as outras para consistência
            'projeto': 'Projeto', 'status': 'Status', 'agendamento': 'Agendamento',
            'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor'
        }
        df.rename(columns=rename_map, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

# --- NOVA FUNÇÃO: Carregar projetos sem data ---
@st.cache_data(ttl=60)
def carregar_projetos_sem_agendamento_db():
    """Carrega apenas projetos sem data de agendamento (backlog)."""
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT * FROM projetos WHERE agendamento IS NULL ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura',
            'data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento',
            'etapas_concluidas': 'Etapas Concluidas',
            'projeto': 'Projeto', 'status': 'Status', 'agendamento': 'Agendamento',
            'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor'
        }
        df.rename(columns=rename_map, inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do backlog: {e}")
        return pd.DataFrame()


def adicionar_projeto_db(data: dict):
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cols = [key.lower() for key in data.keys()]
            vals = [data[key] for key in data.keys()]
            
            # Converte dicionários para JSONB se necessário
            for i, val in enumerate(vals):
                if isinstance(val, dict):
                    vals[i] = pd.io.json.dumps(val)

            insert_sql = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(
                sql.SQL(', ').join(map(sql.Identifier, cols)),
                sql.SQL(', ').join(sql.Placeholder() * len(vals))
            )
            cur.execute(insert_sql, vals)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar projeto: {e}")
        return False

def atualizar_projeto_db(project_id, updates: dict):
    if not conn: return False
    try:
        with conn.cursor() as cur:
            set_clauses = [sql.SQL("{} = %s").format(sql.Identifier(key.lower())) for key in updates.keys()]
            values = list(updates.values())
            
            # Converte dicionários para JSONB se necessário
            for i, val in enumerate(values):
                if isinstance(val, dict):
                    values[i] = pd.io.json.dumps(val)
            
            values.append(project_id)

            update_sql = sql.SQL("UPDATE projetos SET {} WHERE id = %s").format(
                sql.SQL(', ').join(set_clauses)
            )
            cur.execute(update_sql, values)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar projeto: {e}")
        return False

def excluir_projeto_db(project_id):
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir projeto: {e}")
        return False
        
# --- Funções do Banco (Configurações e Usuários) ---
@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT dados_json FROM configuracoes WHERE aba_nome = %s"
        df = pd.read_sql_query(query, conn, params=(tab_name.lower(),))
        if not df.empty and df['dados_json'][0]:
            return pd.DataFrame(df['dados_json'][0])
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def salvar_config_db(df, tab_name):
    if not conn: return False
    try:
        tab_name = tab_name.lower()
        dados_json = df.to_json(orient='records')
        
        sql_query = """
        INSERT INTO configuracoes (aba_nome, dados_json)
        VALUES (%s, %s)
        ON CONFLICT (aba_nome) DO UPDATE SET
            dados_json = EXCLUDED.dados_json;
        """
        with conn.cursor() as cur:
            cur.execute(sql_query, (tab_name, dados_json))
        
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração '{tab_name}': {e}")
        return False

# --- NOVA FUNÇÃO: Exportar para Excel ---
def dataframe_to_excel_bytes(df):
    """Converte um DataFrame para bytes de um arquivo Excel em memória."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Projetos')
    processed_data = output.getvalue()
    return processed_data

# --- Funções Utilitárias ---
def load_css():
    st.markdown("""
    <style>
        /* ... (seu CSS existente) ... */
        .main-title { font-size: 3em; font-weight: bold; text-align: center; color: #1E88E5; }
        .section-title-center { font-size: 2em; font-weight: bold; text-align: center; margin-bottom: 20px; }
        .project-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

def autenticar_direto(email):
    # Esta função pode ser melhorada para buscar no banco de dados de usuários
    return email 

def clean_key(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())

def get_status_color(status):
    s = str(status or "").strip().lower()
    if 'finalizad' in s: return "#66BB6A"
    elif 'pendencia' in s or 'pendência' in s: return "#FFA726"
    elif 'nao iniciad' in s or 'não iniciad' in s: return "#B0BEC5"
    elif 'cancelad' in s: return "#EF5350"
    elif 'pausad' in s: return "#FFEE58"
    else: return "#64B5F6"

def calcular_sla(projeto_row, df_sla):
    data_agendamento = pd.to_datetime(projeto_row.get("Agendamento"), errors='coerce')
    data_finalizacao = pd.to_datetime(projeto_row.get("Data de Finalização"), errors='coerce')
    
    if pd.isna(data_agendamento):
        return "SLA: N/D (sem agendamento)", "gray"
    
    # Lógica de cálculo do SLA (simplificada)
    prazo_dias = 30 # Prazo padrão
    if not df_sla.empty:
        # Aqui você implementaria a lógica para buscar o prazo correto no df_sla
        pass

    if pd.notna(data_finalizacao):
        dias_corridos = (data_finalizacao - data_agendamento).days
        if dias_corridos <= prazo_dias:
            return f"Finalizado no Prazo ({dias_corridos}d)", "#66BB6A"
        else:
            return f"Finalizado com Atraso ({dias_corridos - prazo_dias}d)", "#EF5350"
    else:
        dias_corridos = (datetime.now() - data_agendamento).days
        dias_restantes = prazo_dias - dias_corridos
        if dias_restantes < 0:
            return f"Atrasado em {-dias_restantes}d", "#EF5350"
        else:
            return f"SLA: {dias_restantes}d restantes", "#66BB6A"
