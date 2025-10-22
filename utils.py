import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html
import psycopg2
from psycopg2 import sql
import io

# --- Conexão com o Banco de Dados (PostgreSQL) ---
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados PostgreSQL."""
    try:
        secrets = st.secrets["postgres"]
        conn = psycopg2.connect(
            host=secrets["PGHOST"],
            port=secrets["PGPORT"],
            user=secrets["PGUSER"],
            password=secrets["PGPASSWORD"],
            dbname=secrets["PGDATABASE"]
        )
        conn.autocommit = True
        return conn
    except KeyError as e:
        st.error(f"Erro Crítico: A credencial '{e}' não foi encontrada na seção [postgres] dos 'Secrets'.")
        return None
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None


conn = get_db_connection()


# --- Função de Criação de Tabelas ---
def criar_tabelas_iniciais():
    """Cria as tabelas se não existirem."""
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projetos (
                    id SERIAL PRIMARY KEY,
                    projeto TEXT, descricao TEXT, agencia TEXT, tecnico TEXT, status TEXT,
                    agendamento DATE, data_abertura DATE, data_finalizacao DATE,
                    observacao TEXT, demanda TEXT, log_agendamento TEXT,
                    respostas_perguntas JSONB, etapas_concluidas TEXT,
                    analista TEXT, gestor TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    aba_nome TEXT PRIMARY KEY, dados_json JSONB
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, senha TEXT
                );
            """)
    except Exception as e:
        st.error(f"Erro ao criar/verificar tabelas: {e}")


# --- Funções do Banco (Projetos) ---
def _normalize_and_sanitize(data_dict: dict):
    normalized = {}
    for key, value in data_dict.items():
        k = str(key).lower()
        k = re.sub(r'[çÇ]', 'c', k)
        k = re.sub(r'[êé]', 'e', k)
        k = re.sub(r'[ãá]', 'a', k)
        k = re.sub(r'[í]', 'i', k)
        k = re.sub(r'[ó]', 'o', k)
        k = re.sub(r'[ú]', 'u', k)
        k = k.replace(' de ', ' ').replace(' ', '_')

        if value is None or (isinstance(value, float) and pd.isna(value)):
            sanitized_value = None
        elif isinstance(value, (datetime, date)):
            sanitized_value = value.strftime('%Y-%m-%d')
        else:
            sanitized_value = str(value)

        normalized[k] = sanitized_value
    return normalized


@st.cache_data(ttl=60)
def carregar_projetos_db():
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM projetos ORDER BY id DESC", conn)
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura',
            'data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento',
            'etapas_concluidas': 'Etapas Concluidas', 'projeto': 'Projeto', 'status': 'Status',
            'agendamento': 'Agendamento', 'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor'
        }
        df = df.rename(columns=rename_map)

        if 'Agendamento' in df.columns:
            df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y')
            df['Agendamento_str'] = df['Agendamento_str'].fillna("N/A")

        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def carregar_projetos_sem_agendamento_db():
    if not conn:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM projetos WHERE agendamento IS NULL ORDER BY id DESC", conn)
        rename_map = {
            'id': 'ID', 'descricao': 'Descrição', 'agencia': 'Agência', 'tecnico': 'Técnico',
            'observacao': 'Observação', 'data_abertura': 'Data de Abertura',
            'data_finalizacao': 'Data de Finalização', 'log_agendamento': 'Log Agendamento',
            'etapas_concluidas': 'Etapas Concluidas', 'projeto': 'Projeto', 'status': 'Status',
            'agendamento': 'Agendamento', 'demanda': 'Demanda', 'analista': 'Analista', 'gestor': 'Gestor'
        }
        df = df.rename(columns=rename_map)
        if 'Agendamento' in df.columns:
            df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime('%d/%m/%Y')
            df['Agendamento_str'] = df['Agendamento_str'].fillna("N/A")
        return df
    except Exception as e:
        st.error(f"Erro ao carregar projetos do backlog: {e}")
        return pd.DataFrame()


