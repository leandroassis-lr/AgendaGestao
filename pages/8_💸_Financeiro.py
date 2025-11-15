import streamlit as st
import pandas as pd
import utils_chamados  # Para carregar os chamados
import utils_financeiro # Nosso novo arquivo
import re

st.set_page_config(page_title="Gestão Financeira", page_icon="💸", layout="wide")

# --- Controle de Login ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Por favor, faça o login na página principal (app.py) antes de acessar esta página.")
    st.stop()

# --- Criar Tabelas LPU (só executa se não existirem) ---
utils_financeiro.criar_tabelas_lpu()

st.markdown("<h1 style='text-align: center;'>Gestão Financeira (LPU)</h1>", unsafe_allow_html=True)
st.divider()

# --- 1. SEÇÃO DE IMPORTAÇÃO DA LPU ---
with st.expander("⚙️ Configurações e Importação da LPU"):
    st.info("Use esta seção para carregar ou atualizar a planilha de preços (LPU).")
    
    uploaded_lpu = st.file_uploader(
        "Selecione a planilha LPU (.xlsx)", 
        type=["xlsx"], 
        key="lpu_uploader"
    )
    
    if uploaded_lpu:
        try:
            with st.spinner("Lendo planilhas..."):
                # Lê todas as abas de uma vez
                xls = pd.read_excel(uploaded_lpu, sheet_name=None)
                
                # Pega cada aba (se existir)
                df_fixo = xls.get('Valores fixo', pd.DataFrame())
                df_servico = xls.get('Serviço', pd.DataFrame())
                df_equip = xls.get('Equipamento', pd.DataFrame())

                if df_fixo.empty and df_servico.empty and df_equip.empty:
                    st.error("Erro: Nenhuma aba válida ('Valores fixo', 'Serviço', 'Equipamento') foi encontrada no arquivo.")
                else:
                    st.success("Arquivo lido! Pré-visualização das abas:")
                    if not df_fixo.empty:
                        st.markdown("##### Valores Fixo")
                        st.dataframe(df_fixo.head(), use_container_width=True)
                    if not df_servico.empty:
                        st.markdown("##### Serviço (D/R)")
                        st.dataframe(df_servico.head(), use_container_width=True)
                    if not df_equip.empty:
                        st.markdown("##### Equipamento (Preço)")
                        st.dataframe(df_equip.head(), use_container_width=True)

                    if st.button("🚀 Importar/Atualizar LPU no Banco de Dados"):
                        with st.spinner("Importando LPU..."):
                            sucesso, msg = utils_financeiro.importar_lpu(df_fixo, df_servico, df_equip)
                            if sucesso:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
        
        except Exception as e:
            st.error(f"Erro ao processar o arquivo Excel: {e}")

st.divider()

# --- 2. SEÇÃO DE CÁLCULO E VISUALIZAÇÃO ---
st.markdown("### 💰 Cálculo de Valores por Chamado")

@st.cache_data(ttl=60)
def carregar_dados_completos():
    """Carrega chamados e todos os dicionários de preço."""
    df_chamados = utils_chamados.carregar_chamados_db()
    lpu_fixo = utils_financeiro.carregar_lpu_fixo()
    lpu_servico = utils_financeiro.carregar_lpu_servico()
    lpu_equip = utils_financeiro.carregar_lpu_equipamento()
    return df_chamados, lpu_fixo, lpu_servico, lpu_equip

def calcular_preco(row, lpu_fixo, lpu_servico, lpu_equip):
    """Lógica principal de cálculo de preço para uma linha (chamado)."""
    
    # Pega os dados da linha (chamado)
    servico_norm = str(row.get('Serviço', '')).strip().lower()
    equip_norm = str(row.get('Equipamento', '')).strip().lower()
    qtd = pd.to_numeric(row.get('Qtd.'), errors='coerce')

    # --- REGRA 1: Tentar por Valor Fixo (Chave: Serviço) ---
    # (Ex: "Vistoria")
    if servico_norm in lpu_fixo:
        return lpu_fixo[servico_norm] # Retorna o valor fixo, ignora Qtd

    # --- Se não for Fixo, é por Equipamento. Qtd padrão é 1 ---
    if pd.isna(qtd) or qtd == 0:
        qtd = 1
        
    # --- REGRA 2: Tentar por Serviço de Equipamento (Chave: Equipamento) ---
    # (Ex: "Desinstalação" ou "Reinstalação" de um "SENSOR...")
    if equip_norm in lpu_servico:
        precos_serv = lpu_servico[equip_norm]
        
        if 'desativação' in servico_norm or 'desinstalação' in servico_norm:
            return precos_serv.get('desativacao', 0.0) * qtd
            
        if 'reinstalação' in servico_norm or 'reinstalacao' in servico_norm:
            return precos_serv.get('reinstalacao', 0.0) * qtd

    # --- REGRA 3: Tentar por Preço de Equipamento (Chave: Equipamento) ---
    # (Ex: "Instalação" de um "SENSOR...")
    if equip_norm in lpu_equip:
        return lpu_equip.get(equip_norm, 0.0) * qtd
        
    # Se não encontrou nada
    return 0.0

# --- Execução Principal da Página ---
try:
    with st.spinner("Carregando chamados e LPU..."):
        df_chamados_raw, lpu_fixo, lpu_servico, lpu_equip = carregar_dados_completos()
    
    if df_chamados_raw.empty:
        st.warning("Nenhum chamado encontrado. Importe os chamados na página 'Dados por Agência'.")
        st.stop()
        
    if not lpu_fixo and not lpu_servico and not lpu_equip:
        st.warning("Nenhum preço (LPU) foi importado. Use o botão acima para importar a planilha LPU.")

    # --- Aplica o cálculo de preço a cada linha ---
    with st.spinner("Calculando valores..."):
        df_chamados_raw['Valor_Calculado'] = df_chamados_raw.apply(
            calcular_preco, 
            args=(lpu_fixo, lpu_servico, lpu_equip), 
            axis=1
        )

    # --- FILTROS (Copiados da Página 7) ---
    # (Aqui podemos adicionar filtros financeiros, se necessário)
    st.markdown("Filtros (Em breve)")
    # (Por enquanto, vamos mostrar tudo)
    df_filtrado = df_chamados_raw
    
    # --- KPIs FINANCEIROS ---
    valor_total_filtrado = df_filtrado['Valor_Calculado'].sum()
    
    kpi1, kpi2 = st.columns(2)
    kpi1.metric("Total de Chamados na Visão", len(df_filtrado))
    kpi2.metric("Valor Total Calculado (R$)", f"{valor_total_filtrado:,.2f}")
    
    st.divider()
    
    # --- VISUALIZAÇÃO DOS DADOS ---
    st.markdown("#### Detalhamento dos Chamados")
    
    # Colunas para exibir
    colunas_para_ver = [
        'Nº Chamado', 'Serviço', 'Equipamento', 'Qtd.', 'Valor_Calculado'
    ]
    # Adiciona colunas se existirem
    if 'Agencia_Combinada' in df_filtrado.columns:
        colunas_para_ver.insert(1, 'Agencia_Combinada')
    
    # Garante que só vamos tentar mostrar colunas que existem
    colunas_finais = [col for col in colunas_para_ver if col in df_filtrado.columns]
    
    df_display = df_filtrado[colunas_finais].copy()
    
    # Formatando a coluna de valor
    df_display['Valor_Calculado'] = df_display['Valor_Calculado'].map('R$ {:,.2f}'.format)
    
    st.dataframe(df_display, use_container_width=True)

except Exception as e:
    st.error(f"Ocorreu um erro ao gerar a página: {e}")