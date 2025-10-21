import streamlit as st
import pandas as pd
from datetime import date, datetime
import re
import html
import utils  # Importa TODAS as nossas funções do arquivo utils.py

# ----------------- Helpers -----------------
def _to_date_safe(val):
    """Converte várias representações para datetime.date ou None de forma segura."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    try:
        return pd.to_datetime(val, errors='coerce').date()
    except Exception:
        return None

# ----------------- Configuração da Página e CSS -----------------
st.set_page_config(page_title="Projetos - GESTÃO", page_icon="📋", layout="wide")
utils.load_css() # Carrega o CSS do arquivo utils

# ----------------- Telas da Página Principal -----------------
def tela_login():
    # ... (código existente, sem alterações)
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
    # ... (código existente, sem alterações)
    st.subheader("Cadastrar Novo Usuário")
    with st.form("form_cadastro_usuario"):
        nome = st.text_input("Nome", key="cad_nome")
        email = st.text_input("Email", key="cad_email")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        if st.form_submit_button("Cadastrar"):
            if not nome or not email:
                st.error("Preencha Nome e Email.")
                return
            df = utils.carregar_usuarios_db()
            if not df.empty and email.lower() in df["email"].astype(str).str.lower().values:
                st.error("Email já cadastrado!")
            else:
                st.error("Funcionalidade de salvar novos usuários precisa ser implementada.")

    if st.button("Voltar para Login"):
        st.session_state.cadastro = False
        st.rerun()

def tela_cadastro_projeto():
    # ... (código existente, sem alterações)
    if st.button("⬅️ Voltar para Projetos"):
        st.session_state.tela_cadastro_proj = False
        st.rerun()
    st.subheader("Cadastrar Novo Projeto")
    
    perguntas_customizadas = utils.carregar_config_db("perguntas")
    
    if perguntas_customizadas.empty or 'Pergunta' not in perguntas_customizadas.columns:
        st.info("🚨 Nenhuma pergunta customizada configurada. (Vá para Configurações > Gerenciar Listas)")
        return

    with st.form("form_cadastro_projeto"):
        respostas_customizadas = {}
        for _, row in perguntas_customizadas.iterrows():
            pergunta = row['Pergunta']
            tipo = row.get('Tipo (texto, numero, data)', 'texto')
            key = utils.clean_key(pergunta)
            if tipo == 'data': respostas_customizadas[pergunta] = st.date_input(pergunta, value=None, key=f"custom_{key}", format="DD/MM/YYYY")
            elif tipo == 'numero': respostas_customizadas[pergunta] = st.number_input(pergunta, key=f"custom_{key}", step=1)
            else: respostas_customizadas[pergunta] = st.text_input(pergunta, key=f"custom_{key}")
        
        btn_cadastrar = st.form_submit_button("Cadastrar Projeto")
    
    if btn_cadastrar:
        projeto_nome = respostas_customizadas.get(perguntas_customizadas.iloc[0]['Pergunta'], 'Projeto Customizado')
        nova_linha_data = {
            "Status": "NÃO INICIADA",
            "Data de Abertura": date.today(),
            "Analista": st.session_state.get('usuario', 'N/A'),
            "Projeto": projeto_nome
        }
        nova_linha_data.update(respostas_customizadas)
        
        if utils.adicionar_projeto_db(nova_linha_data):
            st.success(f"Projeto '{projeto_nome}' cadastrado!")
            st.session_state["tela_cadastro_proj"] = False
            st.rerun()

def tela_projetos():
    st.markdown("<div class='section-title-center'>PROJETOS</div>", unsafe_allow_html=True)
    
    df = utils.carregar_projetos_db()
    df_sla = utils.carregar_config_db("sla")
    df_etapas_config = utils.carregar_config_db("etapas_evolucao")
    
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
        if st.button("➕ Cadastrar Primeiro Projeto"):
            st.session_state.tela_cadastro_proj = True
            st.rerun()
        return

    df['Agendamento_str'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.strftime("%d/%m/%y").fillna('N/A')

    st.markdown("#### 🔍 Filtros e Busca")
    termo_busca = st.text_input("Buscar", key="termo_busca", placeholder="Digite um termo para buscar...")
    col1, col2, col3, col4 = st.columns(4)
    
    df_filtrado = df.copy()

    filtros_ativos = {}
    with col1:
        if 'Status' in df.columns:
            opcoes = ["Todos"] + sorted(df['Status'].astype(str).unique().tolist())
            filtros_ativos['Status'] = st.selectbox("Filtrar por Status", opcoes)
    with col2:
        if 'Analista' in df.columns:
            opcoes = ["Todos"] + sorted(df['Analista'].astype(str).unique().tolist())
            filtros_ativos['Analista'] = st.selectbox("Filtrar por Analista", opcoes)
    with col3:
        if 'Agência' in df.columns:
            opcoes = ["Todos"] + sorted(df['Agência'].astype(str).unique().tolist())
            filtros_ativos['Agência'] = st.selectbox("Filtrar por Agência", opcoes)
    
    for campo, valor in filtros_ativos.items():
        if valor != "Todos":
            df_filtrado = df_filtrado[df_filtrado[campo].astype(str) == valor]

    if termo_busca:
        termo = termo_busca.lower().strip()
        mask = df_filtrado.apply(lambda row: any(termo in str(x).lower() for x in row), axis=1)
        df_filtrado = df_filtrado[mask]

    st.markdown("---")
    st.info(f"Projetos encontrados: {len(df_filtrado)}")

    agencias_cfg = utils.carregar_config_db("agencias")
    tecnicos_cfg = utils.carregar_config_db("tecnicos")
    status_options_df = utils.carregar_config_db("status")
    
    agencia_options = ["N/A"] + (agencias_cfg.iloc[:, 0].tolist() if not agencias_cfg.empty else [])
    tecnico_options = ["N/A"] + (tecnicos_cfg.iloc[:, 0].tolist() if not tecnicos_cfg.empty else [])
    status_options = status_options_df.iloc[:, 0].tolist() if not status_options_df.empty else []

    for _, row in df_filtrado.iterrows():
        project_id = row['ID']
        
        status_text = html.escape(str(row.get('Status', 'N/A')))
        analista_text = html.escape(str(row.get('Analista', 'N/A')))
        agencia_text = html.escape(str(row.get('Agência', 'N/A')))
        projeto_text = html.escape(str(row.get('Projeto', 'N/A')))
        
        status_color_name = utils.get_status_color(status_text)
        sla_text, sla_color = utils.calcular_sla(row, df_sla)

        st.markdown(f"<div class='project-card' key='card_{project_id}'>", unsafe_allow_html=True)
        col_info, col_analista, col_agencia, col_status = st.columns([3, 2, 2, 1.5])
        with col_info:
            st.markdown(f"<h6>📅 {row.get('Agendamento_str', 'N/A')}</h6>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='margin:2px 0'>{projeto_text.upper()}</h5>", unsafe_allow_html=True)
        with col_analista:
            st.markdown(f"**Analista:** {analista_text}")
            st.markdown(f"<p style='color:{sla_color}; font-weight:bold;'>{sla_text}</p>", unsafe_allow_html=True)
        with col_agencia:
            st.markdown(f"**Agência:** {agencia_text}")
        with col_status:
            st.markdown(
                f"""<div style="height:100%;display:flex;align-items:center;justify-content:flex-end;">
                <span style="background-color:{status_color_name};color:black;padding:8px 15px;border-radius:5px;font-weight:bold;font-size:0.9em;">{status_text}</span>
                </div>""",
                unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander(f"Ver/Editar Detalhes - ID: {project_id}"):
            with st.form(f"form_edicao_card_{project_id}"):
                
                novo_projeto = st.text_input("Projeto", value=row.get('Projeto', ''), key=f"proj_{project_id}")
                novo_analista = st.text_input("Analista", value=row.get('Analista', ''), key=f"analista_{project_id}")
                novo_gestor = st.text_input("Gestor", value=row.get('Gestor', ''), key=f"gestor_{project_id}")
                
                idx_status = status_options.index(row.get('Status')) if row.get('Status') in status_options else 0
                novo_status_selecionado = st.selectbox("Status", status_options, index=idx_status, key=f"status_{project_id}")

                # ... (restante dos campos do formulário)
                
                # --- CORREÇÃO APLICADA AQUI ---
                # Botões de salvar e excluir estão juntos dentro do formulário
                col_save, col_delete = st.columns([4, 1])
                with col_save:
                    btn_salvar_card = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
                with col_delete:
                    # Este botão não envia o formulário, mas sua ação é processada no mesmo ciclo
                    if st.form_submit_button("🗑️ Excluir", use_container_width=True, type="primary"):
                        if utils.excluir_projeto_db(project_id):
                            st.rerun()
                # --- FIM DA CORREÇÃO ---

                if btn_salvar_card:
                    updates = {
                        "Projeto": novo_projeto,
                        "Analista": novo_analista,
                        "Gestor": novo_gestor,
                        "Status": novo_status_selecionado,
                    }
                    if utils.atualizar_projeto_db(project_id, updates):
                        st.success(f"Projeto ID {project_id} atualizado.")
                        st.rerun()

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
