import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
import re
import html
from sqlalchemy import create_engine, text
import json

# --- CONFIGURAÇÕES GLOBAIS ---
# ESTAS VARIÁVEIS SÓ SÃO USADAS PELA LIMPEZA FINAL
# CONFIG_FILE = "config.xlsx"
# USUARIOS_FILE = "usuarios.xlsx"
# CONFIG_TABS_EXCEL = { ... }

# =========================================================================
# NOVA FUNÇÃO: Criação de Tabelas
# =========================================================================
def criar_tabelas_iniciais(engine):
    """
    Cria todas as tabelas necessárias (projetos, configuracoes, usuarios)
    se elas ainda não existirem.
    """
    with engine.connect() as conn:
        # Tabela Projetos (garantindo que ela exista, baseada nas suas funções)
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS projetos (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
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
        """))
        
        # Tabela Configuracoes (para substituir config.xlsx)
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            aba_nome TEXT PRIMARY KEY,
            dados_json TEXT
        );
        """))
        
        # Tabela Usuarios (para substituir usuarios.xlsx)
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Nome TEXT,
            Email TEXT UNIQUE,
            Senha TEXT
        );
        """))
        conn.commit()

# =========================================================================
# FUNÇÃO DE CONEXÃO (Modificada)
# =========================================================================
@st.cache_resource
def get_engine():
    try:
        db_url_value = st.secrets["db_url"]
        db_token_value = st.secrets["db_token"]
        if db_url_value.startswith("libsql://"):
            db_url_value = db_url_value[9:]
        connection_url = f"sqlite+libsql://{db_url_value}/?secure=true"
        engine = create_engine(
            connection_url,
            connect_args={
                "auth_token": db_token_value,
                "check_same_thread": False
            }
        )
        
        # *** ADIÇÃO IMPORTANTE ***
        # Garante que as tabelas existam antes de continuar
        criar_tabelas_iniciais(engine)
        
        return engine
    except KeyError as e:
        st.error(f"Erro Crítico: A credencial {e} não foi encontrada nos 'Secrets' do Streamlit.")
        st.info("Por favor, adicione 'db_url' e 'db_token' (minúsculos) aos Secrets do seu app.")
        return None
    except Exception as e:
        # Mensagem de erro atualizada
        st.error(f"Erro ao conectar ao banco ou criar tabelas: {e}") 
        return None

# =========================================================================
# FUNÇÕES DO BANCO DE DADOS (PROJETOS)
# =========================================================================

@st.cache_data(ttl=60)
def carregar_projetos_db():
    """Carrega todos os projetos do banco de dados Turso."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame() # Retorna um DF vazio se a conexão falhar

    try:
        query = "SELECT * FROM projetos ORDER BY ID DESC"
        
        with engine.connect() as conn:
            df = pd.read_sql_query(
                sql=text(query),
                con=conn,
                parse_dates={"Agendamento": {"errors": "coerce"},
                             "Data_Abertura": {"errors": "coerce"},
                             "Data_Finalizacao": {"errors": "coerce"}}
            )
        
        # Esta função renomeia as colunas do DB (ex: Data_Abertura)
        # para nomes amigáveis (ex: Data de Abertura)
        df.rename(columns={
            'Descricao': 'Descrição', 'Agencia': 'Agência', 'Tecnico': 'Técnico',
            'Observacao': 'Observação', 'Data_Abertura': 'Data de Abertura',
            'Data_Finalizacao': 'Data de Finalização', 'Log_Agendamento': 'Log Agendamento',
            'Etapas_Concluidas': 'Etapas Concluidas'
        }, inplace=True)
        return df
        
    except Exception as e:
        if "no such table" in str(e):
            st.error(f"Erro: A tabela 'projetos' não foi encontrada no Turso. "
                     f"Verifique se as tabelas foram criadas corretamente.")
        else:
            st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

