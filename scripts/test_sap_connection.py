#!/usr/bin/env python3
"""
Test SAP Connection
测试 SAP 连接和数据提取
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
from loguru import logger

from src.sap_integration.config import SAPConfig
from src.sap_integration.sap_client import SAPODataClient
from src.sap_integration.data_transformer import SAPDataTransformer


def test_connection(client: SAPODataClient):
    """测试基本连接"""
    print("\n" + "=" * 70)
    print("测试 1: SAP 连接测试")
    print("=" * 70)
    
    try:
        result = client.test_connection()
        if result:
            print("✅ 连接成功")
            return True
        else:
            print("❌ 连接失败")
            return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def test_fetch_orders(client: SAPODataClient):
    """测试获取订单数据"""
    print("\n" + "=" * 70)
    print("测试 2: 获取生产订单（前 10 条）")
    print("=" * 70)
    
    try:
        orders = client.get_production_orders(top=10, skip=0)
        
        if orders:
            print(f"✅ 成功获取 {len(orders)} 条订单")
            print("\n示例订单:")
            
            if len(orders) > 0:
                order = orders[0]
                print(f"  订单号: {order.get('OrderNumber')}")
                print(f"  物料号: {order.get('MaterialNumber')}")
                print(f"  计划开始: {order.get('BasicStartDate')}")
                print(f"  实际完成: {order.get('ActualFinishDate')}")
            
            return True
        else:
            print("⚠️  未获取到数据（可能是过滤条件太严格）")
            return False
            
    except Exception as e:
        print(f"❌ 获取订单失败: {e}")
        return False


def test_fetch_materials(client: SAPODataClient):
    """测试获取物料数据"""
    print("\n" + "=" * 70)
    print("测试 3: 获取物料主数据")
    print("=" * 70)
    
    try:
        materials = client.get_material_master()
        
        if materials:
            print(f"✅ 成功获取 {len(materials)} 条物料")
            
            if len(materials) > 0:
                mat = materials[0]
                print(f"\n示例物料:")
                print(f"  物料号: {mat.get('MaterialNumber')}")
                print(f"  生产线: {mat.get('ProductionLine')}")
                print(f"  生产时间: {mat.get('TotalProductionTime')}")
                print(f"  最大产能: {mat.get('ConstraintFactor')}")
            
            return True
        else:
            print("⚠️  未获取到物料数据")
            return False
            
    except Exception as e:
        print(f"❌ 获取物料失败: {e}")
        return False


def test_data_transformation(client: SAPODataClient):
    """测试数据转换"""
    print("\n" + "=" * 70)
    print("测试 4: 数据转换")
    print("=" * 70)
    
    try:
        # 获取少量数据
        orders = client.get_production_orders(top=5)
        
        if not orders:
            print("⚠️  无数据可转换")
            return False
        
        # 转换
        transformer = SAPDataTransformer()
        df = transformer.transform_production_orders(orders)
        
        print(f"✅ 成功转换 {len(df)} 条订单")
        print(f"\n转换后的列:")
        for col in df.columns:
            print(f"  - {col}")
        
        print(f"\n示例数据（第1行）:")
        if len(df) > 0:
            for col in df.columns[:8]:  # 只显示前8列
                print(f"  {col}: {df[col].iloc[0]}")
        
        # 验证数据
        is_valid = transformer.validate_data(df, 'history')
        if is_valid:
            print("\n✅ 数据验证通过")
        else:
            print("\n⚠️  数据验证失败")
        
        return is_valid
        
    except Exception as e:
        print(f"❌ 数据转换失败: {e}")
        return False


def test_metadata(client: SAPODataClient):
    """测试获取元数据"""
    print("\n" + "=" * 70)
    print("测试 5: 获取服务元数据")
    print("=" * 70)
    
    try:
        metadata = client.get_metadata('production_orders')
        
        if metadata:
            print("✅ 成功获取元数据")
            print(f"  元数据长度: {len(metadata.get('xml', ''))} 字符")
            return True
        else:
            print("⚠️  未获取到元数据")
            return False
            
    except Exception as e:
        print(f"❌ 获取元数据失败: {e}")
        return False


def main():
    """主测试流程"""
    parser = argparse.ArgumentParser(description='测试 SAP 连接和数据提取')
    parser.add_argument(
        '--config',
        default='config/sap_config.yaml',
        help='配置文件路径'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='详细输出'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    print("=" * 70)
    print("🧪 SAP 集成测试工具")
    print("=" * 70)
    
    try:
        # 加载配置
        print(f"\n加载配置: {args.config}")
        config = SAPConfig(args.config)
        
        if not config.validate():
            print("\n❌ 配置验证失败")
            print("\n请检查:")
            print("  1. config/sap_config.yaml 文件是否存在")
            print("  2. .env 文件中的环境变量是否设置")
            print("  3. SAP 连接信息是否正确")
            return 1
        
        print("✅ 配置加载成功")
        
        # 创建客户端
        client = SAPODataClient(config.get())
        
        # 运行测试
        tests = [
            ("连接测试", lambda: test_connection(client)),
            ("获取订单", lambda: test_fetch_orders(client)),
            ("获取物料", lambda: test_fetch_materials(client)),
            ("数据转换", lambda: test_data_transformation(client)),
            ("获取元数据", lambda: test_metadata(client))
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                logger.exception(f"测试 '{test_name}' 异常: {e}")
                results.append((test_name, False))
        
        # 打印测试结果
        print("\n" + "=" * 70)
        print("📊 测试结果汇总")
        print("=" * 70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  {test_name:<20} {status}")
        
        print(f"\n总计: {passed}/{total} 测试通过")
        print("=" * 70)
        
        if passed == total:
            print("\n🎉 所有测试通过！可以开始数据同步。")
            print("\n运行命令:")
            print("  python scripts/sync_sap_data.py --mode full --start-date 2024-01-01")
            return 0
        else:
            print("\n⚠️  部分测试失败，请检查配置和 SAP 服务。")
            return 1
            
    except FileNotFoundError as e:
        print(f"\n❌ 配置文件不存在: {e}")
        print("\n请先创建配置文件:")
        print("  cp config/sap_config.yaml config/sap_config_prod.yaml")
        print("  # 然后编辑 sap_config_prod.yaml 填入实际值")
        return 1
    except SAPIntegrationError as e:
        print(f"\n❌ SAP 集成错误: {e}")
        return 1
    except Exception as e:
        logger.exception(f"未预期的错误: {e}")
        print(f"\n❌ 测试失败: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
