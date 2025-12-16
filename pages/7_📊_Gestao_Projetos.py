import streamlit as st
import pandas as pd
import utils_chamados
import time
import io
from datetime import date

st.set_page_config(page_title="Gestão de Projetos", page_icon="🏗️", layout="wide")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
        .stExpander { border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .block-container { padding-top: 2rem; }
        div[data-testid="stDialog"] { width: 70vw; } /* Pop-up mais largo */
    </style>
""", unsafe_allow_html=True)

# --- CONTROLE DE LOGIN ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- FUNÇÕES AUXILIARES ---
def _to_date_safe(val):
    if pd.isna(val) or val == "": return None
    try: return pd.to_datetime(val).date()
    except: return None

def calcular_status_projeto_agrupado(df_grupo):
    status_lista = df_grupo['Status'].dropna().str.lower().tolist()
    if not status_lista or all(s == 'não iniciado' for s in status_lista): return "Não Iniciado"
    if all(s in ['finalizado', 'concluído', 'cancelado'] for s in status_lista): return "Finalizado"
    if 'em andamento' in status_lista: return "Em Andamento"
    return "Em Andamento"

# --- 1. FUNÇÃO DE IMPORTAÇÃO (Mantida a correta) ---
@st.dialog("Importar Chamados", width="large")
def run_importer_dialog():
    st.info("Importação via Mapeamento de Colunas (Posição Fixa).")
    uploaded_files = st.file_uploader("Selecione arquivos (.xlsx ou .csv)", type=["xlsx", "csv"], accept_multiple_files=True, key="up_imp_full")

    if uploaded_files:
        dfs_list = []
        for uploaded_file in uploaded_files:
            try:
                if uploaded_file.name.endswith('.csv'):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', header=0, dtype=str, encoding='utf-8-sig')
                        if len(df.columns) < 5: 
                            uploaded_file.seek(0)
                            df = pd.read_csv(uploaded_file, sep=',', header=0, dtype=str, encoding='utf-8-sig')
                    except:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=None, engine='python', header=0, dtype=str)
                else:
                    df = pd.read_excel(uploaded_file, header=0, dtype=str)
                
                df.dropna(how='all', inplace=True)
                dfs_list.append(df)
            except Exception as e:
                st.error(f"Erro ao ler '{uploaded_file.name}': {e}")
                return

        if dfs_list:
            try:
                df_raw = pd.concat(dfs_list, ignore_index=True)
                if len(df_raw.columns) < 12: st.error("Arquivo com colunas insuficientes."); return

                # Mapeamento
                dados_mapeados = {
                    'Nº Chamado': df_raw.iloc[:, 0], 'Cód. Agência': df_raw.iloc[:, 1], 'Nome Agência': df_raw.iloc[:, 2],
                    'agencia_uf': df_raw.iloc[:, 3], 'Analista': df_raw.iloc[:, 22] if len(df_raw.columns) > 22 else "",
                    'Gestor': df_raw.iloc[:, 20] if len(df_raw.columns) > 20 else "", 'Serviço': df_raw.iloc[:, 4],
                    'Projeto': df_raw.iloc[:, 5], 'Agendamento': df_raw.iloc[:, 6], 
                    'Sistema': df_raw.iloc[:, 8], 
                    'Cod_equipamento': df_raw.iloc[:, 9], 'Nome_equipamento': df_raw.iloc[:, 10], 'Qtd': df_raw.iloc[:, 11]
                }
                df_final = pd.DataFrame(dados_mapeados).fillna("")

                # Formatação "5 - Câmera"
                def formatar_item(row):
                    qtd = str(row['Qtd']).strip()
                    desc = str(row['Nome_equipamento']).strip()
                    if not desc: desc = str(row['Sistema']).strip()
                    if not desc: return ""
                    if qtd and qtd not in ["0", "nan", "", "None"]: return f"{qtd} - {desc}" 
                    return desc

                df_final['Item_Formatado'] = df_final.apply(formatar_item, axis=1)

                def juntar_textos(lista):
                    limpos = [str(x) for x in lista if str(x).strip() not in ["", "nan", "None"]]
                    return " | ".join(dict.fromkeys(limpos))

                colunas_ignoradas_agg = ['Sistema', 'Qtd', 'Item_Formatado', 'Nome_equipamento', 'Cod_equipamento']
                regras = {c: 'first' for c in df_final.columns if c not in colunas_ignoradas_agg}
                regras['Sistema'] = 'first' 
                regras['Item_Formatado'] = juntar_textos 
                
                df_grouped = df_final.groupby('Nº Chamado', as_index=False).agg(regras)
                df_grouped['Equipamento'] = df_grouped['Item_Formatado']
                df_grouped['Descrição'] = df_grouped['Item_Formatado']

                # Separa Novos vs Existentes
                df_banco = utils_chamados.carregar_chamados_db()
                lista_novos = []; lista_atualizar = []
                
                if not df_banco.empty:
                    mapa_ids = dict(zip(df_banco['Nº Chamado'].astype(str).str.strip(), df_banco['ID']))
                    for row in df_grouped.to_dict('records'):
                        chamado_num = str(row['Nº Chamado']).strip()
                        if not chamado_num or chamado_num.lower() == 'nan': continue
                        if chamado_num in mapa_ids:
                            row['ID_Banco'] = mapa_ids[chamado_num]
                            lista_atualizar.append(row)
                        else: lista_novos.append(row)
                else: lista_novos = [r for r in df_grouped.to_dict('records') if str(r['Nº Chamado']).strip()]

                df_insert = pd.DataFrame(lista_novos)
                df_update = pd.DataFrame(lista_atualizar)

                c1, c2 = st.columns(2)
                c1.metric("🆕 Criar Novos", len(df_insert))
                c2.metric("🔄 Atualizar Existentes", len(df_update))
                
                if st.button("🚀 Processar Importação"):
                    bar = st.progress(0); status_txt = st.empty()
                    
                    if not df_insert.empty:
                        status_txt.text("Inserindo novos...")
                        utils_chamados.bulk_insert_chamados_db(df_insert)
                    bar.progress(40)
                    
                    if not df_update.empty:
                        status_txt.text("Atualizando existentes...")
                        for row in df_update.to_dict('records'):
                            updates = {
                                'Sistema': row['Sistema'], 'Equipamento': row['Equipamento'], 'Descrição': row['Descrição'],
                                'Serviço': row['Serviço'], 'Projeto': row['Projeto'],
                                'Agendamento': row['Agendamento'], 'Analista': row['Analista'], 'Gestor': row['Gestor']
                            }
                            utils_chamados.atualizar_chamado_db(row['ID_Banco'], updates)
                    bar.progress(100); status_txt.text("Concluído!")
                    st.success("Importação finalizada!"); time.sleep(1.5)
                    st.cache_data.clear(); st.rerun()

            except Exception as e: st.error(f"Erro no processamento: {e}")

# --- 2. POP-UP (DIALOG) - É AQUI QUE ESTÁ O SEU FORMULÁRIO ANTIGO ---
@st.dialog("Detalhes Operacionais do Chamado", width="large")
def editar_chamado_dialog(row_dict, id_chamado):
    row = pd.Series(row_dict)
    form_key = f"pop_{id_chamado}"
    
    st.markdown(f"### 🎫 {row.get('Nº Chamado')}")
    st.caption(f"Projeto: {row.get('Projeto')} | Agência: {row.get('Nome Agência')}")
    
    # --- CARREGAMENTO DE LISTAS (Igual ao código antigo) ---
    try:
        df_pj = utils_chamados.carregar_config_db("projetos_nomes"); lst_pj = [str(x) for x in df_pj.iloc[:,0].dropna().tolist()] if not df_pj.empty else []
        df_tc = utils_chamados.carregar_config_db("tecnicos"); lst_tc = [str(x) for x in df_tc.iloc[:,0].dropna().tolist()] if not df_tc.empty else []
        df_us = utils_chamados.carregar_usuarios_db(); df_us.columns = [c.capitalize() for c in df_us.columns] if not df_us.empty else []
        lst_an = [str(x) for x in df_us["Nome"].dropna().tolist()] if not df_us.empty and "Nome" in df_us.columns else []
    except: lst_pj=[]; lst_tc=[]; lst_an=[]
    
    def sf(v): return str(v) if pd.notna(v) and str(v).lower() not in ['nan', 'none', ''] else ""
    st_atual = row.get('Status', 'Não Iniciado')

    l_st_manual = ["Pendência de Infra", "Pendência de Equipamento", "Cancelado", "Pausado"]
    is_manual_mode = st_atual in l_st_manual
    
    lista_opcoes = ["🔄 STATUS AUTOMATICO"] + l_st_manual
    if st_atual not in lista_opcoes: lista_opcoes.append(st_atual)
    idx_inicial = lista_opcoes.index(st_atual) if st_atual in lista_opcoes else 0

    v_pj = sf(row.get('Projeto', '')); l_pj = sorted(list(set(lst_pj + [v_pj]))); i_pj = l_pj.index(v_pj) if v_pj in l_pj else 0
    v_tc = sf(row.get('Técnico', '')); l_tc = sorted(list(set(lst_tc + [v_tc]))); i_tc = l_tc.index(v_tc) if v_tc in l_tc else 0
    v_an = sf(row.get('Analista', '')); l_an = sorted(list(set(lst_an + [v_an]))); i_an = l_an.index(v_an) if v_an in l_an else 0

    n_chamado_str = str(row.get('Nº Chamado', ''))
    is_equip = '-e-' in n_chamado_str.lower()
    is_fin_banco = str(row.get('chk_financeiro_banco', '')).upper() == 'TRUE'
    is_fin_book = str(row.get('chk_financeiro_book', '')).upper() == 'TRUE'
    is_financeiro_locked = is_fin_banco or is_fin_book

    with st.form(key=form_key):
        # LINHA 1: STATUS E DATAS
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            if is_financeiro_locked:
                st.markdown(f"<small style='color:#666'>Status (Financeiro)</small><br><b style='color:#2E7D32'>{st_atual}</b>", unsafe_allow_html=True)
                n_st = st_atual
            else:
                n_st = st.selectbox("Status", lista_opcoes, index=idx_inicial, key=f"st_{form_key}")
                if is_manual_mode: st.caption("✋ Modo Manual")
                elif n_st == "🔄 STATUS AUTOMATICO": st.caption("🚀 Ação: Recalcular")

        n_ab = k2.date_input("Abertura", value=_to_date_safe(row.get('Abertura')) or date.today(), format="DD/MM/YYYY", key=f"ab_{form_key}")
        n_ag = k3.date_input("Agendamento", value=_to_date_safe(row.get('Agendamento')), format="DD/MM/YYYY", key=f"ag_{form_key}")
        n_fi = k4.date_input("Finalização", value=_to_date_safe(row.get('Fechamento')), format="DD/MM/YYYY", key=f"fi_{form_key}")

        # LINHA 2: PESSOAS
        k5, k6, k7 = st.columns(3)
        n_an = k5.selectbox("Analista", l_an, index=i_an, key=f"an_{form_key}")
        n_ge = k6.text_input("Gestor", value=row.get('Gestor', ''), key=f"ge_{form_key}")
        n_tc = k7.selectbox("Técnico", l_tc, index=i_tc, key=f"tc_{form_key}")

        # LINHA 3: PROJETO E SISTEMA
        k8, k9, k10 = st.columns(3)
        n_pj = k8.selectbox("Projeto", l_pj, index=i_pj, key=f"pj_{form_key}")
        n_sv = k9.text_input("Serviço", value=row.get('Serviço', ''), key=f"sv_{form_key}")
        n_si = k10.text_input("Sistema", value=row.get('Sistema', ''), key=f"si_{form_key}")

        n_ob = st.text_area("Observações", value=row.get('Observações e Pendencias', ''), height=80, key=f"ob_{form_key}")

        st.markdown("---")
        # LINHA 4: LINKS E PROTOCOLO
        val_chk_cli = str(row.get('chk_status_enviado', '')).upper() == 'TRUE'
        val_chk_ent = str(row.get('chk_equipamento_entregue', '')).upper() == 'TRUE'
        n_lk = row.get('Link Externo', '')
        n_pt = row.get('Nº Protocolo', '')
        n_pedido = row.get('Nº Pedido', '')
        n_envio = _to_date_safe(row.get('Data Envio'))
        ret_chk_cli = val_chk_cli; ret_chk_ent = val_chk_ent

        if is_equip:
            c_e1, c_e2, c_e3, c_e4 = st.columns([1, 1.5, 1.5, 2])
            with c_e1: st.text_input("Nº Chamado", value=n_chamado_str, disabled=True, key=f"nc_{form_key}")
            n_pedido = c_e2.text_input("📦 Nº Pedido", value=n_pedido, key=f"ped_{form_key}")
            n_envio = c_e3.date_input("🚚 Data Envio", value=n_envio, format="DD/MM/YYYY", key=f"env_{form_key}")
            with c_e4:
                # Regra visual simples para checkbox
                st.markdown("<br>", unsafe_allow_html=True)
                ret_chk_ent = st.checkbox("✅ EQUIPAMENTO ENTREGUE", value=val_chk_ent, key=f"chk_ent_{form_key}")
        else:
            c_s1, c_s2, c_s3, c_s4 = st.columns([1, 2, 1.5, 1.5])
            with c_s1:
                has_link = n_lk and str(n_lk).strip().lower() not in ['nan', 'none', '']
                if has_link:
                    st.markdown("<small>Nº Chamado</small>", unsafe_allow_html=True)
                    st.markdown(f"<a href='{n_lk}' target='_blank' style='display:block; background:#E3F2FD; color:#1565C0; padding:6px; border-radius:5px; text-align:center; text-decoration:none; font-weight:bold;'>🔗 Link</a>", unsafe_allow_html=True)
                else: st.text_input("Nº Chamado", value=n_chamado_str, disabled=True, key=f"nc_{form_key}")
            n_lk = c_s2.text_input("Link", value=n_lk, key=f"lk_{form_key}")
            n_pt = c_s3.text_input("Protocolo", value=n_pt, key=f"pt_{form_key}")
            with c_s4:
                st.markdown("<br>", unsafe_allow_html=True)
                ret_chk_cli = st.checkbox("✅ STATUS ENVIADO", value=val_chk_cli, key=f"chk_cli_{form_key}")

        # ÁREA DOS ITENS
        st.markdown("---")
        itens_salvos = str(row.get('Equipamento', '')).strip()
        if not itens_salvos or itens_salvos.lower() in ['nan', 'none', '']: itens_salvos = str(row.get('Descrição', '')).strip()
        
        desc = itens_salvos.replace("|", "<br>").replace(" | ", "<br>") if itens_salvos and itens_salvos.lower() not in ['nan', 'none', ''] else "Sem itens registrados."
        
        st.caption("Itens/Descrição:")
        st.markdown(f"<div style='background:#f9f9f9; padding:10px; border-radius:4px;'>{desc}</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # BOTÃO SALVAR (MANTENDO A ESTRUTURA ORIGINAL)
        if st.form_submit_button("💾 Salvar Alterações deste Chamado"):
            if n_st == "Cancelado" and n_fi is None: st.error("⛔ ERRO: DATA DE FINALIZAÇÃO OBRIGATÓRIA!"); st.stop()

            upds = {
                "Data Abertura": n_ab, "Data Agendamento": n_ag, "Data Finalização": n_fi,
                "Analista": n_an, "Gestor": n_ge, "Técnico": n_tc, "Projeto": n_pj,
                "Serviço": n_sv, "Sistema": n_si, "Observações e Pendencias": n_ob,
                "Link Externo": n_lk, "Nº Protocolo": n_pt, "Nº Pedido": n_pedido, "Data Envio": n_envio,
                "chk_status_enviado": "TRUE" if ret_chk_cli else "FALSE",
                "chk_equipamento_entregue": "TRUE" if ret_chk_ent else "FALSE"
            }
            
            # Lógica Imediata
            if ret_chk_cli and not val_chk_cli: upds["Status"] = "Concluído"; upds["Sub-Status"] = "Enviar Book"
            elif ret_chk_ent and not val_chk_ent: upds["Status"] = "Concluído"; upds["Sub-Status"] = "Aguardando Faturamento"
            elif not is_equip and n_tc and str(n_tc) != "" and str(n_tc) != str(v_tc):
                if has_link: upds["Status"] = "Em Andamento"; upds["Sub-Status"] = "Enviar Status Cliente"
                else: upds["Status"] = "Em Andamento"; upds["Sub-Status"] = "Acionar técnico"
            elif n_st == "🔄 STATUS AUTOMATICO": upds["Status"] = "Não Iniciado"; upds["Sub-Status"] = ""
            elif not is_financeiro_locked and n_st in l_st_manual: upds["Status"] = n_st

            if utils_chamados.atualizar_chamado_db(id_chamado, upds):
                st.success("Chamado atualizado!"); time.sleep(0.5); st.rerun()
            else: st.error("Erro ao salvar.")

# --- 3. CARREGAMENTO E SIDEBAR ---
df = utils_chamados.carregar_chamados_db()

with st.sidebar:
    st.header("Ações")
    if st.button("➕ Importar Chamados"): run_importer_dialog()
    st.divider()
    st.header("📤 Exportação")
    if st.button("📥 Baixar Base (.xlsx)"):
        df_export = utils_chamados.carregar_chamados_db()
        if not df_export.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_export.to_excel(writer, index=False, sheet_name='Base')
            st.download_button("Salvar Excel", data=output.getvalue(), file_name=f"Backup_{date.today()}.xlsx")
        else: st.warning("Banco vazio.")

    st.header("Filtros")
    lista_analistas = ["Todos"] + sorted(df['Analista'].dropna().unique().tolist())
    filtro_analista = st.selectbox("Filtrar por Analista", lista_analistas)

if df.empty:
    st.warning("Sem dados. Importe chamados na barra lateral."); st.stop()

# --- 4. LISTAGEM PRINCIPAL (AGRUPADA POR AGÊNCIA/PROJETO) ---
df_view = df.copy()
if filtro_analista != "Todos": df_view = df_view[df_view['Analista'] == filtro_analista]

# Cria a chave de agrupamento visual
df_view['Agencia_Fmt'] = df_view.apply(lambda x: f"{str(x['Cód. Agência']).split('.')[0]} - {x['Nome Agência']}", axis=1)
df_view['Projeto'] = df_view['Projeto'].fillna("Sem Projeto")

st.title("Gestão Operacional de Projetos")
st.markdown(f"<small>{len(df_view)} chamados encontrados</small>", unsafe_allow_html=True)

# Agrupa por Agência e Projeto (Isso cria o EXPANDER macro)
grupos = df_view.groupby(['Agencia_Fmt', 'Projeto'])

for (agencia, projeto), df_grupo in grupos:
    qtd_chamados = len(df_grupo)
    status_projeto = calcular_status_projeto_agrupado(df_grupo)
    
    # ID Visual do Projeto (Ex: AG5631-PROJETO)
    cod_ag = str(df_grupo.iloc[0]['Cód. Agência']).split('.')[0]
    id_projeto_visual = f"ID: {cod_ag}-{str(projeto)[:3].upper()}"

    cor_st = "grey"
    if status_projeto == "Em Andamento": cor_st = "blue"
    elif status_projeto == "Concluído": cor_st = "green"
    elif status_projeto == "Finalizado": cor_st = "darkgreen"

    # --- O EXPANDER AGORA É O GRUPO (PROJETO) ---
    label_expander = f"🏢 **{agencia}** | 📁 **{projeto}** | 🏷️ {id_projeto_visual} | {qtd_chamados} Chamados"
    
    with st.expander(label_expander, expanded=False):
        # Cabeçalho do Projeto
        c_p1, c_p2 = st.columns([2, 2])
        c_p1.markdown(f"**Status Projeto:** <span style='color:{cor_st}; font-weight:bold'>{status_projeto}</span>", unsafe_allow_html=True)
        st.divider()

        # Lista de Chamados DENTRO do projeto
        st.markdown("###### 🎫 Chamados deste Projeto:")
        
        # Cabeçalho da Lista
        cols = st.columns([1.5, 2, 2, 1.5, 2])
        cols[0].markdown("**ID Chamado**")
        cols[1].markdown("**Serviço**")
        cols[2].markdown("**Sistema**")
        cols[3].markdown("**Status**")
        cols[4].markdown("**Ação**")

        for _, row_chamado in df_grupo.iterrows():
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.5, 2, 2, 1.5, 2])
            
            num_chamado = row_chamado['Nº Chamado']
            cc1.markdown(f"**{num_chamado}**")
            cc2.caption(f"{row_chamado.get('Serviço', '-')}")
            cc3.caption(f"{row_chamado.get('Sistema', '-')}")
            
            st_ch = row_chamado.get('Status', '-')
            cor_badge = "grey"
            if st_ch == "Concluído": cor_badge = "green"
            elif st_ch == "Em Andamento": cor_badge = "blue"
            
            cc4.markdown(f":{cor_badge}[{st_ch}]")
            
            # --- BOTÃO QUE ABRE O POP-UP ---
            if cc5.button("✏️ Editar/Detalhes", key=f"btn_{row_chamado['ID']}"):
                editar_chamado_dialog(row_chamado.to_dict(), row_chamado['ID'])
        
        st.markdown("<br>", unsafe_allow_html=True)
