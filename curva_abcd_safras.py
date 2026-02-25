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
        'Curva Receita do Consultor': 'min', # NOVO: Captura o ápice da Receita
        'Status': lambda x: 'Desligado' if 'Desligado' in x.values else 'Ativo'
    }).reset_index()
    
    # Renomeando as categorias do MF para melhorar o UX
    mf_map = {
        'Sim': 'Profissionais de mercado financeiro (MF)',
        'Não': 'Profissionais em migração de carreira'
    }
    df_agg['MF'] = df_agg['MF'].map(mf_map)
    
    # Renomeando as colunas de curva para padronizar
    df_agg = df_agg.rename(columns={
        'Curva AuC': 'Curva AuC Máxima',
        'Curva Receita do Consultor': 'Curva Receita Máxima'
    })
    return df_agg

def main():
    st.title("📊 Análise de Safras (Cohorts) - Consultores")
    st.markdown("Faça o upload da base unificada (Master) para visualizar o desempenho (AuC e Receita) e a retenção.")
    
    # Widget para upload do arquivo CSV
    uploaded_file = st.file_uploader("Suba o arquivo CSV atualizado", type=['csv'])
    
    if uploaded_file is None:
        st.info("Aguardando o upload do arquivo CSV para iniciar a análise.")
        return

    try:
        df = load_and_prepare_data(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao processar os dados. Verifique se o formato do CSV está correto. Detalhe: {e}")
        return

    st.sidebar.header("Filtros de Análise")
    
    # Nível de Análise
    visao = st.sidebar.radio(
        "Selecione o Nível de Análise:",
        options=["Visão Geral (Todas as Safras)", "Visão Por Safra"]
    )
    
    if visao == "Visão Por Safra":
        turmas_disponiveis = sorted(df['Turma'].dropna().unique().tolist())
        
        # Opções de UX macro
        opcoes_especiais = [
            "Selecionar todas", 
            "Dados - FCE (Finclass)", 
            "Dados - Sem FCE (Finclass)"
        ]
        
        # Pega as 5 turmas mais recentes (maiores números)
        cinco_mais_recentes = turmas_disponiveis[-5:] if len(turmas_disponiveis) >= 5 else turmas_disponiveis
        
        # O seletor junta as opções em texto com os números das turmas
        selecao_raw = st.sidebar.multiselect(
            "Selecione as Safras (Turmas) ou um grupo:",
            options=opcoes_especiais + turmas_disponiveis,
            default=cinco_mais_recentes 
        )
        
        if not selecao_raw:
            st.warning("👈 Por favor, selecione ao menos uma Turma ou grupo no menu lateral.")
            return
            
        # Processa a seleção para traduzir os textos macro em números reais de turma
        turmas_selecionadas_set = set()
        for item in selecao_raw:
            if item == "Selecionar todas":
                turmas_selecionadas_set.update(turmas_disponiveis)
            elif item == "Dados - FCE (Finclass)":
                turmas_selecionadas_set.update([t for t in turmas_disponiveis if t >= 24])
            elif item == "Dados - Sem FCE (Finclass)":
                turmas_selecionadas_set.update([t for t in turmas_disponiveis if t < 24])
            else:
                turmas_selecionadas_set.add(item)
        
        turmas_selecionadas = sorted(list(turmas_selecionadas_set))
        
        df_filtered = df[df['Turma'].isin(turmas_selecionadas)].copy()
        ordem_x = [str(t) for t in turmas_selecionadas]
        eixo_x_titulo = "Turma (Safra)"
        
    else:
        # VISÃO GERAL
        df_filtered = df.copy()
        df_filtered['Turma'] = "Geral"
        ordem_x = ["Geral"]
        eixo_x_titulo = "Visão Consolidada"
    
    # Cor base para as curvas ABCD
    cores_curvas = {'A': '#2ca02c', 'B': '#1f77b4', 'C': '#ff7f0e', 'D': '#d62728'}
    
    # =========================================================================
    # ANÁLISE 1: ÁPICE DA CURVA AuC (MF vs Não-MF)
    # =========================================================================
    st.header("1. Ápice da Curva AuC")
    st.markdown("Percentual de atingimento das curvas A, B, C e D em seu melhor momento (AuC), segmentado pelo background do consultor.")
    
    df_auc_contagem = df_filtered.groupby(['Turma', 'MF', 'Curva AuC Máxima']).size().reset_index(name='Contagem')
    df_total = df_filtered.groupby(['Turma', 'MF']).size().reset_index(name='Total')
    df_auc_pct = pd.merge(df_auc_contagem, df_total, on=['Turma', 'MF'])
    
    df_auc_pct['Percentual (%)'] = (df_auc_pct['Contagem'] / df_auc_pct['Total']) * 100
    df_auc_pct['Percentual (%)'] = df_auc_pct['Percentual (%)'].round(1) 
    df_auc_pct['Turma'] = df_auc_pct['Turma'].astype(str) 
    
    fig_auc = px.bar(
        df_auc_pct, 
        x='Turma', 
        y='Percentual (%)', 
        color='Curva AuC Máxima',
        facet_col='MF', 
        barmode='stack',
        text='Percentual (%)',
        color_discrete_map=cores_curvas,
        category_orders={
            "Curva AuC Máxima": ["A", "B", "C", "D"], 
            "Turma": ordem_x,
            "MF": ["Profissionais de mercado financeiro (MF)", "Profissionais em migração de carreira"]
        },
        template="plotly_white",
        height=500
    )
    
    fig_auc.for_each_annotation(lambda a: a.update(text=f"<b>{a.text.split('=')[-1]}</b>", font=dict(size=14)))
    fig_auc.update_traces(texttemplate='%{text}%', textposition='inside', textfont_size=12, marker_line_color='black', marker_line_width=0.5)
    fig_auc.update_yaxes(title_text="Percentual (%)", showgrid=True, gridcolor='lightgray')
    fig_auc.update_xaxes(title_text=eixo_x_titulo)
    
    st.plotly_chart(fig_auc, use_container_width=True)
    
    st.divider()

    # =========================================================================
    # ANÁLISE 2: ÁPICE DA CURVA RECEITA (MF vs Não-MF)
    # =========================================================================
    st.header("2. Ápice da Curva de Receita")
    st.markdown("Percentual de atingimento das curvas A, B, C e D em seu melhor momento (Receita), segmentado pelo background do consultor.")
    
    df_receita_contagem = df_filtered.groupby(['Turma', 'MF', 'Curva Receita Máxima']).size().reset_index(name='Contagem')
    df_receita_pct = pd.merge(df_receita_contagem, df_total, on=['Turma', 'MF'])
    
    df_receita_pct['Percentual (%)'] = (df_receita_pct['Contagem'] / df_receita_pct['Total']) * 100
    df_receita_pct['Percentual (%)'] = df_receita_pct['Percentual (%)'].round(1) 
    df_receita_pct['Turma'] = df_receita_pct['Turma'].astype(str) 
    
    fig_rec = px.bar(
        df_receita_pct, 
        x='Turma', 
        y='Percentual (%)', 
        color='Curva Receita Máxima',
        facet_col='MF', 
        barmode='stack',
        text='Percentual (%)',
        color_discrete_map=cores_curvas,
        category_orders={
            "Curva Receita Máxima": ["A", "B", "C", "D"], 
            "Turma": ordem_x,
            "MF": ["Profissionais de mercado financeiro (MF)", "Profissionais em migração de carreira"]
        },
        template="plotly_white",
        height=500
    )
    
    fig_rec.for_each_annotation(lambda a: a.update(text=f"<b>{a.text.split('=')[-1]}</b>", font=dict(size=14)))
    fig_rec.update_traces(texttemplate='%{text}%', textposition='inside', textfont_size=12, marker_line_color='black', marker_line_width=0.5)
    fig_rec.update_yaxes(title_text="Percentual (%)", showgrid=True, gridcolor='lightgray')
    fig_rec.update_xaxes(title_text=eixo_x_titulo)
    
    st.plotly_chart(fig_rec, use_container_width=True)
    
    st.divider()

    # =========================================================================
    # ANÁLISE 3: DESLIGAMENTOS (MF vs Não-MF)
    # =========================================================================
    st.header("3. Percentual de Desligamentos (Churn)")
    st.markdown("Taxa de evasão de consultores, comparando os diferentes backgrounds profissionais.")
    
    df_desligados = df_filtered[df_filtered['Status'] == 'Desligado'].groupby(['Turma', 'MF']).size().reset_index(name='Desligados')
    df_deslig_pct = pd.merge(df_total, df_desligados, on=['Turma', 'MF'], how='left')
    df_deslig_pct['Desligados'] = df_deslig_pct['Desligados'].fillna(0)
    
    df_deslig_pct['Taxa de Desligamento (%)'] = (df_deslig_pct['Desligados'] / df_deslig_pct['Total']) * 100
    df_deslig_pct['Taxa de Desligamento (%)'] = df_deslig_pct['Taxa de Desligamento (%)'].round(1)
    df_deslig_pct['Turma'] = df_deslig_pct['Turma'].astype(str)
    
    fig_deslig = px.bar(
        df_deslig_pct,
        x='Turma',
        y='Taxa de Desligamento (%)',
        color='MF',
        barmode='group',
        text='Taxa de Desligamento (%)',
        color_discrete_map={
            'Profissionais de mercado financeiro (MF)': '#1f77b4', 
            'Profissionais em migração de carreira': '#ff7f0e'
        },
        category_orders={
            'Turma': ordem_x,
            'MF': ["Profissionais de mercado financeiro (MF)", "Profissionais em migração de carreira"]
        },
        template="plotly_white",
        height=550
    )
    
    fig_deslig.update_traces(
        texttemplate='%{text}%', 
        textposition='outside',
        textfont_size=12,
        marker_line_color='black',
        marker_line_width=0.5
    )
    
    fig_deslig.update_layout(
        yaxis_title="Percentual Desligado (%)", 
        xaxis_title=eixo_x_titulo, 
        yaxis=dict(range=[0, 115], showgrid=True, gridcolor='lightgray'),
        legend_title_text="",
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.02, 
            xanchor="center", 
            x=0.5
        )
    )
    
    st.plotly_chart(fig_deslig, use_container_width=True)

if __name__ == "__main__":
    main()
