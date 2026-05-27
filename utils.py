import pandas as pd
import io
import streamlit as st
from sqlalchemy import inspect

def export_to_excel(df, filename):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def format_volume(x):
    if pd.isna(x) or x == "": return ""
    try:
        val = float(x)
        # Formato brasileiro: Milhares com . e 2 decimais com ,
        return f"{val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def format_valor(x):
    if pd.isna(x) or x == "": return ""
    try:
        val = float(x)
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def get_model_column_config(model_class):
    """
    Inspeciona o modelo SQLAlchemy e extrai o column_config do Streamlit
    baseado no parâmetro 'info' definido nas colunas.
    """
    config = {}
    mapper = inspect(model_class)
    for attr in mapper.column_attrs:
        # Pega o objeto de coluna real do atributo
        sa_col = attr.columns[0]
        info = sa_col.info
        if info:
            label = info.get('label', attr.key)
            if info.get('hidden'):
                config[label] = None
                continue
                
            col_type = info.get('type', 'text')
            disabled = info.get('disabled', False)
            
            if col_type == 'number':
                config[label] = st.column_config.NumberColumn(
                    label=label,
                    format=info.get('format', '%,.2f'),
                    step=info.get('step', 0.01),
                    disabled=disabled
                )
            elif col_type == 'date':
                config[label] = st.column_config.DateColumn(
                    label=label,
                    format=info.get('format', 'DD/MM/YYYY'),
                    disabled=disabled
                )
            else:
                config[label] = st.column_config.TextColumn(
                    label=label,
                    disabled=disabled
                )
    return config

def build_df_from_model(query_results, model_class):
    """
    Transforma resultados de query em DataFrame usando as labels 
    definidas no 'info' do modelo.
    """
    if not query_results:
        return pd.DataFrame()
        
    mapper = inspect(model_class)
    data = []
    for row in query_results:
        row_dict = {}
        for attr in mapper.column_attrs:
            sa_col = attr.columns[0]
            label = sa_col.info.get('label', attr.key)
            # Ignora colunas escondidas no DataFrame base para não sobrecarregar
            if not sa_col.info.get('hidden'):
                val = getattr(row, attr.key)
                row_dict[label] = val
        data.append(row_dict)
    return pd.DataFrame(data)

def format_dataframe(df):
    """Aplica formatação visual brasileira (1.234,56) para tabelas de leitura."""
    df_styled = df.copy()
    format_dict = {}
    # Keywords para detecção automática (caso não venha do modelo)
    kw_num = ['ton', 'r$', 'custo', 'frete', 'valor', 'preço', 'quantidade', 'estoque', 'capacidade', 'recebimento', 'vendas', 'volume', 'distância', 'esmagado', 'excedente', 'envio', 'carga', 'caminhão', 'limite', 'inicial']
    
    for col in df_styled.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in kw_num):
            if any(m in col_lower for m in ['custo', 'frete', 'valor', 'r$']):
                format_dict[col] = format_valor
            else:
                format_dict[col] = format_volume
    
    if format_dict:
        actual_formats = {c: format_dict[c] for c in df_styled.columns if c in format_dict}
        return df_styled.style.format(actual_formats)
    return df_styled
