#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CCTX-Ana 数据库操作模块
支持CSV和PostgreSQL两种存储方式
"""

import os
import yaml
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 配置文件路径
CONFIG_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / 'config.yml'
CONFIG_EXAMPLE_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / 'config.example.yml'

# 数据存储目录
DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'data'
DATA_DIR.mkdir(exist_ok=True)

# 创建SQLAlchemy基类
Base = declarative_base()

def load_config():
    """加载配置文件"""
    # 如果配置文件不存在，复制示例配置
    if not CONFIG_PATH.exists() and CONFIG_EXAMPLE_PATH.exists():
        import shutil
        shutil.copy(CONFIG_EXAMPLE_PATH, CONFIG_PATH)
        print(f"已创建配置文件: {CONFIG_PATH}")
    
    # 加载配置
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    else:
        # 返回默认配置
        return {
            'database': {
                'type': 'csv',
                'postgresql': {
                    'host': 'localhost',
                    'port': 5432,
                    'dbname': 'cctxana',
                    'user': 'postgres',
                    'password': 'postgres'
                }
            }
        }

class OHLCVData(Base):
    """OHLCV数据模型"""
    __tablename__ = 'ohlcv_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    exchange = Column(String, index=True)
    timeframe = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    
    def __repr__(self):
        return f"<OHLCV(symbol='{self.symbol}', exchange='{self.exchange}', timestamp='{self.timestamp}')>"

class Database:
    """数据库操作类"""
    def __init__(self):
        self.config = load_config()
        self.db_type = self.config['database']['type']
        
        if self.db_type == 'postgresql':
            self._init_postgresql()
        else:
            self.engine = None
            self.session = None
    
    def _init_postgresql(self):
        """初始化PostgreSQL连接"""
        pg_config = self.config['database']['postgresql']
        connection_string = f"postgresql://{pg_config['user']}:{pg_config['password']}@{pg_config['host']}:{pg_config['port']}/{pg_config['dbname']}"
        
        try:
            self.engine = create_engine(connection_string)
            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            print("PostgreSQL数据库连接成功")
        except Exception as e:
            print(f"PostgreSQL数据库连接失败: {e}")
            self.engine = None
            self.session = None
    
    def save_ohlcv_data(self, df, symbol, timeframe, exchange_id):
        """保存OHLCV数据"""
        if self.db_type == 'postgresql' and self.engine is not None:
            return self._save_to_postgresql(df, symbol, timeframe, exchange_id)
        else:
            return self._save_to_csv(df, symbol, timeframe, exchange_id)
    
    def _save_to_postgresql(self, df, symbol, timeframe, exchange_id):
        """保存数据到PostgreSQL"""
        try:
            # 准备数据
            records = []
            for _, row in df.iterrows():
                record = OHLCVData(
                    symbol=symbol,
                    exchange=exchange_id,
                    timeframe=timeframe,
                    timestamp=row['timestamp'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                )
                records.append(record)
            
            # 批量插入数据
            self.session.bulk_save_objects(records)
            self.session.commit()
            print(f"数据已保存到PostgreSQL数据库: {symbol} {timeframe}")
            return True
        except Exception as e:
            self.session.rollback()
            print(f"保存数据到PostgreSQL时出错: {e}")
            # 如果PostgreSQL保存失败，尝试保存到CSV
            return self._save_to_csv(df, symbol, timeframe, exchange_id)
    
    def _save_to_csv(self, df, symbol, timeframe, exchange_id):
        """保存数据到CSV文件"""
        symbol_safe = symbol.replace('/', '_')
        filename = DATA_DIR / f"{symbol_safe}_{timeframe}_{exchange_id}.csv"
        try:
            df.to_csv(filename, index=False)
            print(f"数据已保存到CSV文件: {filename}")
            return True
        except Exception as e:
            print(f"保存数据到CSV时出错: {e}")
            return False
    
    def load_ohlcv_data(self, symbol, timeframe, exchange_id=None):
        """加载OHLCV数据"""
        if self.db_type == 'postgresql' and self.engine is not None:
            return self._load_from_postgresql(symbol, timeframe, exchange_id)
        else:
            return self._load_from_csv(symbol, timeframe, exchange_id)
    
    def _load_from_postgresql(self, symbol, timeframe, exchange_id=None):
        """从PostgreSQL加载数据"""
        try:
            query = self.session.query(OHLCVData).filter(
                OHLCVData.symbol == symbol,
                OHLCVData.timeframe == timeframe
            )
            
            if exchange_id:
                query = query.filter(OHLCVData.exchange == exchange_id)
            
            # 获取结果并转换为DataFrame
            results = query.all()
            if not results:
                return None
            
            data = []
            for record in results:
                data.append({
                    'timestamp': record.timestamp,
                    'open': record.open,
                    'high': record.high,
                    'low': record.low,
                    'close': record.close,
                    'volume': record.volume
                })
            
            df = pd.DataFrame(data)
            return df
        except Exception as e:
            print(f"从PostgreSQL加载数据时出错: {e}")
            # 如果PostgreSQL加载失败，尝试从CSV加载
            return self._load_from_csv(symbol, timeframe, exchange_id)
    
    def _load_from_csv(self, symbol, timeframe, exchange_id=None):
        """从CSV文件加载数据"""
        symbol_safe = symbol.replace('/', '_')
        if exchange_id:
            filename = DATA_DIR / f"{symbol_safe}_{timeframe}_{exchange_id}.csv"
        else:
            # 尝试查找任何匹配的文件
            pattern = f"{symbol_safe}_{timeframe}_*.csv"
            files = list(DATA_DIR.glob(pattern))
            if not files:
                return None
            filename = files[0]
        
        if filename.exists():
            try:
                df = pd.read_csv(filename)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            except Exception as e:
                print(f"加载CSV数据时出错: {e}")
        
        return None

# 创建全局数据库实例
db = Database()