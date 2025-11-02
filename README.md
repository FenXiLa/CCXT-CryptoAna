# CCTX-Ana

加密货币交易所数据分析工具

## 项目描述

CCTX-Ana 是一个基于 CCXT 库的加密货币交易所数据分析工具，用于获取和分析各大交易所的市场数据。

## 已执行的任务

- 安装了pandas库用于数据处理
- 实现了多交易所数据获取功能
- 实现了动态排序交易所功能
- 实现了多时间周期数据抓取功能
- 实现了数据补单功能
- 增加了Crontab定时执行功能
- 添加了PostgreSQL数据库支持
- 实现了Docker容器化部署

## 功能特点

- **多交易所数据获取**: 从排名前十的交易所中依次尝试获取数据，直到成功或尝试完所有交易所
- **动态排序交易所**: 优先使用上次成功获取数据的交易所，提高数据获取效率
- **多时间周期数据抓取**: 支持1m、5m、15m、30m、1h、4h、8h、12h、1d等多种时间周期的数据抓取
- **数据补单功能**: 智能识别缺失的数据时间段，只获取缺失的数据，避免重复抓取
- **定时执行功能**: 支持通过Crontab设置定时任务，自动获取最新数据
- **多种数据存储**: 支持CSV和PostgreSQL两种数据存储方式
- **配置文件支持**: 通过YAML配置文件灵活配置系统参数
- **Docker支持**: 提供Docker容器化部署，与PostgreSQL数据库集成
- **获取交易所列表**: 获取所有可用的交易所列表
- **获取市场信息**: 获取指定交易所的市场信息
- **获取OHLCV数据**: 获取指定交易所、交易对和时间周期的OHLCV数据
- **数据转换**: 将OHLCV数据转换为Pandas DataFrame格式，方便后续分析

## 已解决的问题

- 解决了 `ModuleNotFoundError: No module named 'pandas'` 错误，通过安装pandas库解决
- 更新了 `requirements.txt` 文件，添加了pandas依赖
- 解决了单一交易所数据获取失败问题，实现了多交易所数据获取功能
- 解决了数据重复抓取问题，实现了智能数据补单功能
- 解决了手动执行脚本问题，实现了自动定时执行功能
- 解决了数据持久化问题，支持PostgreSQL数据库存储
- 解决了部署问题，提供Docker容器化部署方案

## 已知问题

- `fatal: bad revision 'HEAD'` 错误，可能是因为Git仓库初始化问题
- API连接错误：尝试连接某些交易所API时可能会出现连接错误，但程序会自动尝试其他交易所，直到成功获取数据

## 使用方法

### 多交易所数据获取

```python
# 获取市场信息
exchange_id, markets = get_markets_from_multiple_exchanges('BTC/USDT')
if markets:
    print(f"成功从 {exchange_id} 获取市场信息")

# 获取OHLCV数据
exchange_id, ohlcv_data = fetch_ohlcv_from_multiple_exchanges('BTC/USDT', '1d', 30)
if ohlcv_data is not None:
    print(f"成功从 {exchange_id} 获取OHLCV数据")
    print(ohlcv_data)
```

### 多时间周期数据抓取与补单

```python
# 获取单个时间周期的数据，自动补充缺失数据
success = fetch_and_save_ohlcv_data('BTC/USDT', '1h', 
                                   start_time=datetime.now() - timedelta(days=7))

# 获取所有时间周期的数据
results = fetch_all_timeframes('BTC/USDT', 
                              start_time=datetime.now() - timedelta(days=30))
```

### 定时执行功能

使用提供的 `cron_task.py` 脚本设置定时任务：

```bash
# 获取BTC/USDT的1小时数据，历史7天
python cron_task.py --symbol BTC/USDT --timeframe 1h --days 7

# 获取ETH/USDT的所有时间周期数据，历史30天
python cron_task.py --symbol ETH/USDT --days 30
```

要设置自动定时执行，请参考 `crontab_example.txt` 文件中的示例，使用 `crontab -e` 命令编辑你的crontab配置。

### Docker部署

项目提供了Docker容器化部署方案，可以与PostgreSQL数据库集成使用。

#### 准备工作

1. 确保已安装Docker和Docker Compose
2. 复制配置文件模板并根据需要修改：
   ```bash
   cp config.example.yml config.yml
   ```

#### 使用Docker Compose启动服务

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down
```

#### 配置说明

在`config.yml`文件中可以配置以下内容：

```yaml
database:
  # 数据存储类型：csv或postgresql
  type: postgresql
  postgresql:
    host: postgres
    port: 5432
    dbname: crypto_data
    user: postgres
    password: postgres

data:
  # 默认交易对
  default_symbol: BTC/USDT
  # 需要获取的时间周期列表
  timeframes:
    - 1h
    - 4h
    - 1d
  # 默认获取的历史数据天数
  default_days: 30
  # 是否启用动态排序交易所功能
  enable_dynamic_sorting: true
  # 是否启用数据补单功能
  enable_data_filling: true

# 定时任务配置
cron:
  # 是否启用定时任务
  enabled: true
  # 定时任务列表
  tasks:
    - symbol: BTC/USDT
      timeframe: 1h
      days: 1
      cron: "0 * * * *"  # 每小时执行一次
    - symbol: ETH/USDT
      timeframe: 1d
      days: 7
      cron: "0 0 * * *"  # 每天执行一次
```

#### 环境变量

也可以通过环境变量来配置数据库连接：

- `POSTGRES_HOST`: PostgreSQL主机地址
- `POSTGRES_PORT`: PostgreSQL端口
- `POSTGRES_DB`: 数据库名称
- `POSTGRES_USER`: 数据库用户名
- `POSTGRES_PASSWORD`: 数据库密码
- `CONFIG_PATH`: 配置文件路径

## 数据存储

- **CSV存储**: 数据文件保存在 `data` 目录下，格式为 CSV
- **PostgreSQL存储**: 数据保存在PostgreSQL数据库中，表名为 `ohlcv_data`
- 成功交易所记录保存在 `cache` 目录下，用于优化后续数据获取

## 后续步骤

- 增加更多数据分析功能
- 实现数据可视化
- 添加更多交易对支持
- 优化错误处理机制
- 实现数据导出到其他数据库功能