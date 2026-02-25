import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Análise de Safras - Portfel", layout="wide")

@st.cache_data
def load_and_prepare_data(uploaded_file):
    # Carrega a base a partir do arquivo upado pelo usuário
    df = pd.read_csv(uploaded_file)
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    
    # Ordena cronologicamente para consistência
    df = df.sort_values(by=['E-mail', 'Data'])
    
    # Agregação para consolidar o "perfil final" de cada consultor
    df_agg = df.groupby('E-mail').agg({
        'Turma': 'first',
        'MF': lambda x: 'Sim' if 'Sim' in x.values else 'Não',
        # min() alfabético: 'A' é menor que 'B', logo traz a curva mais alta atingida
        'Curva AuC': 'min', 
        'Status': lambda x: 'Desligado' if 'Desligado' in x.values else 'Ativo'
    }).reset_index()
    
    df_agg = df_agg.rename(columns={'Curva AuC': 'Curva AuC Máxima'})
    return df_agg

def main():
    st.title("📊 Análise de Safras (Cohorts) - Consultores")
    st.markdown("Faça o upload da base unificada para visualizar o desempenho e a retenção.")
    
    # Widget para upload do arquivo CSV
    uploaded_file = st.file_uploader("Suba o arquivo Base_Unificada_Portfel_Limpa.csv", type=['csv'])
    
    if uploaded_file is None:
        st.info("Aguardando o upload do arquivo CSV para iniciar a análise.")
        return

    try:
        # Lê e prepara os dados usando a função em cache
        df = load_and_prepare_data(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao processar os dados. Verifique se o formato do CSV está correto. Detalhe: {e}")
        return

    st.sidebar.header("Filtros de Análise")
    
    # Novo controle: Nível de Análise
    visao = st.sidebar.radio(
        "Selecione o Nível de Análise:",
        options=["Visão Geral (Todas as Safras)", "Visão Por Safra"]
    )
    
    if visao == "Visão Por Safra":
        # Identifica as turmas disponíveis
        turmas_disponiveis = sorted(df['Turma'].unique().tolist())
        
        # Controle para o usuário selecionar as safras
        turmas_selecionadas = st.sidebar.multiselect(
            "Selecione as Safras (Turmas):",
            options=turmas_disponiveis,
            default=turmas_disponiveis[:5] 
        )
        
        if not turmas_selecionadas:
            st.warning("👈 Por favor, selecione ao menos uma Turma no menu lateral.")
            return
            
        df_filtered = df[df['Turma'].isin(turmas_selecionadas)].copy()
        ordem_x = [str(t) for t in turmas_selecionadas]
        eixo_x_titulo = "Turma (Safra)"
        
    else:
        # VISÃO GERAL: Pega todo o dataframe e agrupa sob o rótulo "Geral"
        df_filtered = df.copy()
        df_filtered['Turma'] = "Geral" # Sobrescreve a turma para consolidar tudo
        ordem_x = ["Geral"]
        eixo_x_titulo = "Visão Consolidada"
    
    # =========================================================================
    # ANÁLISE 1: ÁPICE DA CURVA AuC (MF vs Não-MF)
    # =========================================================================
    st.header("1. Ápice da Curva AuC")
    st.markdown("Percentual de atingimento das curvas A, B, C e D em seu melhor momento. Gráficos separados por atingimento de MF.")
    
    df_curva_contagem = df_filtered.groupby(['Turma', 'MF', 'Curva AuC Máxima']).size().reset_index(name='Contagem')
    df_curva_total = df_filtered.groupby(['Turma', 'MF']).size().reset_index(name='Total')
    df_curva_pct = pd.merge(df_curva_contagem, df_curva_total, on=['Turma', 'MF'])
    
    df_curva_pct['Percentual (%)'] = (df_curva_pct['Contagem'] / df_curva_pct['Total']) * 100
    df_curva_pct['Percentual (%)'] = df_curva_pct['Percentual (%)'].round(2)
    df_curva_pct['Turma'] = df_curva_pct['Turma'].astype(str) 
    
    fig_curva = px.bar(
        df_curva_pct, 
        x='Turma', 
        y='Percentual (%)', 
        color='Curva AuC Máxima',
        facet_col='MF', 
        barmode='stack',
        text='Percentual (%)',
        color_discrete_map={'A': '#2ca02c', 'B': '#1f77b4', 'C': '#ff7f0e', 'D': '#d62728'},
        category_orders={
            "Curva AuC Máxima": ["A", "B", "C", "D"], 
            "Turma": ordem_x
        }
    )
    fig_curva.for_each_annotation(lambda a: a.update(text=a.text.replace("MF=", "Atingiu MF: ")))
    fig_curva.update_traces(textposition='inside', textfont_size=10)
    fig_curva.update_layout(yaxis_title="Percentual (%)", xaxis_title=eixo_x_titulo)
    
    st.plotly_chart(fig_curva, use_container_width=True)
    
    st.divider()

    # =========================================================================
    # ANÁLISE 2: DESLIGAMENTOS (MF vs Não-MF)
    # =========================================================================
    st.header("2. Percentual de Desligamentos (Churn)")
    st.markdown("Taxa de churn, comparando quem atingiu MF com quem não atingiu.")
    
    df_desligados = df_filtered[df_filtered['Status'] == 'Desligado'].groupby(['Turma', 'MF']).size().reset_index(name='Desligados')
    df_deslig_pct = pd.merge(df_curva_total, df_desligados, on=['Turma', 'MF'], how='left')
    df_deslig_pct['Desligados'] = df_deslig_pct['Desligados'].fillna(0)
    
    df_deslig_pct['Taxa de Desligamento (%)'] = (df_deslig_pct['Desligados'] / df_deslig_pct['Total']) * 100
    df_deslig_pct['Taxa de Desligamento (%)'] = df_deslig_pct['Taxa de Desligamento (%)'].round(2)
    df_deslig_pct['Turma'] = df_deslig_pct['Turma'].astype(str)
    
    fig_deslig = px.bar(
        df_deslig_pct,
        x='Turma',
        y='Taxa de Desligamento (%)',
        color='MF',
        barmode='group',
        text='Taxa de Desligamento (%)',
        color_discrete_map={'Sim': '#1f77b4', 'Não': '#ff7f0e'},
        category_orders={'Turma': ordem_x}
    )
    fig_deslig.update_traces(textposition='outside')
    fig_deslig.update_layout(yaxis_title="Percentual Desligado (%)", xaxis_title=eixo_x_titulo, yaxis=dict(range=[0, 110]))
    
    st.plotly_chart(fig_deslig, use_container_width=True)

if __name__ == "__main__":
    main()
