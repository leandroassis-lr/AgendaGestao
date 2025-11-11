import streamlit as st
import pandas as pd
import io
import utils_chamados
from datetime import datetime

def tela_dados_agencia():
    st.title("🏦 Dados por Agência")

    # --- 1. Carregar dados iniciais ---
    df_chamados_raw = utils_chamados.carregar_chamados_db()

# --- 1.1 Criar coluna combinada de agência ---
# Detecta colunas possíveis
possiveis_num_agencia = ["Numero_Agencia", "N_Agencia", "Agencia_Numero", "Agencia Nº", "Agencia_N"]
possiveis_nome_agencia = ["Nome_Agencia", "Agencia", "Agência", "Nome", "Agencia_Nome"]

col_num_agencia = next((c for c in possiveis_num_agencia if c in df_chamados_raw.columns), None)
col_nome_agencia = next((c for c in possiveis_nome_agencia if c in df_chamados_raw.columns), None)

# Cria a coluna combinada se as duas existirem
if col_num_agencia and col_nome_agencia:
    df_chamados_raw["Agencia_Combinada"] = (
        df_chamados_raw[col_num_agencia].astype(str).str.strip() + " - " +
        df_chamados_raw[col_nome_agencia].astype(str).str.strip()
    )
else:
    st.error("❌ Não foi possível criar a coluna 'Agencia_Combinada'. Verifique se o número e o nome da agência estão nas colunas corretas.")
    st.stop()

    # --- 2. Preparar listas de opções ---
    agencia_list = ["Todos"] + sorted(df_chamados_raw["Agencia_Combinada"].dropna().unique().tolist())
    analista_list = ["Todos"] + sorted(df_chamados_raw["Analista"].dropna().unique().tolist())
    projeto_list = ["Todos"] + sorted(df_chamados_raw["Projeto"].dropna().unique().tolist())
    gestor_list = ["Todos"] + sorted(df_chamados_raw["Gestor"].dropna().unique().tolist())
    status_list = ["Todos"] + sorted(df_chamados_raw["Status"].dropna().unique().tolist())

    # ============================================================
    # 5. FILTROS PRINCIPAIS
    # ============================================================
    st.markdown("#### 🔎 Busca Total")
    busca_total = st.text_input(
        "Busca Total", 
        placeholder="Buscar por Nº Chamado, Equipamento, Descrição, Obs., etc...", 
        label_visibility="collapsed", 
        key="filtro_busca_total"
    )

    st.markdown("#### 🎛️ Filtros Específicos")
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_agencia = st.selectbox("Agência:", options=agencia_list, key="filtro_agencia")
    with col2:
        filtro_analista = st.selectbox("Analista:", options=analista_list, key="filtro_analista")
    with col3:
        filtro_projeto = st.selectbox("Projeto:", options=projeto_list, key="filtro_projeto")

    col4, col5, col6 = st.columns(3)
    with col4:
        filtro_gestor = st.selectbox("Gestor:", options=gestor_list, key="filtro_gestor")
    with col5:
        filtro_status = st.selectbox("Status:", options=status_list, key="filtro_status")
    with col6:
        st.write("&nbsp;")

    col7, col8 = st.columns(2)
    with col7:
        filtro_data_inicio = st.date_input("Agendamento (De):", value=None, format="DD/MM/YYYY", key="filtro_data_inicio")
    with col8:
        filtro_data_fim = st.date_input("Agendamento (Até):", value=None, format="DD/MM/YYYY", key="filtro_data_fim")

    st.divider()

    # ============================================================
    # 6. FILTRAR DATAFRAME PRINCIPAL
    # ============================================================
    df_filtrado = df_chamados_raw.copy()

    if filtro_agencia != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Agencia_Combinada'] == filtro_agencia]
    if filtro_analista != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Analista'] == filtro_analista]
    if filtro_projeto != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Projeto'] == filtro_projeto]
    if filtro_gestor != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Gestor'] == filtro_gestor]
    if filtro_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Status'] == filtro_status]

    df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
    if filtro_data_inicio:
        df_filtrado = df_filtrado[df_filtrado['Agendamento'] >= pd.to_datetime(filtro_data_inicio)]
    if filtro_data_fim:
        df_filtrado = df_filtrado[df_filtrado['Agendamento'] <= pd.to_datetime(filtro_data_fim).replace(hour=23, minute=59)]

    if busca_total:
        termo = busca_total.lower()
        cols_to_search = [
            'Nº Chamado', 'Projeto', 'Gestor', 'Analista', 'Sistema', 'Serviço',
            'Equipamento', 'Descrição', 'Observações e Pendencias', 'Obs. Equipamento',
            'Link Externo', 'Nº Protocolo', 'Nº Pedido'
        ]
        masks = []
        for col in cols_to_search:
            if col in df_filtrado.columns:
                masks.append(df_filtrado[col].astype(str).str.lower().str.contains(termo, na=False))
        if masks:
            combined_mask = pd.concat(masks, axis=1).any(axis=1)
            df_filtrado = df_filtrado[combined_mask]

    # ============================================================
    # 7. RESULTADOS
    # ============================================================
    if not df_filtrado.empty:
        st.dataframe(df_filtrado, use_container_width=True)
    else:
        st.info("Nenhum projeto encontrado para os filtros selecionados.")

    # ============================================================
    # 8. EXPORTAR DADOS PARA EXCEL
    # ============================================================
    st.markdown("---")
    st.markdown("### 📤 Exportar Dados")
    st.caption("Clique abaixo para extrair os dados atuais filtrados em formato Excel.")

    if st.button("💾 Exportar Dados Filtrados para Excel", width="stretch"):
        if not df_filtrado.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df_filtrado.to_excel(writer, index=False, sheet_name="Dados_Filtrados")
            buffer.seek(0)

            with st.modal("⬇️ Download do Excel"):
                st.success("Arquivo Excel gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Excel",
                    data=buffer,
                    file_name="dados_filtrados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch"
                )
        else:
            st.warning("Nenhum dado disponível para exportação com os filtros aplicados.")

tela_dados_agencia()

