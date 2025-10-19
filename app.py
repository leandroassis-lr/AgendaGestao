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
# 3. FUNÇÕES DE FLUXO
# ==========================================================
def voltar_para_lista():
    st.session_state.view = "listar"
    st.session_state.selected_id = None
    st.rerun()

def abrir_formulario_novo():
    st.session_state.view = "novo"
    st.session_state.selected_id = None
    st.rerun()

def abrir_formulario_edicao(projeto_id):
    st.session_state.view = "editar"
    st.session_state.selected_id = projeto_id
    st.rerun()

# ==========================================================
# 4. VISUALIZAÇÃO: LISTA DE PROJETOS
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
                    if st.button("🗑️", key=f"del_{row['ID']}"):
                        if excluir_projeto_db(row["ID"]):
                            st.success("Projeto excluído com sucesso!")
                            st.rerun()

        st.divider()

    st.button("➕ Novo Projeto", on_click=abrir_formulario_novo)

# ==========================================================
# 5. VISUALIZAÇÃO: FORMULÁRIO (NOVO / EDITAR)
# ==========================================================
else:
    editar = st.session_state.view == "editar"
    projeto_atual = None
    if editar and st.session_state.selected_id:
        df = carregar_projetos_db()
        projeto_atual = df[df["ID"] == st.session_state.selected_id].to_dict(orient="records")
        if projeto_atual:
            projeto_atual = projeto_atual[0]
        else:
            st.warning("Projeto não encontrado.")
            voltar_para_lista()

    st.markdown("### 📝 " + ("Editar Projeto" if editar else "Novo Projeto"))

    # Campos do formulário
    with st.form(key="form_projeto"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome do Projeto", value=projeto_atual.get("Projeto", "") if projeto_atual else "")
        agencia = col2.text_input("Agência", value=projeto_atual.get("Agência", "") if projeto_atual else "")
        tecnico = col1.text_input("Técnico", value=projeto_atual.get("Técnico", "") if projeto_atual else "")
        status = col2.selectbox("Status", ["Não iniciado", "Em andamento", "Finalizado", "Pausado", "Cancelado"],
                                index=0 if not projeto_atual else
                                ["Não iniciado", "Em andamento", "Finalizado", "Pausado", "Cancelado"].index(
                                    projeto_atual.get("Status", "Não iniciado")))
        agendamento = col1.date_input("Agendamento", value=pd.to_datetime(
            projeto_atual.get("Agendamento", date.today())))
        abertura = col2.date_input("Data de Abertura", value=pd.to_datetime(
            projeto_atual.get("Data de Abertura", date.today())))
        finalizacao = col1.date_input("Data de Finalização", value=pd.to_datetime(
            projeto_atual.get("Data de Finalização", date.today())))
        observacao = st.text_area("Observação", value=projeto_atual.get("Observação", "") if projeto_atual else "")

        submitted = st.form_submit_button("💾 Salvar")

    if submitted:
        dados = {
            "Projeto": nome,
            "Agência": agencia,
            "Técnico": tecnico,
            "Status": status,
            "Agendamento": agendamento,
            "Data de Abertura": abertura,
            "Data de Finalização": finalizacao,
            "Observação": observacao
        }

        sucesso = atualizar_projeto_db(st.session_state.selected_id, dados) if editar else adicionar_projeto_db(dados)
        if sucesso:
            st.success("✅ Projeto salvo com sucesso!")
            voltar_para_lista()
        else:
            st.error("❌ Erro ao salvar o projeto.")

    st.button("⬅️ Voltar", on_click=voltar_para_lista)
