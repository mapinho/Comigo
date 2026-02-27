import pandas as pd
from models import SessionLocal, Factory, Warehouse, WarehouseFactoryRoute, DailyLogFactory, DailyLogWarehouse
from datetime import datetime

def load_factories(filepath):
    df = pd.read_excel(filepath)
    session = SessionLocal()
    try:
        for index, row in df.iterrows():
            factory = session.query(Factory).filter(Factory.name == row['Name']).first()
            if not factory:
                factory = Factory(name=row['Name'])
                session.add(factory)
            
            factory.static_capacity = row['Static Capacity (Tons)']
            factory.crushing_capacity_daily = row['Crushing Capacity Daily (Tons)']
            factory.receiving_capacity_daily = row['Receiving Capacity Daily (Tons)']
            factory.max_trucks_in_yard = row['Max Trucks in Yard']
            factory.avg_truck_capacity = row['Avg Truck Capacity (Tons)']
            factory.monthly_direct_reception_forecast = row['Monthly Direct Reception Forecast (Tons)']
            factory.initial_stock_d0 = row['Initial Stock d0 (Tons)']
            
        session.commit()
    finally:
        session.close()

def load_warehouses(filepath):
    df = pd.read_excel(filepath)
    session = SessionLocal()
    try:
        for index, row in df.iterrows():
            warehouse = session.query(Warehouse).filter(Warehouse.name == row['Name']).first()
            if not warehouse:
                warehouse = Warehouse(name=row['Name'])
                session.add(warehouse)
                
            warehouse.static_capacity = row['Static Capacity (Tons)']
            warehouse.daily_shipping_capacity = row['Daily Shipping Capacity (Tons)']
            warehouse.avg_shipping_vehicle_load = row['Avg Shipping Vehicle Load (Tons)']
            warehouse.harvest_total_reception_forecast = row['Harvest Total Reception Forecast (Tons)']
            warehouse.daily_direct_reception_forecast = row['Daily Direct Reception Forecast (Tons)']
            warehouse.harvest_total_sales_forecast = row['Harvest Total Sales Forecast (Tons)']
            warehouse.daily_market_sales_forecast = row['Daily Market Sales Forecast (Tons)']
            warehouse.initial_stock_d0 = row['Initial Stock d0 (Tons)']
            
        session.commit()
    finally:
        session.close()

def load_routes(filepath):
    df = pd.read_excel(filepath)
    session = SessionLocal()
    try:
        for index, row in df.iterrows():
            warehouse = session.query(Warehouse).filter(Warehouse.name == row['Warehouse Name']).first()
            factory = session.query(Factory).filter(Factory.name == row['Factory Name']).first()
            
            if warehouse and factory:
                route = session.query(WarehouseFactoryRoute).filter(
                    WarehouseFactoryRoute.warehouse_id == warehouse.id,
                    WarehouseFactoryRoute.factory_id == factory.id
                ).first()
                if not route:
                    route = WarehouseFactoryRoute(warehouse_id=warehouse.id, factory_id=factory.id)
                    session.add(route)
                    
                route.distance_km = row['Distance (km)']
                route.freight_cost_per_ton = row['Freight Cost per Ton (R$)']
                
        session.commit()
    finally:
        session.close()

def load_daily_updates(filepath):
    df = pd.read_excel(filepath)
    session = SessionLocal()
    try:
        for index, row in df.iterrows():
            date_obj = datetime.strptime(str(row['Date (YYYY-MM-DD)']).split(' ')[0], '%Y-%m-%d').date()
            entity_type = row['Entity Type (Factory/Warehouse)']
            entity_name = row['Entity Name']
            
            if entity_type.lower() == 'factory':
                factory = session.query(Factory).filter(Factory.name == entity_name).first()
                if factory:
                    log = session.query(DailyLogFactory).filter(
                        DailyLogFactory.date == date_obj,
                        DailyLogFactory.factory_id == factory.id
                    ).first()
                    if log:
                        if pd.notna(row['Real Stock (Tons)']):
                            log.real_stock = row['Real Stock (Tons)']
                        if pd.notna(row['Waiting Trucks (Only for Factory)']):
                            log.waiting_trucks_real = row['Waiting Trucks (Only for Factory)']
            
            elif entity_type.lower() == 'warehouse':
                warehouse = session.query(Warehouse).filter(Warehouse.name == entity_name).first()
                if warehouse:
                    log = session.query(DailyLogWarehouse).filter(
                        DailyLogWarehouse.date == date_obj,
                        DailyLogWarehouse.warehouse_id == warehouse.id
                    ).first()
                    if log:
                        if pd.notna(row['Real Stock (Tons)']):
                            log.real_stock = row['Real Stock (Tons)']
                            
        session.commit()
    finally:
        session.close()
