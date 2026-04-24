#!/usr/bin/env python3
"""
Simple SAP Connection Test
简单的 SAP 连通性测试 - 只需 .env 配置即可运行
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from urllib import response
import requests
import base64
import json
import pandas as pd
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 输出目录
OUTPUT_DIR = Path("data/sap_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 服务路径
SERVICE_PATH = '/sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder'


def test_sap_connection():
    """测试 SAP 连接并保存数据"""
    
    print("=" * 80)

    print("🧪 SAP 连通性测试")
    print("=" * 80)
    
    # 1. 读取配置
    print("\n步骤 1: 读取配置")
    print("-" * 80)
    
    sap_host = os.getenv('SAP_HOST')
    sap_port = os.getenv('SAP_PORT', '443')
    sap_protocol = os.getenv('SAP_PROTOCOL', 'https')
    sap_client = os.getenv('SAP_CLIENT', '100')
    sap_username = os.getenv('SAP_USERNAME')
    sap_password = os.getenv('SAP_PASSWORD')
    sap_service = os.getenv('SAP_ODATA_SERVICE', '/sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder')
    sap_verify_ssl = os.getenv('SAP_VERIFY_SSL', 'false').lower() == 'true'
    
    # 验证配置
    if not all([sap_host, sap_username, sap_password]):
        print("❌ 配置不完整，请检查 .env 文件")
        print("\n必需的环境变量:")
        print("  - SAP_HOST")
        print("  - SAP_USERNAME")
        print("  - SAP_PASSWORD")
        print("  - SAP_ODATA_SERVICE (可选，有默认值)")
        return False
    
    print(f"✓ SAP 主机: {sap_host}:{sap_port}")
    print(f"✓ 客户端: {sap_client}")
    print(f"✓ 用户: {sap_username}")
    print(f"✓ 服务路径: {sap_service}")
    print(f"✓ SSL 验证: {'启用' if sap_verify_ssl else '禁用（仅测试）'}")
    
    # 2. 构建请求
    print("\n步骤 2: 构建请求")
    print("-" * 80)
    
    base_url = f"{sap_protocol}://{sap_host}:{sap_port}"
    service_url = base_url + sap_service
    entity_url = service_url + "/ProductionOrderSet"
    
    # Basic 认证
    credentials = f"{sap_username}:{sap_password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Accept': 'application/json',
        'sap-client': sap_client
    }
    
    # 将查询参数直接传递到 headers 中
    headers.update({
        '$format': 'json',
        '$top': '10',
        '$filter': 'ActualFinishDate ne null',
        '$orderby': 'BasicStartDate desc'
    })

    # 移除 params，确保只通过 headers 传递
    params = None

    print(f"✓ 请求 URL: {entity_url}")
    print(f"✓ 查询参数（通过 headers 传递）: {json.dumps(headers, indent=2)}")
    
    # 3. 发送请求
    print("\n步骤 3: 发送请求到 SAP")
    print("-" * 80)
    
    try:
        print(f"正在连接 {sap_host}...")
        
        response = requests.get(
            entity_url,
            headers=headers,
            params=params,
            timeout=30,
            verify=sap_verify_ssl  # 从配置读取，测试环境可设为 False
        )
        
        # 禁用 SSL 警告（仅在 verify=False 时）
        if not sap_verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        print(f"✓ HTTP 状态码: {response.status_code}")
        
        # 检查状态码
        if response.status_code == 401:
            print("❌ 认证失败 (401)")
            print("   请检查用户名和密码是否正确")
            return False
        
        elif response.status_code == 404:
            print("❌ 服务不存在 (404)")
            print(f"   请确认 OData 服务已发布: {service_url}")
            print(f"   可以在浏览器访问: {service_url}/$metadata")
            return False
        
        elif response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应内容: {response.text[:200]}")
            return False
        
        print("✅ 请求成功")
        
    except requests.exceptions.Timeout:
        print("❌ 连接超时（>30秒）")
        print("   请检查网络连接和防火墙设置")
        return False
    
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {e}")
        print("   请检查:")
        print(f"   1. SAP 服务器地址是否正确: {sap_host}")
        print(f"   2. 端口是否正确: {sap_port}")
        print("   3. 网络是否连通")
        return False
    
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False
    
    # 4. 解析数据
    print("\n步骤 4: 解析响应数据")
    print("-" * 80)
    
    try:
        data = response.json()
        
        # 保存原始 JSON（用于调试）
        json_file = OUTPUT_DIR / f"sap_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 原始响应已保存: {json_file}")
        
        # 提取订单数据
        if 'd' in data and 'results' in data['d']:
            orders = data['d']['results']
            print(f"✓ 成功解析 {len(orders)} 条订单")
        else:
            print("⚠️  响应格式异常，未找到 'results'")
            print(f"   响应结构: {list(data.keys())}")
            orders = []
        
        if not orders:
            print("⚠️  未获取到订单数据")
            print("   可能原因:")
            print("   1. 过滤条件太严格（没有符合条件的数据）")
            print("   2. SAP 服务返回空结果")
            return False
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        print(f"   响应内容: {response.text[:200]}")
        return False
    
    # 5. 显示示例数据
    print("\n步骤 5: 显示示例数据")
    print("-" * 80)
    
    if len(orders) > 0:
        first_order = orders[0]
        print(f"\n第一条订单数据:")
        for key, value in first_order.items():
            # 截断长字符串
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            print(f"  {key:<25}: {value_str}")
    
    # 修正日期字段为日期型，不包含时间
    for order in orders:
        if 'GSTRP' in order:
            order['GSTRP'] = order['GSTRP'].split('T')[0]
        if 'GLTRP' in order:
            order['GLTRP'] = order['GLTRP'].split('T')[0]
        if 'GSTRI' in order:
            order['GSTRI'] = order['GSTRI'].split('T')[0]
        if 'GLTRI' in order:
            order['GLTRI'] = order['GLTRI'].split('T')[0]
    
    # 6. 转换并保存数据
    print("\n步骤 6: 转换并保存数据")
    print("-" * 80)
    
    try:
        # 转换为 DataFrame
        df = pd.DataFrame(orders)
        
        # 保存为 CSV
        csv_file = OUTPUT_DIR / f"sap_test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        print(f"✓ 数据已保存为 CSV: {csv_file}")
        print(f"  - 行数: {len(df)}")
        print(f"  - 列数: {len(df.columns)}")
        print(f"  - 列名: {', '.join(df.columns[:5])}...")
        
        # 保存为 Excel（更易查看）
        excel_file = OUTPUT_DIR / f"sap_test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(excel_file, index=False, engine='openpyxl')
        print(f"✓ 数据已保存为 Excel: {excel_file}")
        
    except Exception as e:
        print(f"⚠️  保存数据时出错: {e}")
        # 继续，不影响测试结果
    
    # 7. 生成测试报告
    print("\n步骤 7: 生成测试报告")
    print("-" * 80)
    
    report_file = OUTPUT_DIR / f"connection_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SAP 连通性测试报告\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("配置信息:\n")
        f.write(f"  SAP 主机: {sap_host}:{sap_port}\n")
        f.write(f"  客户端: {sap_client}\n")
        f.write(f"  用户: {sap_username}\n")
        f.write(f"  服务: {sap_service}\n\n")
        
        f.write("测试结果:\n")
        f.write(f"  ✅ 连接成功\n")
        f.write(f"  ✅ 认证通过\n")
        f.write(f"  ✅ 数据获取成功\n")
        f.write(f"  ✅ 获取订单数: {len(orders)} 条\n\n")
        
        f.write("数据文件:\n")
        f.write(f"  - JSON: {json_file.name}\n")
        f.write(f"  - CSV:  {csv_file.name}\n")
        f.write(f"  - Excel: {excel_file.name}\n\n")
        
        f.write("示例数据（第一条订单）:\n")
        if len(orders) > 0:
            for key, value in first_order.items():
                f.write(f"  {key}: {value}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("✅ SAP 接口连接成功！\n")
        f.write("=" * 80 + "\n")
    
    print(f"✓ 测试报告已保存: {report_file}")
    
    # 8. 成功总结
    print("\n" + "=" * 80)
    print("✅ SAP 连通性测试成功！")
    print("=" * 80)
    print(f"\n📊 测试结果:")
    print(f"  - 成功连接到 SAP 服务器")
    print(f"  - 成功获取 {len(orders)} 条生产订单数据")
    print(f"  - 数据已保存到: {OUTPUT_DIR}")
    print(f"\n📁 生成的文件:")
    print(f"  1. {json_file.name} - 原始 JSON 响应")
    print(f"  2. {csv_file.name} - CSV 格式数据")
    print(f"  3. {excel_file.name} - Excel 格式数据")
    print(f"  4. {report_file.name} - 测试报告")
    print(f"\n💡 下一步:")
    print(f"  1. 查看测试数据: {csv_file}")
    print(f"  2. 验证字段是否完整")
    print(f"  3. 联系 SAP 团队确认数据正确性")
    print(f"  4. 如果一切正常，可以运行完整同步:")
    print(f"     python scripts/sync_sap_data.py --test")
    print("=" * 80)
    
    return True


def fetch_caufv_data():
    """获取 CAUFV 表数据"""
    print("\n" + "=" * 80)
    print("🧪 测试获取 CAUFV 表数据")
    print("=" * 80)

    # 1. 构建请求
    sap_host = os.getenv('SAP_HOST')
    sap_port = os.getenv('SAP_PORT', '443')
    sap_protocol = os.getenv('SAP_PROTOCOL', 'https')
    sap_client = os.getenv('SAP_CLIENT', '100')
    sap_username = os.getenv('SAP_USERNAME')
    sap_password = os.getenv('SAP_PASSWORD')
    sap_verify_ssl = os.getenv('SAP_VERIFY_SSL', 'false').lower() == 'true'

    base_url = f"{sap_protocol}://{sap_host}:{sap_port}"
    service_url = base_url + '/ABB/Test/ZTTPP_APS/ProductionOrder'
    entity_url = service_url

    credentials = f"{sap_username}:{sap_password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Accept': 'application/json',
        'sap-client': sap_client
    }

    params = {
        '$format': 'json',
        '$filter': (
            "AUTYP eq '10' and "
            "WERKS eq '1202' and "
            "GSTRP ge '20240101' and "
            "GSTRP le '20251231'"
        ),
        '$select': 'AUFNR,KDAUF,KDPOS,PLNBEZ,GAMNG,GSTRP,GLTRP,GSTRI,GLTRI'
    }

    # 将查询参数添加到 headers 中
    for key, value in params.items():
        headers[key] = value

    # 清空 params 以避免重复传递
    params = {}

    # 添加查询表参数到 headers
    headers['Query-Table'] = 'CAUFV'

    try:
        print(f"✓ 请求 URL: {entity_url}")
        response = requests.get(
            entity_url,
            headers=headers,
            params=params,
            timeout=30,
            verify=sap_verify_ssl
        )

        if response.status_code != 200:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"   响应内容: {response.text[:200]}")
            return False
        data = response.json()
        if 'd' in data and 'results' in data['d']:
            results = data['d']['results']
            print(f"✓ 成功获取 {len(results)} 条数据")
            for row in results[:5]:
                print(row)
            return True
        else:
            print("⚠️  响应格式异常")
            return False

    except Exception as e:
        print(f"❌ 获取数据失败: {e}")
        return False


def main():
    """主函数"""
    print("\n🚀 开始 SAP 连通性测试...\n")
    
    # 检查 .env 文件
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env 文件不存在")
        print("\n请先创建 .env 文件:")
        print("  1. 复制模板: cp .env.example .env")
        print("  2. 编辑 .env 文件，填入 SAP 连接信息:")
        print("     - SAP_HOST")
        print("     - SAP_USERNAME")
        print("     - SAP_PASSWORD")
        print("     - SAP_ODATA_SERVICE")
        return 1
    
    print(f"✓ 找到配置文件: {env_file}")
    
    # 运行测试
    try:
        success = test_sap_connection()
        success = fetch_caufv_data()
        return 0 if success else 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        return 1
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print(f"\n详细错误信息:")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
