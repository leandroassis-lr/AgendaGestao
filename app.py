import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html
import io
from sqlalchemy import inspect, text

# Importa TODAS as nossas funções do arquivo utils.py
import utils 

# ----------------- Helpers -----------------
def _to_date_safe(val):
    """Converte várias representações (str, pd.Timestamp, datetime, date) para datetime.date ou None."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    try:
        ts = pd.to_datetime(val, errors='coerce')
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None

# ----------------- Função para Inspecionar Banco -----------------
def inspecionar_banco():
    engine = utils.get_engine()
    if engine is None:
        st.error("Não foi possível conectar ao banco")
        return

    inspector = inspect(engine)
    tabelas = inspector.get_table_names()
    st.write("Tabelas no banco:", tabelas)
    if "projetos" not in tabelas:
        st.warning("Tabela 'projetos' não encontrada no banco")
        return

    colunas = inspector.get_columns("projetos")
    st.write("Colunas da tabela 'projetos':")
    for col in colunas:
        st.write(f"- {col['name']} ({col['type']})")

    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT * FROM projetos LIMIT 10"))
            linhas = resultado.mappings().all()
            if linhas:
                st.write("Exemplos de registros na tabela 'projetos':")
                for linha in linhas:
                    st.write(linha)
            else:
                st.write("Tabela 'projetos' está vazia")
    except Exception as e:
        st.error(f"Erro ao consultar dados: {e}")

# ----------------- Função para Exportar Banco em Excel -----------------
def exportar_banco_excel():
    engine = utils.get_engine()
    if engine is None:
        st.error("Não foi possível conectar ao banco")
        return

    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT * FROM projetos"))
            linhas = resultado.mappings().all()
            if not linhas:
                st.info("Tabela 'projetos' está vazia")
                return
            df = pd.DataFrame(linhas)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Projetos')
            data = output.getvalue()

            st.download_button(
                label="📥 Download dos dados em Excel",
                data=data,
                file_name="projetos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"Erro ao exportar dados: {e}")

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css() # Carrega o CSS do arquivo utils

# ----------------- Telas da Página -----------------
# (mantém todas as funções tela_login, tela_cadastro_usuario, tela_cadastro_projeto, tela_projetos iguais ao seu código enviado antes,
# apenas omitidas aqui para foco na integração)

# ----------------- CONTROLE PRINCIPAL -----------------
def main():
    if "logado" not in st.session_state: st.session_state.logado = False
    if "cadastro" not in st.session_state: st.session_state.cadastro = False
    if "tela_cadastro_proj" not in st.session_state: st.session_state.tela_cadastro_proj = False

    if not st.session_state.get("logado", False):
        if st.session_state.get("cadastro", False):
            tela_cadastro_usuario()
        else:
            tela_login()
        return

    st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
    st.sidebar.divider()
    # Botão para inspecionar banco
    if st.sidebar.button("🔍 Inspecionar Banco"):
        inspecionar_banco()
    # Botão para exportar banco em Excel
    if st.sidebar.button("📥 Exportar banco para Excel"):
        exportar_banco_excel()
    st.sidebar.divider()
    st.sidebar.title("Ações")
    if st.sidebar.button("➕ Novo Projeto", use_container_width=True):
        st.session_state.tela_cadastro_proj = True
        st.rerun()
    st.sidebar.divider()
    st.sidebar.title("Sistema")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    
    if st.session_state.get("tela_cadastro_proj"):
        tela_cadastro_projeto()
    else:
        tela_projetos()

if __name__ == "__main__":
    main()
