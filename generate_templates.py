import pandas as pd
import os

def generate_templates():
    if not os.path.exists('templates'):
        os.makedirs('templates')
        
    # Fábricas
    df_fabricas = pd.DataFrame(columns=[
        'nome', 'capacidade_estatica', 'capacidade_esmagamento_diaria', 
        'capacidade_recebimento_diaria', 'limite_caminhoes', 
        'carga_media_caminhao', 'estoque_inicial'
    ])
    df_fabricas.to_excel('templates/factories_template.xlsx', index=False)
    
    # Armazéns
    df_armazens = pd.DataFrame(columns=[
        'nome', 'capacidade_estatica', 'capacidade_expedicao_diaria', 'estoque_inicial'
    ])
    df_armazens.to_excel('templates/warehouses_template.xlsx', index=False)
    
    # Rotas
    df_rotas = pd.DataFrame(columns=[
        'origem', 'destino', 'distancia_km', 'custo_frete_ton'
    ])
    df_rotas.to_excel('templates/routes_template.xlsx', index=False)
    
    # Previsões
    df_previsoes = pd.DataFrame(columns=[
        'entidade', 'mes_referencia', 'recebimento_produtor', 'vendas', 'eh_safra'
    ])
    df_previsoes.to_excel('templates/daily_updates_template.xlsx', index=False)
    
    print("Templates gerados na pasta 'templates/'")

if __name__ == "__main__":
    generate_templates()
