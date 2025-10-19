import streamlit as st
import pandas as pd
import os
from datetime import date
import re
import html
from sqlalchemy import text

CONFIG_FILE = "config.xlsx"
USUARIOS_FILE = "usuarios.xlsx"
CONFIG_TABS = {
    "status": ["Status"], "agencias": ["Agência"], "projetos_nomes": ["Nome do Projeto"],
    "tecnicos": ["Técnico"], "sla": ["Nome do Projeto", "Demanda", "Prazo (dias)"],
    "perguntas": ["Pergunta", "Tipo (texto, numero, data)"],
    "etapas_evolucao": ["Nome do Projeto", "Etapa"]
}

@st.cache_data(ttl=60)
def carregar_projetos_db():
    try:
        conn = st.connection("turso", type="sql")
        query = "SELECT * FROM projetos ORDER BY ID DESC"
        df = conn.query(query,
                        parse_dates={"Agendamento": {"errors": "coerce"},
                                     "Data_Abertura": {"errors": "coerce"},
                                     "Data_Finalizacao": {"errors": "coerce"}})
        df.rename(columns={
            'Descricao': 'Descrição', 'Agencia': 'Agência', 'Tecnico': 'Técnico',
            'Observacao': 'Observação', 'Data_Abertura': 'Data de Abertura',
            'Data_Finalizacao': 'Data de Finalização', 'Log_Agendamento': 'Log Agendamento',
            'Etapas_Concluidas': 'Etapas Concluidas'
        }, inplace=True)
        return df
    except Exception as e:
        if "no such table" in str(e):
            st.error("Erro: A tabela 'projetos' não foi encontrada no Turso. Lembra-te de executar a Etapa 4 (Migrar os dados antigos).")
        else:
            st.error(f"Erro ao carregar projetos: {e}")
        return pd.DataFrame()

def atualizar_projeto_db(project_id, updates: dict):
    """Retorna (success: bool, message: str)"""
    try:
        conn = st.connection("turso", type="sql")
        db_updates = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in updates.items()
        }
        set_clause = ", ".join([f'"{key}" = ?' for key in db_updates.keys()])
        sql = f"UPDATE projetos SET {set_clause} WHERE ID = ?"
        values = list(db_updates.values()) + [project_id]

        with conn.session as s:
            s.execute(text(sql), values)
            s.commit()

        st.cache_data.clear()
        return True, f"Projeto (ID: {project_id}) atualizado com sucesso."
    except Exception as e:
        return False, f"Erro ao atualizar projeto: {e}"

def adicionar_projeto_db(data: dict):
    """Retorna (success: bool, message: str)"""
    try:
        conn = st.connection("turso", type="sql")
        db_data = {
            key.replace(' ', '_').replace('ç', 'c').replace('ê', 'e').replace('ã', 'a'): value
            for key, value in data.items()
        }
        cols_str = ', '.join([f'"{c}"' for c in db_data.keys()])
        placeholders = ', '.join(['?'] * len(db_data))
        sql = f"INSERT INTO projetos ({cols_str}) VALUES ({placeholders})"

        with conn.session as s:
            s.execute(text(sql), list(db_data.values()))
            s.commit()

        st.cache_data.clear()
        return True, "Projeto adicionado com sucesso."
    except Exception as e:
        return False, f"Erro ao adicionar projeto: {e}"

def excluir_projeto_db(project_id):
    """Retorna (success: bool, message: str)"""
    try:
        conn = st.connection("turso", type="sql")
        sql = 'DELETE FROM projetos WHERE ID = ?'

        with conn.session as s:
            s.execute(text(sql), (project_id,))
            s.commit()

        st.cache_data.clear()
        return True, "Projeto excluído com sucesso."
    except Exception as e:
        return False, f"Erro ao excluir projeto: {e}"

def load_css():
    css_path = "style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""<style>/* fallback */</style>""", unsafe_allow_html=True)

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
    # Mantido como placeholder — salvar em xlsx no Cloud falhará sem filesystem persistente
    pass

def carregar_usuarios():
    if os.path.exists(USUARIOS_FILE): return pd.read_excel(USUARIOS_FILE)
    else:
        df = pd.DataFrame(columns=["Nome", "Email", "Senha"])
        return df

def salvar_usuario(df):
    # Mantido, mas no Cloud pode falhar
    df.to_excel(USUARIOS_FILE, index=False)

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
