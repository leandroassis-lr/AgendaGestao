import streamlit as st
import pandas as pd
import utils
import utils_chamados
from datetime import date, timedelta
import time

st.set_page_config(page_title="Detalhes - GESTÃO", page_icon="🔧", layout="wide")
utils.load_css()

# --- FUNÇÃO DE DIALOG (POP-UP) DE EDIÇÃO ---
@st.dialog("📝 Editar Chamado", width="large")
def open_chamado_dialog(row_dict):
    st.markdown(f"### Editando Chamado: {row_dict.get('Nº Chamado')}")
    st.info("Alterações feitas aqui refletem imediatamente no Banco de Dados.")
    
    with st.form("form_edit_chamado"):
        c1, c2 = st.columns(2)
        with c1:
            # Opções de Status
            lista_status = ["AGENDADO", "EM ANDAMENTO", "CONCLUÍDO", "FINALIZADO", "PENDÊNCIA", "CANCELADO", "FATURADO"]
            st_atual = str(row_dict.get('Status', 'AGENDADO')).upper()
            idx_st = lista_status.index(st_atual) if st_atual in lista_status else 0
            
            novo_status = st.selectbox("Status", lista_status, index=idx_st)
            novo_substatus = st.text_input("Sub-Status (Ação)", value=str(row_dict.get('Sub-Status','')))
            novo_analista = st.text_input("Analista", value=str(row_dict.get('Analista','')))
            novo_tecnico = st.text_input("Técnico", value=str(row_dict.get('Técnico','')))
            novo_link = st.text_input("Link Externo", value=str(row_dict.get('Link Externo','')))
            
        with c2:
            # Tratamento de Datas para o Form
            val_ag = row_dict.get('Agendamento')
            d_ag = pd.to_datetime(val_ag).date() if pd.notna(val_ag) else None
            novo_agendamento = st.date_input("Agendamento", value=d_ag)
            
            val_fech = row_dict.get('Fechamento')
            d_fech = pd.to_datetime(val_fech).date() if pd.notna(val_fech) else None
            nova_finalizacao = st.date_input("Fechamento", value=d_fech)
            
            nova_obs = st.text_area("Observação", value=str(row_dict.get('Observação','')), height=100)
            nova_desc = st.text_area("Descrição", value=str(row_dict.get('Descrição','')), height=100)

        # Botões de Ação
        c_btn1, c_btn2 = st.columns([1, 1])
        with c_btn1:
            submitted = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
        
    if submitted:
        dados = {
            'Status': novo_status,
            'Sub-Status': novo_substatus,
            'Analista': novo_analista,
            'Técnico': novo_tecnico,
            'Agendamento': novo_agendamento,
            'Fechamento': nova_finalizacao,
            'Observação': nova_obs,
            'Descrição': nova_desc,
            'Link Externo': novo_link
        }
        # Atualiza no Banco
        sucesso, msg = utils_chamados.atualizar_chamado_db(row_dict['ID'], dados)
        if sucesso:
            st.success("✅ Atualizado com sucesso!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Erro ao atualizar: {msg}")

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def main():
    # 1. BOTÃO DE VOLTAR (Topo da Página)
    c_back, c_title = st.columns([1, 5])
    with c_back:
        if st.button("⬅️ Voltar ao Cockpit", use_container_width=True):
            st.switch_page("app.py")
    with c_title:
        st.title("🔧 Detalhes Operacionais do Projeto")

    # 2. CARREGAMENTO DE DADOS
    df_filtrado = utils_chamados.carregar_chamados_db()
    
    if df_filtrado.empty:
        st.warning("Banco de dados vazio.")
        return

    with st.container():
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        
        # --- 3. FILTRO DE DATA (O PAI DE TODOS) ---
        c_tit, c_date = st.columns([4, 1.5])
        with c_tit: st.markdown("### 🔍 Filtros & Pesquisa")
        with c_date: 
            # Garante formato data
            df_filtrado['Agendamento'] = pd.to_datetime(df_filtrado['Agendamento'], errors='coerce')
            
            d_min = df_filtrado['Agendamento'].min() if not pd.isna(df_filtrado['Agendamento'].min()) else date.today()
            d_max = df_filtrado['Agendamento'].max() if not pd.isna(df_filtrado['Agendamento'].max()) else date.today()
            
            # Input de Data
            filtro_data_range = st.date_input("Período", value=(d_min, d_max), format="DD/MM/YYYY", label_visibility="collapsed")

        # --- 4. PREPARAÇÃO DAS LISTAS (BASEADO NA DATA) ---
        df_opcoes = df_filtrado.copy()
        if len(filtro_data_range) == 2:
            d_inicio, d_fim = filtro_data_range
            # Converte para timestamp seguro para filtrar
            ts_inicio = pd.to_datetime(d_inicio)
            ts_fim = pd.to_datetime(d_fim) + timedelta(hours=23, minutes=59)
            
            df_opcoes = df_opcoes[
                (df_opcoes['Agendamento'] >= ts_inicio) & 
                (df_opcoes['Agendamento'] <= ts_fim)
            ]
        
        # Listas dinâmicas
        df_opcoes['_filtro_agencia'] = df_opcoes['Cód. Agência'].astype(str) + " - " + df_opcoes['Nome Agência'].astype(str)
        lista_agencias_disponiveis = sorted(df_opcoes['_filtro_agencia'].dropna().unique().tolist())
        
        df_proj_options = df_opcoes.copy() # Usa o DF já filtrado por data
        lista_projetos_disponiveis = sorted(df_proj_options['Projeto'].dropna().unique().tolist())

        # --- 5. RECEBIMENTO DO FILTRO DO COCKPIT ---
        padrao_projetos = []
        if "sel_projeto" in st.session_state:
            p_sel = st.session_state["sel_projeto"]
            # Verifica se o projeto existe na lista total (mesmo que fora da data, para não travar)
            if p_sel in df_filtrado['Projeto'].unique(): 
                padrao_projetos = [p_sel]
            
            # Limpa a sessão para destravar navegação futura
            del st.session_state["sel_projeto"]

        # --- 6. CAMPOS DE FILTRO ---
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 1.5, 1.5])
        
        with c1:
            busca_geral = st.text_input("Busca", placeholder="🔎 ID, Nome, Serviço...", label_visibility="collapsed")
        
        with c2:
            filtro_agencia_multi = st.multiselect("Agências", options=lista_agencias_disponiveis, placeholder="Filtrar Agência", label_visibility="collapsed")
        
        with c3:
            # Se filtrar agência, reduz a lista de projetos
            if filtro_agencia_multi:
                # Filtra as opções de projeto baseado nas agências selecionadas
                projs_da_agencia = df_opcoes[df_opcoes['_filtro_agencia'].isin(filtro_agencia_multi)]['Projeto'].unique()
                lista_projetos_disponiveis = sorted([p for p in lista_projetos_disponiveis if p in projs_da_agencia])

            filtro_projeto_multi = st.multiselect("Projetos", options=lista_projetos_disponiveis, default=padrao_projetos, placeholder="Filtrar Projeto", label_visibility="collapsed")
        
        with c4:
            # Lista de Ações
            df_acao_options = df_proj_options.copy()
            if filtro_projeto_multi:
                df_acao_options = df_acao_options[df_acao_options['Projeto'].isin(filtro_projeto_multi)]
                
            lista_acoes = sorted([str(x) for x in df_acao_options['Sub-Status'].dropna().unique().tolist() if str(x).strip() != ''])
            filtro_acao_multi = st.multiselect("Ação / Etapa", options=lista_acoes, placeholder="Filtrar Ação/Status", label_visibility="collapsed")

        st.markdown('</div>', unsafe_allow_html=True)

    # --- 7. APLICAÇÃO FINAL DOS FILTROS NA TABELA (df_view) ---
    df_view = df_filtrado.copy()
    
    # 7.1 Filtro de Data
    if len(filtro_data_range) == 2:
        ts_inicio = pd.to_datetime(filtro_data_range[0])
        ts_fim = pd.to_datetime(filtro_data_range[1]) + timedelta(hours=23, minutes=59)
        df_view = df_view[(df_view['Agendamento'] >= ts_inicio) & (df_view['Agendamento'] <= ts_fim)]

    # 7.2 Busca Texto
    if busca_geral:
        termo = busca_geral.lower()
        df_view = df_view[df_view.astype(str).apply(lambda x: x.str.lower()).apply(lambda x: x.str.contains(termo)).any(axis=1)]
    
    # 7.3 Filtro de Agência
    if filtro_agencia_multi:
        df_view['_filtro_agencia'] = df_view['Cód. Agência'].astype(str) + " - " + df_view['Nome Agência'].astype(str)
        df_view = df_view[df_view['_filtro_agencia'].isin(filtro_agencia_multi)]

    # 7.4 Filtro de Projeto
    if filtro_projeto_multi: 
        df_view = df_view[df_view['Projeto'].isin(filtro_projeto_multi)]
        
    # 7.5 Filtro de Ação
    if filtro_acao_multi:
        df_view = df_view[df_view['Sub-Status'].astype(str).isin(filtro_acao_multi)]

    # --- 8. KPIs (INDICADORES DO TOPO) ---
    status_fim = ['concluído', 'finalizado', 'faturado', 'fechado', 'equipamento entregue']
    qtd_total = len(df_view)
    qtd_fim = len(df_view[df_view['Status'].str.lower().isin(status_fim)])
    
    if not df_view.empty:
        gr = df_view.groupby('Projeto')
        proj_total = gr.ngroups
        # Conta projetos onde TODOS os chamados estão finalizados
        proj_concluidos = sum(1 for _, d in gr if d['Status'].str.lower().isin(status_fim).all())
        proj_abertos = proj_total - proj_concluidos
    else: proj_total=0; proj_concluidos=0; proj_abertos=0

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"""<div class="kpi-card kpi-blue"><div class="kpi-title">Chamados (Visão Atual)</div><div class="kpi-value">{qtd_total}</div></div>""", unsafe_allow_html=True)
    with k2: st.markdown(f"""<div class="kpi-card kpi-orange"><div class="kpi-title">Projetos Abertos</div><div class="kpi-value">{proj_abertos}</div></div>""", unsafe_allow_html=True)
    with k3: st.markdown(f"""<div class="kpi-card kpi-green"><div class="kpi-title">Projetos Finalizados</div><div class="kpi-value">{proj_concluidos}</div></div>""", unsafe_allow_html=True)
    with k4: st.markdown(f"""<div class="kpi-card kpi-purple"><div class="kpi-title">Tarefas Concluídas</div><div class="kpi-value">{qtd_fim}</div></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 9. BARRA DE STATUS COLORIDA ---
    if not df_view.empty:
        counts = df_view['Sub-Status'].value_counts()
        top_status = counts.head(5) 
        if len(top_status) > 0:
            cols = st.columns(len(top_status))
            for i, (status, count) in enumerate(top_status.items()):
                try: cor = utils_chamados.get_status_color(status)
                except: cor = "#ccc"
                with cols[i]:
                    st.markdown(f"""<div class="status-summary-box" style="border-left: 5px solid {cor}; background: white; border: 1px solid #eee; border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;"><span class="status-label" style="font-size: 0.75em; font-weight: bold; color: #555; text-transform: uppercase;">{str(status)[:15]}</span><span class="status-val" style="font-size: 1.1em; font-weight: 800; color: #333;">{count}</span></div>""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 10. LISTAGEM PRINCIPAL (CARDS DETALHADOS) ---
    if df_view.empty:
        st.info("Nenhum registro encontrado com os filtros atuais.")
    else:
        # Ordenação
        df_view = df_view.sort_values(by=['Agendamento', 'Projeto'], ascending=[True, True])
        
        # Paginação simples para não travar
        itens_por_pag = 20
        total_pags = (len(df_view) // itens_por_pag) + 1
        pag_atual = st.number_input("Página", min_value=1, max_value=total_pags, value=1)
        inicio = (pag_atual - 1) * itens_por_pag
        fim = inicio + itens_por_pag
        
        df_paginado = df_view.iloc[inicio:fim]

        for i, row in df_paginado.iterrows():
            # Extração de dados
            c_id = row['ID']
            chamado = row.get('Nº Chamado', 'N/A')
            projeto = row.get('Projeto', 'N/A')
            agencia = f"{row.get('Cód. Agência','')} - {row.get('Nome Agência','')}"
            status = row.get('Status', 'AGENDADO')
            sub_status = row.get('Sub-Status', '')
            analista = row.get('Analista', 'N/D')
            tecnico = row.get('Técnico', 'N/D')
            
            # Tratamento data para exibição
            data_ag = row.get('Agendamento')
            data_str = data_ag.strftime('%d/%m/%Y') if pd.notna(data_ag) else "Sem Data"
            
            # Cor do Status
            cor_status = utils_chamados.get_status_color(status)

            # HTML do Card Rico
            card_html = f"""
            <div style="background-color: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 5px solid {cor_status}; box-shadow: 1px 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="background-color: #eee; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: #555;">{chamado}</span>
                        <h4 style="margin: 5px 0; color: #333;">{projeto}</h4>
                        <p style="margin: 0; font-size: 0.9em; color: #666;">🏢 {agencia}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: bold; font-size: 1.1em; color: #333;">{data_str}</div>
                        <span style="background-color: {cor_status}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; text-transform: uppercase;">{status}</span>
                    </div>
                </div>
                <hr style="margin: 10px 0; border-top: 1px solid #eee;">
                <div style="display:flex; justify-content: space-between; font-size: 0.85em; color: #555;">
                    <div>👤 <b>Analista:</b> {analista} &nbsp;&nbsp; 🔧 <b>Técnico:</b> {tecnico}</div>
                    <div style="font-weight:bold; color: #1565C0;">⚡ {sub_status}</div>
                </div>
                <div style="margin-top: 8px; font-size: 0.85em; color: #777; background: #f9f9f9; padding: 5px; border-radius: 4px;">
                    📝 {str(row.get('Descrição', ''))[:100]}...
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Botão de Editar (Abre o Dialog)
            if st.button(f"✏️ Editar {chamado}", key=f"edit_{c_id}"):
                open_chamado_dialog(row.to_dict())

if __name__ == "__main__":
    main()
