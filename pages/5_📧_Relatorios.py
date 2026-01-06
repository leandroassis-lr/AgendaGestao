import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import utils
import utils_chamados
import html

st.set_page_config(page_title="Relatórios - GESTÃO", page_icon="📧", layout="wide")
utils.load_css()

# --- FUNÇÃO ENVIAR EMAIL (Padrão) ---
def enviar_email(destinatario, assunto, corpo_html):
    """Envia um email usando as credenciais dos Secrets."""
    try:
        email_config = st.secrets["email"]
        remetente = email_config["user"]
        senha = email_config["password"]
        smtp_server = email_config["smtp_server"]
        smtp_port = email_config["smtp_port"]
        
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(remetente, senha)
            server.send_message(msg)
        return True, "Email enviado com sucesso!"
    except KeyError:
        return False, "Erro: Credenciais de email não configuradas nos 'Secrets'."
    except Exception as e:
        return False, f"Erro ao enviar email: {e}"

# --- 1. FUNÇÃO DE ESTILO (Adaptada) ---
def formatar_df_para_html(df, titulo, hoje):
    if df.empty:
        return f"<h4 style='color:#34495E; font-family: Arial, sans-serif;'>{titulo}</h4><p style='font-family:Arial, sans-serif; color: #555;'>Nenhum chamado encontrado.</p>"

    # Cores
    cor_header_bg = "#1565C0"      # Azul (Identidade da Pág 7)
    cor_header_texto = "#FFFFFF"
    cor_borda_header = "#0D47A1"
    cor_linha_par = "#f3f3f3"
    cor_linha_impar = "#ffffff"
    cor_borda_linha = "#dddddd"
    cor_titulo_h4 = "#34495E"
    familia_fonte = "'Arial', sans-serif"
    
    cor_texto_critico = "#D32F2F"

    html_output = f"<h4 style='color:{cor_titulo_h4}; font-family: {familia_fonte};'>{titulo}</h4>"
    html_output += f"""<table style='border-collapse: collapse; width: 100%; font-family: {familia_fonte}; font-size: 0.85em; min-width: 600px; box-shadow: 0 0 10px rgba(0,0,0,0.1);'>"""
    
    # Cabeçalho
    html_output += "<thead><tr>"
    for col in df.columns:
        html_output += f"<th style='background-color: {cor_header_bg}; color: {cor_header_texto}; text-align: left; padding: 10px; border-bottom: 2px solid {cor_borda_header};'>{html.escape(str(col))}</th>"
    html_output += "</tr></thead><tbody>"
    
    # Linhas
    for i, row in df.iterrows():
        current_row_style = cor_linha_par if i % 2 == 0 else cor_linha_impar
        html_output += f"<tr style='background-color: {current_row_style};'>"
        
        for col in df.columns:
            val = row[col]
            display_val = html.escape(str(val)) if pd.notna(val) and val is not None else ""
            
            cell_style = f"padding: 10px; text-align: left; border-bottom: 1px solid {cor_borda_linha};"
            
            # Destaques Condicionais
            if col == 'Aging (Dias)' and isinstance(val, (int, float)) and val > 15:
                cell_style += f" color: {cor_texto_critico}; font-weight: bold;"
            
            if col == 'Agendamento' and val == hoje.strftime('%d/%m/%Y'):
                 cell_style += f" color: {cor_texto_critico}; font-weight: bold;"

            html_output += f"<td style='{cell_style}'>{display_val}</td>"
        html_output += "</tr>"
    
    html_output += "</tbody></table><br>" 
    return html_output

