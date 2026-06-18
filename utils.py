import pandas as pd
import io
import streamlit as st
from sqlalchemy import inspect

def export_to_excel(df, filename="export.xlsx"):
    output = io.BytesIO()
    # Remove a linha de total se existir antes de exportar
    df_export = df.copy()
    if not df_export.empty:
        for col in df_export.columns:
            if (df_export[col] == "TOTAL").any():
                df_export = df_export[df_export[col] != "TOTAL"]
                break
            
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def format_volume(x):
    if pd.isna(x) or x == "" or str(x).strip().upper() == "TOTAL": return x
    try:
        val = float(x)
        return f"{val:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def format_valor(x):
    if pd.isna(x) or x == "" or str(x).strip().upper() == "TOTAL": return x
    try:
        val = float(x)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return x

def get_model_column_config(model_class):
    config = {}
    mapper = inspect(model_class)
    for attr in mapper.column_attrs:
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
                is_id = label.lower() == 'id' or label.lower().startswith('id ') or label.lower().endswith(' id')
                config[label] = st.column_config.NumberColumn(
                    label=label,
                    format="%d" if is_id else info.get('format', 'localized'),
                    step=1 if is_id else info.get('step', 0.01),
                    disabled=disabled
                )
            elif col_type == 'date':
                config[label] = st.column_config.DateColumn(
                    label=label,
                    format="DD/MM/YYYY",
                    disabled=disabled
                )
            else:
                config[label] = st.column_config.TextColumn(
                    label=label,
                    disabled=disabled
                )
    return config

def build_df_from_model(query_results, model_class):
    if not query_results:
        return pd.DataFrame()
        
    mapper = inspect(model_class)
    data = []
    for row in query_results:
        row_dict = {}
        for attr in mapper.column_attrs:
            sa_col = attr.columns[0]
            label = sa_col.info.get('label', attr.key)
            if not sa_col.info.get('hidden'):
                val = getattr(row, attr.key)
                row_dict[label] = val
        data.append(row_dict)
    return pd.DataFrame(data)

def format_dataframe(df):
    """
    Centraliza a formatação brasileira (1.234,56) para tabelas de LEITURA.
    Retorna um objeto Styler do Pandas.
    """
    if df.empty: return df
    
    # Se já for um styler, extrai o dado original (Styler tem atributo .data)
    # Se for DataFrame, usa ele mesmo
    df_raw = df.data.copy() if hasattr(df, 'data') and not isinstance(df, pd.DataFrame) else df.copy()

    format_dict = {}
    kw_money = ['custo', 'frete', 'valor', 'r$', 'total (r$)']
    kw_volume = ['ton', 'sc', 'quantidade', 'estoque', 'capacidade', 'esmagamento', 'recebimento', 'vendas', 'produtor', 'esmagado', 'excedente', 'envio']
    
    for col in df_raw.columns:
        col_lower = str(col).lower()
        is_id = col_lower == 'id' or col_lower.startswith('id ') or col_lower.endswith(' id')
        
        # Só formata se a coluna for numérica ou contiver números
        if df_raw[col].dtype in ['float64', 'int64']:
            if is_id:
                format_dict[col] = lambda x: f"{int(x)}" if pd.notna(x) and str(x).strip().upper() != "TOTAL" else x
            elif any(k in col_lower for k in kw_money):
                format_dict[col] = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else ""
            elif any(k in col_lower for k in kw_volume):
                format_dict[col] = lambda x: f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else ""
            else:
                format_dict[col] = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else ""
        else:
            # Tenta converter colunas object que deveriam ser numéricas
            try:
                temp_numeric = pd.to_numeric(df_raw[col], errors='coerce')
                if temp_numeric.notna().any():
                     if any(k in col_lower for k in kw_money):
                        format_dict[col] = lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) and x != "" else x
                     elif any(k in col_lower for k in kw_volume):
                        format_dict[col] = lambda x: f"{float(x):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) and x != "" else x
            except (ValueError, TypeError):
                pass

    return df_raw.style.format(format_dict, na_rep="")

def append_totals_row(df):
    """
    Adiciona uma linha de TOTAL ao final do DataFrame.
    Garante que colunas sejam compatíveis com Arrow para evitar avisos.
    """
    if df.empty: return df
    
    df_temp = df.copy()
    totals = {}
    label_col = None
    
    # Achar coluna de texto para colocar o label TOTAL
    for col in df_temp.columns:
        if pd.api.types.is_object_dtype(df_temp[col]) or pd.api.types.is_string_dtype(df_temp[col]):
            label_col = col
            break
    if not label_col: label_col = df_temp.columns[0]

    for col in df_temp.columns:
        col_norm = str(col).strip().lower()
        
        # Filtros de exclusão
        is_id = col_norm == 'id' or col_norm.startswith('id ') or col_norm.endswith(' id')
        is_unit = '/ton' in col_norm or 'unitário' in col_norm or 'unitario' in col_norm or 'frete ton' in col_norm
        is_dist = 'distância' in col_norm or 'distancia' in col_norm or '(km)' in col_norm
        is_stock = 'saldo estoque' in col_norm
        
        # Filtros de inclusão
        kw_sum = ['capacidade', 'estática', 'estatica', 'esmagamento', 'recebimento', 'vendas', 'produtor', 'ton', 'sc', 'quantidade', 'total', 'esmagado', 'estoque', 'excedente', 'envio']
        
        should_sum = (any(k in col_norm for k in kw_sum) or 'r$' in col_norm) and not is_id and not is_unit and not is_dist and not is_stock
        
        if should_sum:
            try:
                def to_num(v):
                    if pd.isna(v) or v == "" or str(v).strip().upper() == "TOTAL": return 0.0
                    if isinstance(v, (int, float)): return float(v)
                    s = str(v).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                    try: return float(s)
                    except: return 0.0
                
                totals[col] = df_temp[col].apply(to_num).sum()
            except: totals[col] = 0.0
        elif col == label_col:
            totals[col] = "TOTAL"
        else:
            # Usar o valor nulo compatível com o tipo da coluna para evitar erros de Arrow
            if pd.api.types.is_numeric_dtype(df_temp[col]):
                totals[col] = float('nan')
            elif pd.api.types.is_datetime64_any_dtype(df_temp[col]):
                totals[col] = pd.NaT
            else:
                totals[col] = ""

    # Garante que a linha de total tenha as mesmas colunas na ordem correta
    row_total = pd.DataFrame([totals])[df_temp.columns]
    
    df_final = pd.concat([df_temp, row_total], ignore_index=True)
    return df_final
