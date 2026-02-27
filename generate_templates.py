import pandas as pd
import os

def generate_templates():
    os.makedirs('templates', exist_ok=True)
    
    # Factory Template
    df_factory = pd.DataFrame(columns=[
        'Name', 
        'Static Capacity (Tons)', 
        'Crushing Capacity Daily (Tons)', 
        'Receiving Capacity Daily (Tons)', 
        'Max Trucks in Yard', 
        'Avg Truck Capacity (Tons)', 
        'Monthly Direct Reception Forecast (Tons)', 
        'Initial Stock d0 (Tons)'
    ])
    df_factory.to_excel('templates/factories_template.xlsx', index=False)

    # Warehouse Template
    df_warehouse = pd.DataFrame(columns=[
        'Name', 
        'Static Capacity (Tons)', 
        'Daily Shipping Capacity (Tons)', 
        'Avg Shipping Vehicle Load (Tons)', 
        'Harvest Total Reception Forecast (Tons)', 
        'Daily Direct Reception Forecast (Tons)', 
        'Harvest Total Sales Forecast (Tons)', 
        'Daily Market Sales Forecast (Tons)', 
        'Initial Stock d0 (Tons)'
    ])
    df_warehouse.to_excel('templates/warehouses_template.xlsx', index=False)

    # Routes Template
    df_routes = pd.DataFrame(columns=[
        'Warehouse Name', 
        'Factory Name', 
        'Distance (km)', 
        'Freight Cost per Ton (R$)'
    ])
    df_routes.to_excel('templates/routes_template.xlsx', index=False)

    # Daily Updates Template
    df_daily = pd.DataFrame(columns=[
        'Date (YYYY-MM-DD)', 
        'Entity Type (Factory/Warehouse)', 
        'Entity Name', 
        'Real Stock (Tons)', 
        'Waiting Trucks (Only for Factory)'
    ])
    df_daily.to_excel('templates/daily_updates_template.xlsx', index=False)

    print("Templates generated successfully in 'templates/' directory.")

if __name__ == "__main__":
    generate_templates()