# --- 2. TELA DE RELATÓRIOS ---
def tela_relatorios():
    st.markdown("<div class='section-title-center'>RELATÓRIOS POR EMAIL</div>", unsafe_allow_html=True)
    st.info("Gere e envie um relatório por analista baseado na base da Gestão de Projetos (Página 7).")

    destinatario_default = st.session_state.get('usuario_email', '') 
    
    destinatarios_input = st.text_area(
        "Enviar para o(s) email(s):", 
        value=destinatario_default,
        placeholder="Separe múltiplos emails por vírgula (,)",
        height=70
    )

    if st.button("🚀 Gerar e Enviar Relatório Diário", use_container_width=True):
        
        # Validação de Emails
        if not destinatarios_input:
            st.error("Insira pelo menos um email."); return

        emails_limpos = [e.strip() for e in destinatarios_input.replace(';', ',').split(',') if '@' in e]
        if not emails_limpos:
            st.error("Nenhum email válido."); return
        
        destinatarios_finais = ", ".join(emails_limpos)
        st.toast(f"Enviando para: {destinatarios_finais}")

        with st.spinner("Processando dados da Gestão de Projetos..."):
            # 1. CARREGA DADOS DA PAG 7
            df = utils_chamados.carregar_chamados_db()
            
            if df.empty:
                st.error("Base de dados vazia."); return

            # 2. TRATAMENTO DE DATAS E COLUNAS
            hoje = date.today()
            
            # Converte colunas vitais
            df['Agendamento'] = pd.to_datetime(df['Agendamento'], errors='coerce').dt.date
            df['Abertura'] = pd.to_datetime(df['Abertura'], errors='coerce').dt.date
            
            # Preenche Analista Vazio
            if 'Analista' not in df.columns: df['Analista'] = 'Não Definido'
            df['Analista'] = df['Analista'].fillna('Sem Analista')

            # Cálculo do Aging (Baseado na Abertura)
            df['Aging (Dias)'] = (hoje - df['Abertura']).apply(lambda x: x.days if pd.notna(x) else 0).astype(int)
            
            # 3. FILTROS (Vencidos vs Próxima Semana)
            proxima_segunda = hoje + timedelta(days=(7 - hoje.weekday()))
            status_fim = ["finalizado", "concluído", "faturado", "fechado", "cancelado"]
            
            # Backlog (Sem data de agendamento e não finalizado)
            df_backlog = df[
                (pd.isna(df['Agendamento'])) & 
                (~df['Status'].str.lower().isin(status_fim))
            ]

            # Vencidos (Data < Hoje e não finalizado)
            df_vencidos = df[
                (df['Agendamento'] < hoje) & 
                (~df['Status'].str.lower().isin(status_fim))
            ].copy()
            
            # Próxima Semana (Hoje <= Data <= Prox Segunda)
            df_proxima_semana = df[
                (df['Agendamento'] >= hoje) & 
                (df['Agendamento'] <= proxima_segunda)
            ].copy()
            
            # Lista de Analistas envolvidos
            lista_analistas = sorted(pd.concat([df_vencidos['Analista'], df_proxima_semana['Analista']]).unique())
            
            # DEFINIÇÃO DAS COLUNAS DO RELATÓRIO (Nomes da Pag 7)
            colunas_relatorio = ['Nº Chamado', 'Projeto', 'Nome Agência', 'Agendamento', 'Status', 'Aging (Dias)']

            # 4. GERAÇÃO DO HTML
            familia_fonte_segura = "'Arial', sans-serif" 
            
            kpi_html = f"""
            <h3 style="color: #2C3E50; font-family: {familia_fonte_segura};">Resumo Geral da Operação</h3>
            <table style="font-family: {familia_fonte_segura}; width: 100%; border-collapse: collapse; border: 1px solid #ddd;">
                <tr style="background-color: #f9f9f9;"><td style="padding: 10px;">🚨 Chamados Vencidos:</td><td style="padding: 10px; font-weight: bold; color: #D32F2F; text-align: right;">{len(df_vencidos)}</td></tr>
                <tr><td style="padding: 10px;">🗓️ Agendados (Semana):</td><td style="padding: 10px; font-weight: bold; text-align: right;">{len(df_proxima_semana)}</td></tr>
                <tr style="background-color: #f9f9f9;"><td style="padding: 10px;">🗃️ Backlog (Sem Data):</td><td style="padding: 10px; font-weight: bold; text-align: right;">{len(df_backlog)}</td></tr>
            </table><br>
            """
            
            corpo_html = f"""
            <html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head>
            <body style="font-family: {familia_fonte_segura}; line-height: 1.6;">
                <h2 style="color: #1565C0; border-bottom: 2px solid #1565C0;">
                    Relatório de Gestão - {hoje.strftime('%d/%m/%Y')}
                </h2>{kpi_html} 
            """
            
            if not lista_analistas: corpo_html += "<p>Sem pendências críticas ou agendamentos próximos.</p>"
            
            for analista in lista_analistas:
                analista_html = html.escape(str(analista))
                corpo_html += f"<hr><h3 style='background-color: #E3F2FD; padding: 10px; border-radius: 4px; color: #0D47A1;'>👤 {analista_html}</h3>"
                
                # Prepara DF Vencidos
                df_v_html = df_vencidos[df_vencidos['Analista'] == analista].copy()
                if not df_v_html.empty:
                    df_v_html = df_v_html[colunas_relatorio]
                    df_v_html['Agendamento'] = df_v_html['Agendamento'].apply(lambda x: x.strftime('%d/%m/%Y') if x else '-')
                    corpo_html += formatar_df_para_html(df_v_html, f"🚨 Vencidos ({len(df_v_html)})", hoje)
                
                # Prepara DF Semana
                df_p_html = df_proxima_semana[df_proxima_semana['Analista'] == analista].copy()
                if not df_p_html.empty:
                    df_p_html = df_p_html[colunas_relatorio]
                    df_p_html['Agendamento'] = df_p_html['Agendamento'].apply(lambda x: x.strftime('%d/%m/%Y') if x else '-')
                    corpo_html += formatar_df_para_html(df_p_html, f"🗓️ Próximos Agendamentos ({len(df_p_html)})", hoje)
            
            corpo_html += "<br><p style='color: #777; font-size: 0.8em;'><em>Gerado automaticamente pelo Sistema de Gestão.</em></p></body></html>"

            # 5. ENVIO
            sucesso, mensagem = enviar_email(destinatarios_finais, f"Relatório Gestão - {hoje.strftime('%d/%m/%Y')}", corpo_html)

            if sucesso:
                st.success(mensagem); st.balloons()
            else:
                st.error(mensagem)

# --- Controle Principal ---
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("Faça login na página principal.")
    st.stop()

tela_relatorios()

