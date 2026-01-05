#!/usr/bin/env python3
"""
SAP Data Synchronization Script
SAP 数据同步脚本 - 从 SAP 系统提取数据到本地 CSV
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
from datetime import datetime
from loguru import logger

from src.sap_integration.config import SAPConfig
from src.sap_integration.data_extractor import SAPDataExtractor
from src.sap_integration.exceptions import SAPIntegrationError


def setup_logging(log_dir: str = "logs"):
    """配置日志"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_path / "sap_sync_{time}.log",
        rotation="1 day",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='从 SAP 系统同步生产订单数据'
    )
    
    parser.add_argument(
        '--mode',
        choices=['full', 'incremental'],
        default='incremental',
        help='同步模式: full=全量同步, incremental=增量同步'
    )
    
    parser.add_argument(
        '--start-date',
        help='开始日期 (YYYY-MM-DD)，仅用于 full 模式'
    )
    
    parser.add_argument(
        '--end-date',
        help='结束日期 (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--config',
        default='config/sap_config.yaml',
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='测试模式（只提取少量数据）'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    logger.info("=" * 70)
    logger.info("SAP 数据同步工具")
    logger.info("=" * 70)
    
    try:
        # 1. 加载配置
        logger.info(f"加载配置: {args.config}")
        config = SAPConfig(args.config)
        
        if not config.validate():
            logger.error("配置验证失败，请检查配置文件和环境变量")
            return 1
        
        # 2. 创建提取器
        extractor = SAPDataExtractor(config.get())
        
        # 3. 测试连接
        logger.info("测试 SAP 连接...")
        if not extractor.client.test_connection():
            logger.error("SAP 连接测试失败")
            return 1
        
        # 4. 执行同步
        if args.test:
            logger.info("⚠️  测试模式：只提取最近 7 天的数据")
            from datetime import timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            data = extractor.extract_all_data(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                mode='full'
            )
        else:
            data = extractor.sync(mode=args.mode)
        
        # 5. 打印摘要
        print("\n" + "=" * 70)
        print("📊 同步完成摘要")
        print("=" * 70)
        print(f"模式: {args.mode}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n数据统计:")
        print(f"  - 生产订单 (History.csv): {len(data['history'])} 条")
        print(f"  - 物料数据 (FG.csv): {len(data['material'])} 条")
        print(f"  - 产能数据 (Capacity.csv): {len(data['capacity'])} 条")
        print(f"\n文件位置: {extractor.output_dir}")
        print("=" * 70)
        
        # 6. 建议下一步
        print("\n💡 下一步操作:")
        print("  1. 检查数据文件: data/raw/History.csv")
        print("  2. 重新训练模型: python scripts/train_aps_model_optimized.py")
        print("  3. 运行预测: python scripts/predict_new_orders.py")
        print()
        
        return 0
        
    except SAPIntegrationError as e:
        logger.error(f"SAP 集成错误: {e}")
        print(f"\n❌ 同步失败: {e}")
        return 1
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        print(f"\n❌ 同步失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