def adicionar_projeto_db(data: dict):
    if not conn:
        return False
    try:
        db_data = _normalize_and_sanitize(data)
        cols = db_data.keys()
        vals = list(db_data.values())
        query = sql.SQL("INSERT INTO projetos ({}) VALUES ({})").format(
            sql.SQL(', ').join(map(sql.Identifier, cols)),
            sql.SQL(', ').join(sql.Placeholder() * len(cols))
        )
        with conn.cursor() as cur:
            cur.execute(query, vals)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥")
        return False


def atualizar_projeto_db(project_id, updates: dict):
    if not conn:
        return False
    try:
        db_data = _normalize_and_sanitize(updates)
        set_clause = sql.SQL(', ').join(
            sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in db_data.keys()
        )
        query = sql.SQL("UPDATE projetos SET {} WHERE id = {}").format(set_clause, sql.Placeholder())
        vals = list(db_data.values()) + [project_id]
        with conn.cursor() as cur:
            cur.execute(query, vals)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥")
        return False


def excluir_projeto_db(project_id):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM projetos WHERE id = %s", (project_id,))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥")
        return False


# --- Funções do Banco (Configurações e Usuários) ---
@st.cache_data(ttl=600)
def carregar_config_db(tab_name):
    if not conn:
        return pd.DataFrame()
    try:
        query = "SELECT dados_json FROM configuracoes WHERE aba_nome = %s"
        with conn.cursor() as cur:
            cur.execute(query, (tab_name.lower(),))
            result = cur.fetchone()

        if result is None or result[0] is None:
            return pd.DataFrame()

        data = result[0]
        if isinstance(data, str):
            return pd.read_json(data, orient='records')
        elif isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro detalhado ao carregar configuração '{tab_name}': {e}")
        return pd.DataFrame()


def salvar_config_db(df, tab_name):
    if not conn:
        return False
    try:
        dados_json = df.to_json(orient='records')
        sql_query = """
            INSERT INTO configuracoes (aba_nome, dados_json) VALUES (%s, %s)
            ON CONFLICT (aba_nome) DO UPDATE SET dados_json = EXCLUDED.dados_json;
        """
        with conn.cursor() as cur:
            cur.execute(sql_query, (tab_name.lower(), dados_json))
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração '{tab_name}': {e}")
        return False


@st.cache_data(ttl=600)
def carregar_usuarios_db():
    if not conn:
        return pd.DataFrame()
    try:
        return pd.read_sql_query("SELECT id, nome, email, senha FROM usuarios", conn)
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame()


def salvar_usuario_db(df):
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios")
            if not df.empty:
                for _, row in df.iterrows():
                    cur.execute(
                        "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
                        (row.get('Nome'), row.get('Email'), row.get('Senha'))
                    )
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar usuários: {e}")
        return False


# --- Funções de Importação/Exportação ---
def generate_excel_template_bytes():
    template_columns = ["Projeto", "Descrição", "Agência", "Técnico", "Demanda", "Observação", "Analista", "Gestor"]
    df_template = pd.DataFrame(columns=template_columns)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()


