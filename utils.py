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
# SEÇÃO DE CONEXÃO (CORRIGIDA)
# =========================================================================

@st.cache_resource  # Usamos cache_resource para o "motor" da conexão
def get_engine():
    """
    Cria e retorna uma conexão (engine) SQLAlchemy para o Turso.
    Esta função usa os "Secrets" do Streamlit.
    """
    try:
        # 1. Puxa as credenciais dos "Secrets" do Streamlit
        #    (Estes devem ser os NOMES das chaves no painel do Streamlit Cloud)
        db_url = st.secrets["TURSO_DB_URL"]
        db_token = st.secrets["TURSO_AUTH_TOKEN"]
        
        # 2. VERIFICA se o usuário colocou "libsql://" por engano no secret
        if db_url.startswith("libsql://"):
            db_url = db_url[9:] # Remove o prefixo
            
        # 3. Monta a URL de conexão CORRETA
        #    O formato é: "sqlite+dialeto://hostname"
        connection_url = f"sqlite+libsql://{db_url}"
        
        # 4. Cria o "motor" (engine) da conexão
        #    O 'auth_token' vai nos 'connect_args'
        engine = create_engine(
            connection_url, 
            connect_args={
                "auth_token": db_token,
                "check_same_thread": False # OBRIGATÓRIO para Streamlit
            }
        )
        return engine
    
    except KeyError as e:
        # Agora a mensagem de erro será clara
        st.error(f"Erro Crítico: A credencial {e} não foi encontrada nos 'Secrets' do Streamlit.")
        st.info("Por favor, adicione TURSO_DB_URL e TURSO_AUTH_TOKEN aos Secrets do seu app.")
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
        
        # Usamos 'with engine.connect()' para rodar a query
        with engine.connect() as conn:
            df = pd.read_sql_query(
                sql=text(query),  # Usar text() é uma boa prática
                con=conn,
                parse_dates={"Agendamento": {"errors": "coerce"},
                             "Data_Abertura": {"errors": "coerce"},
                             "Data_Finalizacao": {"errors": "coerce"}}
            )
        
        # Sua lógica original de renomear colunas (mantida)
        df.rename(columns={
            'Descricao': 'Descrição', 'Agencia': 'Agência', 'Tecnico': 'Técnico',
            'Observacao': 'Observação', 'Data_Abertura': 'Data de Abertura',
            'Data_Finalizacao': 'Data de Finalização', 'Log_Agendamento': 'Log Agendamento',
            'Etapas_Concluidas': 'Etapas Concluidas'
        }, inplace=True)
        return df
        
    except Exception as e:
        # Seu tratamento de erro original (mantido)
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
        # Sua lógica original de conversão de nomes de colunas (mantida)
        db_updates = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in updates.items()
        }
        
        # Sua lógica original de SQL (mantida)
        set_clause = ", ".join([f'"{key}" = ?' for key in db_updates.keys()])
        sql = f"UPDATE projetos SET {set_clause} WHERE ID = ?"
        values = list(db_updates.values()) + [project_id]

        # Usamos 'with engine.connect()' para executar a atualização
        with engine.connect() as conn:
            conn.execute(text(sql), values)
            conn.commit()  # Salva a transação
            
        st.cache_data.clear() # Limpa o cache
        return True
        
    except Exception as e:
        st.toast(f"Erro ao atualizar projeto: {e}", icon="🔥") # Seu toast (mantido)
        return False

def adicionar_projeto_db(data: dict):
    """Adiciona um novo projeto ao banco."""
    engine = get_engine()
    if engine is None:
        return False
        
    try:
        # Sua lógica original de conversão de nomes de colunas (mantida)
        db_data = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in data.items()
        }
        
        # Sua lógica original de SQL (mantida)
        cols_str = ', '.join([f'"{c}"' for c in db_data.keys()])
        placeholders = ', '.join(['?'] * len(db_data))
        sql = f"INSERT INTO projetos ({cols_str}) VALUES ({placeholders})"
        values = list(db_data.values())
        
        # Usamos 'with engine.connect()' para executar a inserção
        with engine.connect() as conn:
            conn.execute(text(sql), values)
            conn.commit() # Salva a transação
            
        st.cache_data.clear() # Limpa o cache
        return True
        
    except Exception as e:
        st.toast(f"Erro ao adicionar projeto: {e}", icon="🔥") # Seu toast (mantido)
        return False

def excluir_projeto_db(project_id):
    """Exclui um projeto do banco com base no ID."""
    engine = get_engine()
    if engine is None:
        return False
        
    try:
        # Sua lógica original de SQL (mantida)
        sql = 'DELETE FROM projetos WHERE ID = ?'
        
        # Usamos 'with engine.connect()' para executar a exclusão
        with engine.connect() as conn:
            conn.execute(text(sql), (project_id,)) # Passa o ID como uma tupla
            conn.commit() # Salva a transação
            
        st.cache_data.clear() # Limpa o cache
        st.toast("Projeto excluído!", icon="✅") # Seu toast (mantido)
        return True
        
    except Exception as e:
        st.toast(f"Erro ao excluir projeto: {e}", icon="🔥") # Seu toast (mantido)
        return False

# =========================================================================
# O RESTO DO SEU ARQUIVO UTILS.PY (INTACTO)
# =========================================================================

# --- FUNÇÕES DE CONFIGURAÇÃO E UTILITÁRIOS ---
# (O resto do teu código permanece igual)
# ATENÇÃO: As funções que usam .xlsx (salvar_config, salvar_usuario)
# ainda vão falhar no Streamlit Cloud, como discutimos.

def load_css():
    css_path = "style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Fallback CSS (O seu código original tinha "..." aqui)
        st.markdown("""<style> 
            /* Adicione um CSS básico aqui se o arquivo falhar */
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
    # (código mantido como no seu original)
    st.error("ERRO DE DEPLOY: A função 'salvar_config' não funciona no Streamlit Cloud. Os dados do Excel são somente leitura.")
    # ATENÇÃO: ISTO VAI FALHAR NO STREAMLIT CLOUD
    pass

def carregar_usuarios():
    if os.path.exists(USUARIOS_FILE): return pd.read_excel(USUARIOS_FILE)
    else:
        df = pd.DataFrame(columns=["Nome", "Email", "Senha"])
        # ATENÇÃO: ISTO VAI FALHAR NO STREAMLIT CLOUD
        # df.to_excel(USUARIOS_FILE, index=False) 
        return df

def salvar_usuario(df):
    st.error("ERRO DE DEPLOY: A função 'salvar_usuario' não funciona no Streamlit Cloud. Os dados do Excel são somente leitura.")
    # ATENÇÃO: ISTO VAI FALHAR NO STREAMLIT CLOUD
    # df.to_excel(USUARIOS_FILE, index=False)
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
