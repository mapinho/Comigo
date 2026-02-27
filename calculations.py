import datetime
from sqlalchemy import asc
from models import SessionLocal, Factory, Warehouse, WarehouseFactoryRoute, DailyLogFactory, DailyLogWarehouse, FreightTransfer

def run_simulation(start_date, num_days=30):
    session = SessionLocal()
    try:
        factories = session.query(Factory).all()
        warehouses = session.query(Warehouse).all()
        routes = session.query(WarehouseFactoryRoute).order_by(asc(WarehouseFactoryRoute.freight_cost_per_ton)).all()

        current_date = start_date

        for day in range(num_days):
            # 1. Update Warehouses available stock
            warehouse_availables = {}
            for w in warehouses:
                # Get yesterday's log or use d0
                yesterday_log = session.query(DailyLogWarehouse).filter(
                    DailyLogWarehouse.warehouse_id == w.id,
                    DailyLogWarehouse.date == current_date - datetime.timedelta(days=1)
                ).first()

                if yesterday_log:
                    # If real_stock is available, use it, else use estimated
                    start_stock = yesterday_log.real_stock if yesterday_log.real_stock is not None else yesterday_log.estimated_stock
                    total_received_so_far = yesterday_log.total_received_so_far
                    total_sold_so_far = yesterday_log.total_sold_so_far
                else:
                    start_stock = w.initial_stock_d0
                    total_received_so_far = 0.0
                    total_sold_so_far = 0.0

                daily_reception = w.daily_direct_reception_forecast if total_received_so_far < w.harvest_total_reception_forecast else 0.0
                daily_sales = w.daily_market_sales_forecast if total_sold_so_far < w.harvest_total_sales_forecast else 0.0
                
                # Prevent over-receiving and over-selling based on forecast totals
                if total_received_so_far + daily_reception > w.harvest_total_reception_forecast:
                    daily_reception = w.harvest_total_reception_forecast - total_received_so_far
                if total_sold_so_far + daily_sales > w.harvest_total_sales_forecast:
                    daily_sales = w.harvest_total_sales_forecast - total_sold_so_far

                available_stock = start_stock + daily_reception - daily_sales
                if available_stock < 0:
                    available_stock = 0
                if available_stock > w.static_capacity:
                    available_stock = w.static_capacity

                max_can_ship = min(w.daily_shipping_capacity, available_stock)
                
                warehouse_availables[w.id] = {
                    'start_stock': start_stock,
                    'daily_reception': daily_reception,
                    'daily_sales': daily_sales,
                    'available_stock': available_stock,
                    'max_can_ship': max_can_ship,
                    'total_received_so_far': total_received_so_far + daily_reception,
                    'total_sold_so_far': total_sold_so_far + daily_sales,
                    'shipped_today': 0.0
                }

            # 2. Update Factories needs
            factory_needs = {}
            for f in factories:
                yesterday_log = session.query(DailyLogFactory).filter(
                    DailyLogFactory.factory_id == f.id,
                    DailyLogFactory.date == current_date - datetime.timedelta(days=1)
                ).first()

                if yesterday_log:
                    start_stock = yesterday_log.real_stock if yesterday_log.real_stock is not None else yesterday_log.estimated_stock
                else:
                    start_stock = f.initial_stock_d0

                daily_direct = f.monthly_direct_reception_forecast / 30.0
                
                # Check how much capacity is left
                capacity_remaining = f.static_capacity - (start_stock + daily_direct - f.crushing_capacity_daily)
                
                # How much it can physically receive today (restrição: recebimento diário < capacidade de recebimento)
                max_receiving_tons = f.receiving_capacity_daily - daily_direct
                
                # Limit by trucks capacity
                max_truck_tons = f.max_trucks_in_yard * f.avg_truck_capacity
                
                max_can_receive = min(capacity_remaining, max_receiving_tons, max_truck_tons)
                if max_can_receive < 0:
                    max_can_receive = 0

                factory_needs[f.id] = {
                    'start_stock': start_stock,
                    'daily_direct': daily_direct,
                    'max_can_receive': max_can_receive,
                    'received_today': 0.0,
                    'trucks_used_today': 0
                }

            # 3. Allocation (Greedy based on cheapest freight)
            for route in routes:
                w_id = route.warehouse_id
                f_id = route.factory_id
                
                w_data = warehouse_availables[w_id]
                f_data = factory_needs[f_id]

                if w_data['max_can_ship'] > 0 and f_data['max_can_receive'] > 0:
                    transfer_amount = min(w_data['max_can_ship'], f_data['max_can_receive'])
                    
                    # Update local trackers
                    w_data['max_can_ship'] -= transfer_amount
                    w_data['shipped_today'] += transfer_amount
                    w_data['available_stock'] -= transfer_amount

                    f_data['max_can_receive'] -= transfer_amount
                    f_data['received_today'] += transfer_amount
                    
                    # Trucks used for this transfer
                    # Assuming average vehicle load is from warehouse
                    warehouse = session.query(Warehouse).get(w_id)
                    vehicles_used = int(transfer_amount / warehouse.avg_shipping_vehicle_load) if warehouse.avg_shipping_vehicle_load > 0 else 0
                    
                    f_data['trucks_used_today'] += vehicles_used

                    # Log transfer
                    transfer = FreightTransfer(
                        date=current_date,
                        warehouse_id=w_id,
                        factory_id=f_id,
                        amount_tons=transfer_amount,
                        vehicles_used=vehicles_used,
                        total_freight_cost=transfer_amount * route.freight_cost_per_ton
                    )
                    session.add(transfer)

            # 4. Finalize Daily Logs
            for w in warehouses:
                w_data = warehouse_availables[w.id]
                log_w = session.query(DailyLogWarehouse).filter_by(date=current_date, warehouse_id=w.id).first()
                if not log_w:
                    log_w = DailyLogWarehouse(date=current_date, warehouse_id=w.id)
                    session.add(log_w)
                
                log_w.received_direct = w_data['daily_reception']
                log_w.sold_to_market = w_data['daily_sales']
                log_w.shipped_to_factories = w_data['shipped_today']
                log_w.estimated_stock = w_data['available_stock']
                log_w.vehicles_needed = int(w_data['shipped_today'] / w.avg_shipping_vehicle_load) if w.avg_shipping_vehicle_load > 0 else 0
                log_w.total_received_so_far = w_data['total_received_so_far']
                log_w.total_sold_so_far = w_data['total_sold_so_far']

            for f in factories:
                f_data = factory_needs[f.id]
                log_f = session.query(DailyLogFactory).filter_by(date=current_date, factory_id=f.id).first()
                if not log_f:
                    log_f = DailyLogFactory(date=current_date, factory_id=f.id)
                    session.add(log_f)

                log_f.received_direct = f_data['daily_direct']
                log_f.received_from_warehouses = f_data['received_today']
                
                # Estimate stock
                est_stock = f_data['start_stock'] + f_data['daily_direct'] + f_data['received_today'] - f.crushing_capacity_daily
                if est_stock < 0:
                    est_stock = 0
                if est_stock > f.static_capacity:
                    est_stock = f.static_capacity
                    
                log_f.crushed = f.crushing_capacity_daily if (f_data['start_stock'] + f_data['daily_direct'] + f_data['received_today']) >= f.crushing_capacity_daily else (f_data['start_stock'] + f_data['daily_direct'] + f_data['received_today'])
                log_f.estimated_stock = est_stock
                log_f.waiting_trucks_estimated = f_data['trucks_used_today'] # Or some calculation if it exceeds max

            session.commit()
            current_date += datetime.timedelta(days=1)
            
    finally:
        session.close()

if __name__ == "__main__":
    run_simulation(datetime.date.today(), num_days=30)
