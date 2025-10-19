import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html

# Importa TODAS as nossas funções do arquivo utils.py
import utils 
from sqlalchemy import inspect, text

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

# Função para inspecionar o banco de dados
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
            linhas = resultado.fetchall()
            if linhas:
                st.write("Exemplos de registros na tabela 'projetos':")
                for linha in linhas:
                    st.write(dict(linha))
            else:
                st.write("Tabela 'projetos' está vazia")
    except Exception as e:
        st.error(f"Erro ao consultar dados: {e}")

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css() # Carrega o CSS do arquivo utils

# ----------------- Telas da Página Principal -----------------
def tela_login():
    st.markdown("<div class='main-title'>GESTÃO DE PROJETOS</div>", unsafe_allow_html=True)
    st.title("")
    st.write("")
    with st.form("form_login"):
        email = st.text_input("Email (Opcional)", key="login_email")
        st.text_input("Senha (Desativada)", type="password", disabled=True)
        if st.form_submit_button("Conectar-se"):
            nome_usuario = "Visitante"
            if email: nome_usuario = utils.autenticar_direto(email) or email
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
            pergunta = row['Pergunta']; tipo = row['Tipo (texto, numero, data)']; key = utils.clean_key(pergunta)
            if tipo == 'data': respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
            elif tipo == 'numero': respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
            else: respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
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
    df_sla = utils.carregar_config("sla")
    df_etapas_config = utils.carregar_config("etapas_evolucao")
    
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        return

    # Normaliza agendamento para string segura
    df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime("%d/%m/%y").fillna('N/A')

    st.markdown("#### 🔍 Filtros e Busca")
    termo_busca = st.text_input("Buscar", key="termo_busca", placeholder="Digite um termo para buscar...")
    col1, col2, col3, col4 = st.columns(4)
    campos_select_1 = {"Status": col1, "Analista": col2, "Agência": col3, "Gestor": col4}
    campos_select_2 = {"Projeto": col1, "Técnico": col2}
    filtros = {}
    for campo, col in campos_select_1.items():
        with col:
            if campo in df.columns:
                opcoes = ["Todos"] + sorted(df[campo].astype(str).unique().tolist())
                filtros[campo] = st.selectbox(f"Filtrar por {campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")
    for campo, col in campos_select_2.items():
        with col:
            if campo in df.columns:
                opcoes = ["Todos"] + sorted(df[campo].astype(str).unique().tolist())
                filtros[campo] = st.selectbox(f"Filtrar por {campo}", opcoes, key=f"filtro_{utils.clean_key(campo)}")

    data_existente = pd.to_datetime(df['Agendamento'], errors='coerce').dropna()
    data_min = data_existente.min().date() if not data_existente.empty else date.today()
    data_max = data_existente.max().date() if not data_existente.empty else date.today()
    with col3:
        st.markdown("Agendamento (De):")
        data_inicio_filtro = st.date_input("De", value=data_min, key="filtro_data_start", label_visibility="collapsed", format="DD/MM/YYYY")
    with col4:
        st.markdown("Agendamento (Até):")
        data_fim_filtro = st.date_input("Até", value=data_max, key="filtro_data_end", label_visibility="collapsed", format="DD/MM/YYYY")

    df_filtrado = df.copy()
    for campo, valor in filtros.items():
        if valor != "Todos" and campo in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == valor]
    if data_inicio_filtro and data_fim_filtro:
        agendamento_dates = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce').dt.date
        mask = agendamento_dates.notna() & (agendamento_dates >= data_inicio_filtro) & (agendamento_dates <= data_fim_filtro)
        df_filtrado = df_filtrado[mask.fillna(False)]
    if termo_busca:
        termo = termo_busca.lower().strip()
        mask_busca = df_filtrado.apply(lambda row: row.astype(str).str.lower().str.contains(termo, na=False).any(), axis=1)
        df_filtrado = df_filtrado[mask_busca]

    st.markdown("---")
    st.info(f"Projetos encontrados: {len(df_filtrado)}")
    
    agencias_cfg = utils.carregar_config("agencias")
    tecnicos_cfg = utils.carregar_config("tecnicos")
    agencia_options = ["N/A"] + (agencias_cfg["Agência"].tolist() if not agencias_cfg.empty else [])
    tecnico_options = ["N/A"] + (tecnicos_cfg["Técnico"].tolist() if not tecnicos_cfg.empty else [])
    status_options = utils.carregar_config("status")["Status"].tolist() if not utils.carregar_config("status").empty else []

    for _, row in df_filtrado.iterrows():
        project_id = row['ID']
        
        status_raw = row['Status'] if pd.notna(row['Status']) else 'N/A'
        status_text = html.escape(str(status_raw))
        analista_text = html.escape(str(row['Analista'])) if pd.notna(row['Analista']) else 'N/A'
        agencia_text = html.escape(str(row.get("Agência", "N/A")))
        projeto_text = html.escape(str(row.get("Projeto", "N/A")))
        demanda_text = html.escape(str(row.get("Demanda", "N/A")))
        tecnico_text = html.escape(str(row.get("Técnico", "N/A")))
        status_color_name = utils.get_status_color(str(status_raw))
        sla_text, sla_color = utils.calcular_sla(row, df_sla)

        st.markdown("<div class='project-card'>", unsafe_allow_html=True)
        col_info, col_analista, col_agencia, col_status = st.columns([3, 2, 2, 1.5])
        with col_info:
            st.markdown(f"<h6>📅 {row['Agendamento_str']}</h6>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='margin:2px 0'>{projeto_text.upper()}</h5>", unsafe_allow_html=True)
            st.markdown(f"<small style='color:var(--muted);'>{demanda_text} - {tecnico_text}</small>", unsafe_allow_html=True)
        with col_analista:
            st.markdown(f"**Analista:** {analista_text}")
            st.markdown(f"<p style='color:{sla_color}; font-weight:bold;'>{sla_text}</p>", unsafe_allow_html=True)
        with col_agencia:
            st.markdown(f"**Agência:**")
            st.markdown(f"{agencia_text}")
        with col_status:
            st.markdown(
    f"""<div style="height:100%;display:flex;align-items:center;justify-content:flex-end;">
    <span style="background-color:{status_color_name};color:black;padding:8px 15px;border-radius:5px;font-weight:bold;font-size:0.9em;">{status_text}</span>
    </div>""",
    unsafe_allow_html=True
)

        with st.expander(f"Ver/Editar Detalhes - ID: {project_id}"):
            with st.form(f"form_edicao_card_{project_id}"):
                # restante do código de edição...
                pass

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
    # Adiciona botão para inspecionar banco
    if st.sidebar.button("🔍 Inspecionar Banco"):
        inspecionar_banco()
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
