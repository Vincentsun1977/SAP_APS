#!/usr/bin/env python3
"""
从 SAP ECC 通过 OpenSQL API 抽取训练数据
用法:
    # 全量（从 2024-01-01 至今）
    python scripts/fetch_sap_data.py --date-from 20240101

    # 增量（最近 30 天）
    python scripts/fetch_sap_data.py --days 30

    # 指定日期范围
    python scripts/fetch_sap_data.py --date-from 20250101 --date-to 20250331

    # 仅测试连接
    python scripts/fetch_sap_data.py --test
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
from datetime import datetime, timedelta
from loguru import logger

from src.sap_integration.config import SAPConfig
from src.sap_integration.opensql_client import SAPOpenSQLClient
from src.sap_integration.opensql_fetcher import SAPDataFetcher


def setup_logging(log_dir: str = "logs"):
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "sap_fetch_{time}.log",
        rotation="1 day",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )


def main():
    parser = argparse.ArgumentParser(
        description="从 SAP ECC (OpenSQL API) 抽取 FG / Capacity / History / Shortage 数据"
    )
    parser.add_argument(
        "--date-from",
        help="History 起始日期 (YYYYMMDD)，与 --days 二选一",
    )
    parser.add_argument(
        "--date-to",
        help="History 截止日期 (YYYYMMDD)，默认今天",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="从今天往回 N 天（自动计算 date-from）",
    )
    parser.add_argument(
        "--plant",
        default=None,
        help="工厂代码（默认从配置文件读取）",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="CSV 输出目录（默认 data/raw）",
    )
    parser.add_argument(
        "--config",
        default="config/sap_config.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="仅测试 OpenSQL API 连接",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="不保存 CSV（仅打印统计）",
    )

    args = parser.parse_args()
    setup_logging()

    logger.info("=" * 60)
    logger.info("SAP OpenSQL 数据抽取工具")
    logger.info("=" * 60)

    # 加载配置
    cfg = SAPConfig(args.config).config
    opensql_cfg = cfg.get("opensql", {})
    if not opensql_cfg:
        logger.error("配置文件中缺少 'opensql' 段，请参考 config/sap_config.yaml")
        sys.exit(1)

    plant = args.plant or opensql_cfg.get("plant", "1202")

    # 创建客户端
    client = SAPOpenSQLClient(opensql_cfg)

    # 仅测试连接
    if args.test:
        ok = client.test_connection()
        sys.exit(0 if ok else 1)

    # 确定日期范围
    if args.days:
        date_from = (datetime.now() - timedelta(days=args.days)).strftime("%Y%m%d")
    elif args.date_from:
        date_from = args.date_from
    else:
        date_from = cfg.get("sync", {}).get("full_sync_start_date", "20240101")
        # 配置中可能是 YYYY-MM-DD 格式
        date_from = date_from.replace("-", "")

    date_to = args.date_to  # None → 默认今天

    logger.info(f"工厂: {plant}")
    logger.info(f"日期: {date_from} ~ {date_to or 'today'}")
    logger.info(f"输出: {args.output_dir}")

    # 执行
    fetcher = SAPDataFetcher(
        client=client,
        plant=plant,
        output_dir=args.output_dir,
    )

    try:
        result = fetcher.fetch_all(
            date_from=date_from,
            date_to=date_to,
            save_csv=not args.no_save,
        )
        logger.info("✓ 数据抽取成功完成")
    except Exception as e:
        logger.error(f"✗ 数据抽取失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
