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

# ----------------- Telas -----------------

def tela_login():
    st.markdown("<div class='main-title'>GESTÃO DE PROJETOS</div>", unsafe_allow_html=True)
    st.title("")
    st.write("")
    with st.form("form_login"):
        email = st.text_input("Email (Opcional)", key="login_email")
        st.text_input("Senha (Desativada)", type="password", disabled=True)
        if st.form_submit_button("Conectar-se"):
            nome_usuario = "Visitante"
            if email:
                nome_usuario = utils.autenticar_direto(email) or email
            st.session_state.update(usuario=nome_usuario, logado=True)
            st.rerun()
    st.divider()
    if st.button("Novo usuário", key="btn_novo_usuario"):
        st.session_state.cadastro = True
        st.rerun()

def tela_cadastro_usuario():
    st.subheader("Cadastrar Novo Usuário")
    with st.form("form_cadastro_usuario"):
        nome = st.text_input("Nome", key="cad_nome")
        email = st.text_input("Email", key="cad_email")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        if st.form_submit_button("Cadastrar"):
            if not nome or not email:
                st.error("Preencha Nome e Email.")
                return
            df = utils.carregar_usuarios()
            if email.lower() in df["Email"].astype(str).str.lower().values:
                st.error("Email já cadastrado!")
            else:
                nova_linha = pd.DataFrame([[nome, email, senha]], columns=df.columns)
                df = pd.concat([df, nova_linha], ignore_index=True)
                utils.salvar_usuario(df)
                st.success("Usuário cadastrado!")
                st.session_state.cadastro = False
                st.rerun()
    if st.button("Voltar para Login"):
        st.session_state.cadastro = False
        st.rerun()

def tela_cadastro_projeto():
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_cadastro_proj = False
        st.rerun()
    st.subheader("Cadastrar Novo Projeto")
    perguntas_customizadas = utils.carregar_config("perguntas")
    if perguntas_customizadas.empty:
        st.info("🚨 Nenhuma pergunta customizada configurada.")
        return

    with st.form("form_cadastro_projeto"):
        respostas_customizadas = {}
        for index, row in perguntas_customizadas.iterrows():
            pergunta = row['Pergunta']
            tipo = row['Tipo (texto, numero, data)']
            key = utils.clean_key(pergunta)
            if tipo == 'data':
                respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
            elif tipo == 'numero':
                respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
            else:
                respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
        btn_cadastrar = st.form_submit_button("Cadastrar Projeto")
    
    if btn_cadastrar:
        projeto_nome = respostas_customizadas.get(perguntas_customizadas.iloc[0]['Pergunta'], 'Projeto Customizado')
        nova_linha_data = {
            "Status": "NÃO INICIADA",
            "Data de Abertura": date.today().strftime('%Y-%m-%d'),
            "Analista": st.session_state.get('usuario', 'N/A'),
            "Projeto": projeto_nome
        }
        for pergunta, resposta in respostas_customizadas.items():
            if isinstance(resposta, date):
                nova_linha_data[pergunta] = resposta.strftime('%Y-%m-%d')
            else:
                nova_linha_data[pergunta] = resposta
        
        if utils.adicionar_projeto_db(nova_linha_data):
            st.success(f"Projeto '{projeto_nome}' cadastrado!")
            st.session_state["tela_cadastro_proj"] = False
            st.rerun()

def tela_projetos():
    st.markdown("<div class='section-title-center'>PROJETOS</div>", unsafe_allow_html=True)
    
    df = utils.carregar_projetos_db()
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # Mostra o DataFrame com projetos filtrável e ordenável
    st.dataframe(df)

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
        return None
    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT * FROM projetos"))
            linhas = resultado.mappings().all()
        if not linhas:
            st.info("Tabela 'projetos' está vazia")
            return None
        df = pd.DataFrame(linhas)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Projetos')
        return output.getvalue()
    except Exception as e:
        st.error(f"Erro ao exportar dados: {e}")
        return None

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css()

# ----------------- CONTROLE PRINCIPAL -----------------
def main():
    if "logado" not in st.session_state:
        st.session_state.logado = False
    if "cadastro" not in st.session_state:
        st.session_state.cadastro = False
    if "tela_cadastro_proj" not in st.session_state:
        st.session_state.tela_cadastro_proj = False

    if not st.session_state.get("logado", False):
        if st.session_state.get("cadastro", False):
            tela_cadastro_usuario()
        else:
            tela_login()
        return

    st.sidebar.title(f"Bem-vindo(a), {st.session_state.get('usuario', 'Visitante')}! 📋")
    st.sidebar.divider()

    if st.sidebar.button("🔍 Inspecionar Banco"):
        inspecionar_banco()

    excel_data = exportar_banco_excel()
    if excel_data:
        st.sidebar.download_button(
            label="📥 Exportar banco para Excel",
            data=excel_data,
            file_name="projetos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
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

