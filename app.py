import streamlit as st
import pandas as pd
from datetime import date
from utils import (
    carregar_projetos_db,
    adicionar_projeto_db,
    atualizar_projeto_db,
    excluir_projeto_db,
    carregar_config,
    get_status_color,
    calcular_sla,
    load_css
)

# ==========================================================
# 1. CONFIGURAÇÃO INICIAL
# ==========================================================
st.set_page_config(page_title="Agenda de Projetos", page_icon="📋", layout="wide")
load_css()

st.title("📋 Agenda de Projetos")

# ==========================================================
# 2. CONTROLE DE ESTADO
# ==========================================================
if "view" not in st.session_state:
    st.session_state.view = "listar"
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None

# ==========================================================
# 3. FUNÇÕES DE FLUXO (CORRIGIDAS)
# ==========================================================
def voltar_para_lista():
    st.session_state.view = "listar"
    st.session_state.selected_id = None
    # st.rerun() # REMOVIDO

def abrir_formulario_novo():
    st.session_state.view = "novo"
    st.session_state.selected_id = None
    # st.rerun() # REMOVIDO

def abrir_formulario_edicao(projeto_id):
    st.session_state.view = "editar"
    st.session_state.selected_id = projeto_id
    # st.rerun() # REMOVIDO

# ==========================================================
# 4. VISUALIZAÇÃO: LISTA DE PROJETOS (CORRIGIDA)
# ==========================================================
if st.session_state.view == "listar":
    st.markdown("### 📑 Lista de Projetos")

    df = carregar_projetos_db()
    if df.empty:
        st.info("Nenhum projeto cadastrado ainda.")
    else:
        df_display = df.copy()
        df_display["SLA"], df_display["Cor SLA"] = zip(*df_display.apply(
            lambda r: calcular_sla(r, carregar_config("sla")), axis=1))

        for idx, row in df_display.iterrows():
            cor_status = get_status_color(row.get("Status", ""))
            cor_sla = row["Cor SLA"]

            with st.container():
                cols = st.columns([3, 3, 3, 3, 1, 1])
                cols[0].markdown(f"**{row.get('Projeto', '')}**")
                cols[1].markdown(f"🏦 {row.get('Agência', '')}")
                cols[2].markdown(f"👷 {row.get('Técnico', '')}")
                cols[3].markdown(f"<span style='color:{cor_status}'>{row.get('Status', '')}</span>", unsafe_allow_html=True)
                cols[4].markdown(f"<span style='color:{cor_sla}'>{row['SLA']}</span>", unsafe_allow_html=True)
                with cols[5]:
                    if st.button("✏️", key=f"edit_{row['ID']}"):
                        abrir_formulario_edicao(row["ID"])
                        st.rerun() # Adicionar rerun AQUI, fora do callback, é seguro.
                    
                    if st.button("🗑️", key=f"del_{row['ID']}"):
                        if excluir_projeto_db(row["ID"]):
                            st.success("Projeto excluído com sucesso!")
                            # st.rerun() # REMOVIDO - O rerun do success/info já é suficiente
                        else:
                            st.error("Erro ao excluir o projeto.")
                        st.rerun() # Força a atualização da lista após a tentativa de exclusão


    st.divider()

    st.button("➕ Novo Projeto", on_click=abrir_formulario_novo)

# ==========================================================
# 5. VISUALIZAÇÃO: FORMULÁRIO (NOVO / EDITAR) (CORRIGIDO)
# ==========================================================
else: # if st.session_state.view == "novo" or st.session_state.view == "editar":
    editar = st.session_state.view == "editar"
    projeto_atual = None
    if editar and st.session_state.selected_id:
        df = carregar_projetos_db()
        # Garante que estamos pegando a linha certa e tratando o caso de não encontrar
        projeto_df = df[df["ID"] == st.session_state.selected_id]
        if not projeto_df.empty:
            projeto_atual = projeto_df.to_dict(orient="records")[0]
        else:
            st.error("ID do projeto não encontrado. Voltando para a lista.")
            voltar_para_lista()
            st.rerun() # Necessário para efetivar a volta

    st.markdown("### 📝 " + ("Editar Projeto" if editar else "Novo Projeto"))

    with st.form(key="form_projeto"):
        # Seção de inputs do formulário (sem alterações)
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome do Projeto", value=projeto_atual.get("Projeto", "") if projeto_atual else "")
        agencia = col2.text_input("Agência", value=projeto_atual.get("Agência", "") if projeto_atual else "")
        tecnico = col1.text_input("Técnico", value=projeto_atual.get("Técnico", "") if projeto_atual else "")
        
        status_options = ["Não iniciado", "Em andamento", "Finalizado", "Pausado", "Cancelado"]
        current_status = projeto_atual.get("Status", "Não iniciado") if projeto_atual else "Não iniciado"
        status_index = status_options.index(current_status) if current_status in status_options else 0
        status = col2.selectbox("Status", status_options, index=status_index)
        
        agendamento_val = pd.to_datetime(projeto_atual.get("Agendamento", date.today())).date() if projeto_atual else date.today()
        agendamento = col1.date_input("Agendamento", value=agendamento_val)
        
        abertura_val = pd.to_datetime(projeto_atual.get("Data de Abertura", date.today())).date() if projeto_atual else date.today()
        abertura = col2.date_input("Data de Abertura", value=abertura_val)

        # Tratar data de finalização que pode não existir
        finalizacao_val = projeto_atual.get("Data de Finalização")
        if pd.notna(finalizacao_val):
            finalizacao_val = pd.to_datetime(finalizacao_val).date()
        else:
            finalizacao_val = None # Usar None para permitir campo vazio
        finalizacao = col1.date_input("Data de Finalização", value=finalizacao_val)

        observacao = st.text_area("Observação", value=projeto_atual.get("Observação", "") if projeto_atual else "")

        submitted = st.form_submit_button("💾 Salvar")

    if submitted:
        dados = {
            "Projeto": nome,
            "Agência": agencia,
            "Técnico": tecnico,
            "Status": status,
            "Agendamento": str(agendamento),
            "Data de Abertura": str(abertura),
            "Data de Finalização": str(finalizacao) if finalizacao else None,
            "Observação": observacao
        }

        if editar:
            sucesso = atualizar_projeto_db(st.session_state.selected_id, dados)
        else:
            sucesso = adicionar_projeto_db(dados)

        if sucesso:
            st.success("✅ Projeto salvo com sucesso!")
            st.balloons()
            voltar_para_lista()
        else:
            st.error("❌ Erro ao salvar o projeto.")

    st.button("⬅️ Voltar", on_click=voltar_para_lista)
