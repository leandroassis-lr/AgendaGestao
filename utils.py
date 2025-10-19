import streamlit as st
import pandas as pd
import os
# import sqlite3  # Removido (Correto)
from datetime import date
import re
import html
from sqlalchemy import create_engine, text # Importar 'create_engine'

# --- CONFIGURAÇÕES GLOIS ---
# DB_FILE = "gestao_projetos.db"  # Removido (Correto)
CONFIG_FILE = "config.xlsx"
USUARIOS_FILE = "usuarios.xlsx"
CONFIG_TABS = {
    "status": ["Status"], "agencias": ["Agência"], "projetos_nomes": ["Nome do Projeto"],
    "tecnicos": ["Técnico"], "sla": ["Nome do Projeto", "Demanda", "Prazo (dias)"],
    "perguntas": ["Pergunta", "Tipo (texto, numero, data)"],
    "etapas_evolucao": ["Nome do Projeto", "Etapa"]
}

# =========================================================================
# SEÇÃO DE CONEXÃO (CORRIGIDA PARA CONEXÃO SEGURA)
# =========================================================================

@st.cache_resource  # Usamos cache_resource para o "motor" da conexão
def get_engine():
    """
    Cria e retorna uma conexão (engine) SQLAlchemy para o Turso.
    Esta função usa os "Secrets" do Streamlit.
    """
    try:
        # 1. Puxa as credenciais com NOMES SIMPLES
        db_url_value = st.secrets["db_url"]
        db_token_value = st.secrets["db_token"]
        
        # 2. VERIFICA se o usuário colocou "libsql://" por engano no secret
        if db_url_value.startswith("libsql://"):
            db_url_value = db_url_value[9:] # Remove o prefixo
            
        # 3. Monta a URL de conexão CORRETA
        #    A MUDANÇA ESTÁ AQUI: Adicionamos "/?secure=true"
        #    Isso força o driver a usar uma conexão segura (WSS/HTTPS)
        connection_url = f"sqlite+libsql://{db_url_value}/?secure=true"
        
        # 4. Cria o "motor" (engine) da conexão
        engine = create_engine(
            connection_url, 
            connect_args={
                "auth_token": db_token_value,
                "check_same_thread": False # OBRIGATÓRIO para Streamlit
            }
        )
        return engine
    
    except KeyError as e:
        # Esta mensagem de erro agora mostrará a nova chave se falhar
        st.error(f"Erro Crítico: A credencial {e} não foi encontrada nos 'Secrets' do Streamlit.")
        st.info("Por favor, adicione 'db_url' e 'db_token' (minúsculos) aos Secrets do seu app.")
        return None
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# =========================================================================
# FUNÇÕES DO BANCO DE DADOS (Inalteradas)
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

def atualizar_projeto_db(project_id, updates: dict):
    """Atualiza um projeto no banco com base no ID."""
    engine = get_engine()
    if engine is None:
        return False
        
    try:
        db_updates = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in updates.items()
        }
        
        set_clause = ", ".join([f'"{key}" = ?' for key in db_updates.keys()])
        sql = f"UPDATE projetos SET {set_clause} WHERE ID = ?"
        values = list(db_updates.values()) + [project_id]

        with engine.connect() as conn:
            conn.execute(text(sql), values)
            conn.commit()
            
        st.cache_data.clear()
        return True
        
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥")
        return False

def adicionar_projeto_db(data: dict):
    """Adiciona um novo projeto ao banco usando placeholders posicionais."""
    engine = get_engine()
    if engine is None:
        return False

    try:
        # Normaliza os nomes das colunas para o banco
        db_data = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in data.items()
        }

        cols_str = ', '.join([f'"{c}"' for c in db_data.keys()])
        placeholders = ', '.join(['?' for _ in db_data])
        sql = f"INSERT INTO projetos ({cols_str}) VALUES ({placeholders})"
        values = tuple(db_data.values())  # Tupla é o formato aceito

        with engine.connect() as conn:
            conn.execute(text(sql), values)
            conn.commit()

        st.cache_data.clear()
        return True

    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥")
        return False        
def excluir_projeto_db(project_id):
    """Exclui um projeto do banco com base no ID."""
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
# O RESTO DO SEU ARQUIVO UTILS.PY (INTACTO)
# =========================================================================

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

@st.cache_data(ttl=3600)
def carregar_config(tab_name):
    cols = CONFIG_TABS.get(tab_name, [])
    if os.path.exists(CONFIG_FILE):
        try:
            df = pd.read_excel(CONFIG_FILE, sheet_name=tab_name)
            if not all(col in df.columns for col in cols): df = pd.DataFrame(columns=cols)
            return df.astype(str).replace('nan', '')
        except Exception:
            return pd.DataFrame(columns=cols)
    else:
        return pd.DataFrame(columns=cols)

def salvar_config(df, tab_name):
    st.error("ERRO DE DEPLOY: A função 'salvar_config' não funciona no Streamlit Cloud. Os dados do Excel são somente leitura.")
    pass

def carregar_usuarios():
    if os.path.exists(USUARIOS_FILE): return pd.read_excel(USUARIOS_FILE)
    else:
        df = pd.DataFrame(columns=["Nome", "Email", "Senha"])
        return df

def salvar_usuario(df):
    st.error("ERRO DE DEPLOY: A função 'salvar_usuario' não funciona no Streamlit Cloud. Os dados do Excel são somente leitura.")
    pass

def autenticar_direto(email):
    df = carregar_usuarios()
    user = df[df["Email"].astype(str).str.lower() == str(email).lower()]
    if not user.empty: return user.iloc[0]["Nome"]
    else: return None

def clean_key(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(text).lower())

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
    if pd.isna(data_agendamento): return "SLA: N/D (sem agendamento)", "gray"
    rule = df_sla[(df_sla["Nome do Projeto"] == projeto_nome) & (df_sla["Demanda"] == demanda)]
    if rule.empty: rule = df_sla[(df_sla["Nome do Projeto"] == projeto_nome) & (df_sla["Demanda"].astype(str).isin(['', 'nan']))]
    if rule.empty: return "SLA: N/A", "gray"
    try: prazo_dias = int(rule.iloc[0]["Prazo (dias)"])
    except (ValueError, TypeError): return "SLA: Inválido", "red"
    start_date = data_agendamento.date()
    if pd.notna(data_finalizacao):
        end_date = data_finalizacao.date(); dias_corridos = (end_date - start_date).days
        if dias_corridos <= prazo_dias: return f"Finalizado no Prazo ({dias_corridos}d)", "#66BB6A"
        else: atraso = dias_corridos - prazo_dias; return f"Finalizado com Atraso ({atraso}d)", "#EF5350"
    else:
        end_date = date.today(); dias_corridos = (end_date - start_date).days; dias_restantes = prazo_dias - dias_corridos
        if dias_restantes < 0: return f"Atrasado em {-dias_restantes}d", "#EF5350"
        elif dias_restantes == 0: return "SLA Vence Hoje!", "#FFA726"
        else: return f"SLA: {dias_restantes}d restantes", "#66BB6F"