def bulk_insert_projetos_db(df: pd.DataFrame, usuario_logado: str):
    if not conn:
        return False, 0
    column_map = {
        'Projeto': 'projeto', 'Descrição': 'descricao', 'Agência': 'agencia', 'Técnico': 'tecnico',
        'Demanda': 'demanda', 'Observação': 'observacao', 'Analista': 'analista', 'Gestor': 'gestor'
    }
    if 'Projeto' not in df.columns:
        st.error("Erro: A planilha enviada não contém a coluna obrigatória 'Projeto'.")
        return False, 0

    df_to_insert = df.rename(columns=column_map)
    df_to_insert['status'] = 'NÃO INICIADA'
    df_to_insert['data_abertura'] = date.today()
    if 'analista' in df_to_insert:
        df_to_insert['analista'] = df_to_insert['analista'].fillna(usuario_logado)
    else:
        df_to_insert['analista'] = usuario_logado

    cols_to_insert = ['projeto', 'descricao', 'agencia', 'tecnico', 'status',
                      'data_abertura', 'observacao', 'demanda', 'analista', 'gestor']
    df_final = df_to_insert[[col for col in cols_to_insert if col in df_to_insert.columns]]
    values = [tuple(x) for x in df_final.to_numpy()]
    cols_sql = ", ".join(df_final.columns)
    placeholders = ", ".join(["%s"] * len(df_final.columns))
    query = f"INSERT INTO projetos ({cols_sql}) VALUES ({placeholders})"

    try:
        with conn.cursor() as cur:
            cur.executemany(query, values)
        st.cache_data.clear()
        return True, len(values)
    except Exception as e:
        st.error(f"Erro ao inserir dados em lote: {e}")
        return False, 0


def dataframe_to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_to_export = df.copy()
        if 'Agendamento_str' in df_to_export.columns:
            df_to_export.drop(columns=['Agendamento_str'], inplace=True)
        df_to_export.to_excel(writer, index=False, sheet_name='Projetos')
    return output.getvalue()


# --- Funções Utilitárias ---
def load_css():
    st.markdown("""
        <style>
        .main-title { font-size: 3em; font-weight: bold; text-align: center; color: #1E88E5; }
        .section-title-center { font-size: 2em; font-weight: bold; text-align: center; margin-bottom: 20px; }
        .project-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px;
                        margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        </style>
    """, unsafe_allow_html=True)


def autenticar_direto(email):
    df_users = carregar_usuarios_db()
    if not df_users.empty and 'email' in df_users.columns:
        user = df_users[df_users["email"].astype(str).str.lower() == str(email).lower()]
        if not user.empty:
            return user.iloc[0]["nome"]
    return None


def clean_key(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())


def get_status_color(status):
    s = str(status or "").strip().lower()
    if 'finalizad' in s:
        return "#66BB6A"
    elif 'pendencia' in s or 'pendência' in s:
        return "#FFA726"
    elif 'nao iniciad' in s or 'não iniciad' in s:
        return "#B0BEC5"
    elif 'cancelad' in s:
        return "#EF5350"
    elif 'pausad' in s:
        return "#FFEE58"
    else:
        return "#64B5F6"  # Em Andamento


def calcular_sla(projeto_row, df_sla):
    data_agendamento = pd.to_datetime(projeto_row.get("Agendamento"), errors='coerce')
    data_finalizacao = pd.to_datetime(projeto_row.get("Data de Finalização"), errors='coerce')

    projeto_nome = str(projeto_row.get("Projeto", "")).upper()
    demanda = projeto_row.get("Demanda", "")

    if pd.isna(data_agendamento):
        return "SLA: N/D (sem agendamento)", "gray"

    if df_sla.empty:
        return "SLA: N/A (Regras não carregadas)", "gray"

    df_sla_upper = df_sla.copy()
    df_sla_upper["Nome do Projeto"] = df_sla_upper["Nome do Projeto"].astype(str).str.upper()

    rule = df_sla_upper[
        (df_sla_upper["Nome do Projeto"] == projeto_nome) &
        (df_sla_upper["Demanda"] == demanda)
    ]

    if rule.empty:
        rule = df_sla_upper[
            (df_sla_upper["Nome do Projeto"] == projeto_nome) &
            (df_sla_upper["Demanda"].astype(str).isin(['', 'nan', 'None']))
        ]

    if rule.empty:
        return "SLA: N/A (Regra não encontrada)", "gray"

    try:
        prazo_raw = rule.iloc[0]["Prazo (dias)"]
        if pd.isna(prazo_raw):
            prazo_raw = rule.iloc[0, -1]
            if pd.isna(prazo_raw):
                return "SLA: Prazo N/D", "gray"
        prazo_dias = int(prazo_raw)
    except (ValueError, TypeError, IndexError):
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
