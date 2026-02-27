import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/transbordo_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Factory(Base):
    __tablename__ = 'factories'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    static_capacity = Column(Float)
    crushing_capacity_daily = Column(Float)
    receiving_capacity_daily = Column(Float)
    max_trucks_in_yard = Column(Integer)
    avg_truck_capacity = Column(Float)
    monthly_direct_reception_forecast = Column(Float)
    initial_stock_d0 = Column(Float)

    routes = relationship("WarehouseFactoryRoute", back_populates="factory")
    daily_logs = relationship("DailyLogFactory", back_populates="factory")

class Warehouse(Base):
    __tablename__ = 'warehouses'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    static_capacity = Column(Float)
    daily_shipping_capacity = Column(Float)
    avg_shipping_vehicle_load = Column(Float)
    harvest_total_reception_forecast = Column(Float)
    daily_direct_reception_forecast = Column(Float)
    harvest_total_sales_forecast = Column(Float)
    daily_market_sales_forecast = Column(Float)
    initial_stock_d0 = Column(Float)

    routes = relationship("WarehouseFactoryRoute", back_populates="warehouse")
    daily_logs = relationship("DailyLogWarehouse", back_populates="warehouse")

class WarehouseFactoryRoute(Base):
    __tablename__ = 'warehouse_factory_routes'

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    factory_id = Column(Integer, ForeignKey('factories.id'))
    distance_km = Column(Float)
    freight_cost_per_ton = Column(Float)

    warehouse = relationship("Warehouse", back_populates="routes")
    factory = relationship("Factory", back_populates="routes")

class DailyLogFactory(Base):
    __tablename__ = 'daily_log_factories'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    factory_id = Column(Integer, ForeignKey('factories.id'))
    
    estimated_stock = Column(Float)
    real_stock = Column(Float, nullable=True) # Real, when updated
    
    received_from_warehouses = Column(Float)
    received_direct = Column(Float)
    crushed = Column(Float)
    
    waiting_trucks_estimated = Column(Integer)
    waiting_trucks_real = Column(Integer, nullable=True) # Real, when updated

    factory = relationship("Factory", back_populates="daily_logs")

class DailyLogWarehouse(Base):
    __tablename__ = 'daily_log_warehouses'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    
    estimated_stock = Column(Float)
    real_stock = Column(Float, nullable=True) # Real, when updated
    
    received_direct = Column(Float)
    sold_to_market = Column(Float)
    shipped_to_factories = Column(Float)
    vehicles_needed = Column(Integer)
    
    total_received_so_far = Column(Float, default=0.0)
    total_sold_so_far = Column(Float, default=0.0)

    warehouse = relationship("Warehouse", back_populates="daily_logs")

class FreightTransfer(Base):
    __tablename__ = 'freight_transfers'

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    warehouse_id = Column(Integer, ForeignKey('warehouses.id'))
    factory_id = Column(Integer, ForeignKey('factories.id'))
    amount_tons = Column(Float)
    vehicles_used = Column(Integer)
    total_freight_cost = Column(Float)

def init_db():
    Base.metadata.create_all(bind=engine)