# Função para aplicar CSS customizado (Inalterada)
def load_css():
    css_path = "style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""<style>
        .stButton>button {
            border-radius: 5px;
        }
        </style>""", unsafe_allow_html=True)

# Função sanitize_value (Inalterada)
def sanitize_value(val):
    if val is None:
        return None
    if isinstance(val, (int, float, bool)):
        return val
    if isinstance(val, (date, datetime)):
        return val
    if isinstance(val, str):
        return val
    try:
        return json.dumps(val)
    except Exception:
        return str(val)

# Função atualizar_projeto_db (CORRIGIDA)
def atualizar_projeto_db(project_id, updates: dict):
    engine = get_engine()
    if engine is None:
        return False
    try:
        # --- CORREÇÃO AQUI ---
        # Remove ' de ' ANTES de substituir espaços por '_'
        updates_sanitized = {
            key.replace(' de ', ' ').replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('é', 'e').replace('ã', 'a'): val
            for key, val in updates.items()
        }
        # Agora 'Data de Abertura' vira 'Data Abertura' e depois 'Data_Abertura' (Correto!)
        # --- FIM DA CORREÇÃO ---

        set_clause = ", ".join([f'"{k}" = :{k}' for k in updates_sanitized.keys()])
        sql = f'UPDATE projetos SET {set_clause} WHERE ID = :project_id'
        params = updates_sanitized.copy()
        params['project_id'] = project_id
        sql_stmt = text(sql)
        with engine.connect() as conn:
            conn.execute(sql_stmt, params)
            conn.commit()
        st.cache_data.clear()
        st.toast("Projeto atualizado com sucesso!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥")
        return False

# Função adicionar_projeto_db (CORRIGIDA)
def adicionar_projeto_db(data: dict):
    engine = get_engine()
    if engine is None:
        return False
    try:
        # --- CORREÇÃO AQUI ---
        # Remove ' de ' ANTES de substituir espaços por '_'
        db_data_raw = {
            key.replace(' de ', ' ').replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in data.items()
        }
        # --- FIM DA CORREÇÃO ---

        db_data = {k: sanitize_value(v) for k, v in db_data_raw.items()}
        cols_str = ', '.join([f'"{c}"' for c in db_data.keys()])
        placeholders = ', '.join([f":{c}" for c in db_data.keys()])
        sql = f"INSERT INTO projetos ({cols_str}) VALUES ({placeholders})"
        sql_stmt = text(sql)
        with engine.connect() as conn:
            conn.execute(sql_stmt, parameters=db_data)
            conn.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥")
        return False

# Função excluir_projeto_db (Inalterada)
def excluir_projeto_db(project_id):
    engine = get_engine()
    if engine is None:
        return False
    try:
        sql = 'DELETE FROM projetos WHERE ID = ?'
        with engine.connect() as conn:
            conn.execute(text(sql), (project_id,))
            conn.commit()
        st.cache_data.clear()
        st.toast("Projeto excluído!", icon="✅")
        return True
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥")
        return False

# =========================================================================
# NOVAS FUNÇÕES (CONFIGURAÇÕES - via DB)
# =========================================================================

@st.cache_data(ttl=600) # Cache de 10 minutos
def carregar_config_db(tab_name):
    """Carrega uma 'aba' de configuração do banco de dados Turso."""
    engine = get_engine()
    if engine is None: return pd.DataFrame()
    try:
        query = text("SELECT dados_json FROM configuracoes WHERE aba_nome = :aba")
        with engine.connect() as conn:
            result = conn.execute(query, {"aba": tab_name}).fetchone()
        
        if result and result[0]:
            # Carrega o DataFrame a partir do JSON salvo
            df = pd.read_json(result[0], orient='records')
            return df.astype(str).replace('nan', '')
        else:
            # Se não houver, retorna um DF vazio
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Erro ao carregar configuração '{tab_name}' do DB: {e}")
        return pd.DataFrame()

def salvar_config_db(df, tab_name):
    """Salva um DataFrame de configuração como JSON no banco de dados."""
    engine = get_engine()
    if engine is None: return False
    try:
        # Converte o DataFrame para JSON
        dados_json = df.to_json(orient='records')
        
        # Usa REPLACE (INSERT OR REPLACE) para atualizar ou inserir
        query = text("""
        REPLACE INTO configuracoes (aba_nome, dados_json) 
        VALUES (:aba, :json)
        """)
        
        with engine.connect() as conn:
            conn.execute(query, {"aba": tab_name, "json": dados_json})
            conn.commit()
        
        st.cache_data.clear() # Limpa todo o cache para recarregar
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração '{tab_name}' no DB: {e}")
        return False

# =========================================================================
# NOVAS FUNÇÕES (USUÁRIOS - via DB)
# =========================================================================

@st.cache_data(ttl=600)
def carregar_usuarios_db():
    """Carrega os usuários do banco de dados Turso."""
    engine = get_engine()
    if engine is None: return pd.DataFrame(columns=["Nome", "Email", "Senha"])
    try:
        query = "SELECT * FROM usuarios"
        with engine.connect() as conn:
            df = pd.read_sql_query(text(query), con=conn)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar usuários do DB: {e}")
        return pd.DataFrame(columns=["Nome", "Email", "Senha"])

def salvar_usuario_db(df):
    """Salva o DataFrame de usuários no banco de dados (SOBRESCRITA)."""
    engine = get_engine()
    if engine is None: return False
    try:
        df_to_save = df.copy()
        
        if 'E-mail' in df_to_save.columns:
            df_to_save.rename(columns={'E-mail': 'Email'}, inplace=True)
        
        colunas_tabela = ['Nome', 'Email', 'Senha']
        
        # Filtra o DataFrame para ter apenas as colunas que a tabela aceita
        # (Ignora colunas extras como 'ID' se vierem do Excel)
        colunas_presentes = [col for col in colunas_tabela if col in df_to_save.columns]
        df_final = df_to_save[colunas_presentes]

        with engine.connect() as conn:
            conn.execute(text("DELETE FROM usuarios"))
            
            if not df_final.empty:
                df_final.to_sql('usuarios', con=conn, if_exists='append', index=False)
                
            conn.commit()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar usuários no DB: {e}") 
        return False

# =========================================================================
# FUNÇÕES ANTIGAS (EXCEL - Removidas ou para remover)
# (Mantenha se você ainda não fez a limpeza final)
# =========================================================================

# @st.cache_data(ttl=3600)
# def _carregar_config_excel(tab_name): ...
# def _carregar_usuarios_excel(): ...


# =========================================================================
# FUNÇÕES UTILITÁRIAS (Modificadas ou Inalteradas)
# =========================================================================

def autenticar_direto(email):
    """Autentica o usuário usando o banco de dados."""
    df = carregar_usuarios_db() # <-- MUDANÇA
    user = df[df["Email"].astype(str).str.lower() == str(email).lower()]
    if not user.empty:
        return user.iloc[0]["Nome"]
    else:
        return None

def clean_key(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())

def get_status_color(status):
    s = (status or "").strip().lower()
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
        return "#64B5F6"

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
