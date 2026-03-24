"""
生产环境预测脚本
使用训练好的模型对新的生产订单进行延迟风险预测
"""
import sys
sys.path.append('.')

import pandas as pd
from pathlib import Path
from typing import Optional, Union
from src.models.xgboost_model import ProductionDelayModel
from src.data_processing.aps_data_loader import APSDataLoader
from src.data_processing.aps_feature_engineer import APSFeatureEngineer
from src.config.paths import (
    MODELS_DIR,
    INFERENCE_OUTPUT_DIR,
    get_latest_aps_model_path,
)
from loguru import logger
from datetime import datetime


def predict_new_orders(
    new_orders_csv: Union[str, Path],
    model_path: Optional[Union[str, Path]] = None,
    output_csv: Optional[Union[str, Path]] = None,
):
    """
    预测新订单的延迟风险
    
    Args:
        new_orders_csv: 新订单CSV文件路径（包含Order, FG, Capacity等信息）
        model_path: 训练好的模型文件路径
        output_csv: 输出预测结果的CSV文件路径（可选）
    
    Returns:
        DataFrame: 包含预测结果的数据框
    """
    logger.info("="*60)
    logger.info("生产环境延迟风险预测")
    logger.info("="*60)
    
    # 1. 加载模型
    model_path = Path(model_path) if model_path else get_latest_aps_model_path()
    if model_path is None:
        raise FileNotFoundError(f"未找到模型文件，请先训练模型或检查目录: {MODELS_DIR}")

    logger.info(f"加载模型: {model_path}")
    model = ProductionDelayModel()
    model.load(str(model_path))
    
    # 2. 加载新订单数据
    logger.info(f"加载新订单数据: {new_orders_csv}")
    df_new = pd.read_csv(new_orders_csv)
    logger.info(f"  ✓ 加载了 {len(df_new)} 条新订单")
    
    # 3. 数据预处理
    logger.info("数据预处理中...")
    # 这里需要和训练时一样的预处理步骤
    # 包括合并FG数据、Capacity数据等
    
    # 简化版：假设CSV已包含基础字段
    # 转换日期格式
    df_new['planned_start_date'] = pd.to_datetime(df_new['planned_start_date'])
    
    # 4. 特征工程
    logger.info("生成预测特征...")
    engineer = APSFeatureEngineer(lookback_days=90)
    
    # 注意：对于新数据，历史特征需要从历史数据库中查询
    # 这里简化处理，使用默认值
    df_features = engineer.transform(df_new)
    
    # 获取模型需要的特征
    feature_names = engineer.get_feature_names()
    X_new = df_features[feature_names].fillna(0).values
    
    logger.info(f"  ✓ 生成了 {X_new.shape[1]} 个特征")
    
    # 5. 预测
    logger.info("执行预测...")
    
    # 预测延迟概率
    delay_probabilities = model.predict_proba(X_new)[:, 1]
    
    # 二分类预测（默认阈值0.5）
    predictions = model.predict(X_new)
    
    # 6. 整理结果
    df_result = df_new.copy()
    df_result['delay_probability'] = delay_probabilities
    df_result['prediction'] = predictions
    df_result['risk_level'] = df_result['delay_probability'].apply(classify_risk)
    df_result['recommendation'] = df_result['risk_level'].apply(get_recommendation)
    df_result['prediction_time'] = datetime.now()
    
    # 统计
    high_risk_count = (df_result['risk_level'] == '高风险').sum()
    medium_risk_count = (df_result['risk_level'] == '中风险').sum()
    low_risk_count = (df_result['risk_level'] == '低风险').sum()
    
    logger.info("="*60)
    logger.info("预测完成！")
    logger.info("="*60)
    logger.info(f"总订单数: {len(df_result)}")
    logger.info(f"  🔴 高风险: {high_risk_count} ({high_risk_count/len(df_result):.1%})")
    logger.info(f"  🟡 中风险: {medium_risk_count} ({medium_risk_count/len(df_result):.1%})")
    logger.info(f"  🟢 低风险: {low_risk_count} ({low_risk_count/len(df_result):.1%})")
    logger.info("="*60)
    
    # 7. 保存结果
    if output_csv:
        output_path = Path(output_csv)
    else:
        INFERENCE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = INFERENCE_OUTPUT_DIR / f"prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_result.to_csv(output_path, index=False, encoding='utf-8-sig')
    logger.info(f"✓ 预测结果已保存: {output_path}")
    
    return df_result


def classify_risk(probability: float) -> str:
    """根据延迟概率分类风险等级"""
    if probability >= 0.7:
        return "高风险"
    elif probability >= 0.4:
        return "中风险"
    else:
        return "低风险"


def get_recommendation(risk_level: str) -> str:
    """根据风险等级给出建议"""
    recommendations = {
        "高风险": "🚨 立即采取行动：调配额外资源，调整排程，或与客户沟通交期",
        "中风险": "⚠️ 密切监控：准备应急预案，提前协调资源",
        "低风险": "✅ 按计划执行：正常跟踪，定期复核"
    }
    return recommendations.get(risk_level, "正常跟踪")


def predict_single_order(order_data: dict, model_path: Optional[Union[str, Path]] = None) -> dict:
    """
    预测单个订单
    
    Args:
        order_data: 订单数据字典
        model_path: 模型路径
        
    Returns:
        预测结果字典
    
    Example:
        order = {
            'production_number': 'P001',
            'material': 'CDX6291204R5011',
            'order_quantity': 10,
            'planned_start_date': '2026-02-01',
            'total_production_time': 2.5,
            'line_capacity': 50,
            # ... 其他字段
        }
        result = predict_single_order(order)
    """
    model_path = Path(model_path) if model_path else get_latest_aps_model_path()
    if model_path is None:
        raise FileNotFoundError(f"未找到模型文件，请先训练模型或检查目录: {MODELS_DIR}")

    model = ProductionDelayModel()
    model.load(str(model_path))

    engineer = APSFeatureEngineer(lookback_days=90)
    df = pd.DataFrame([order_data])
    df['planned_start_date'] = pd.to_datetime(df['planned_start_date'])
    df_features = engineer.transform(df)
    feature_names = engineer.get_feature_names()
    X = df_features[feature_names].fillna(0).values

    delay_probability = float(model.predict_proba(X)[0, 1])
    prediction = int(model.predict(X)[0])
    risk_level = classify_risk(delay_probability)

    result = order_data.copy()
    result.update(
        {
            "delay_probability": delay_probability,
            "prediction": prediction,
            "risk_level": risk_level,
            "recommendation": get_recommendation(risk_level),
            "prediction_time": datetime.now().isoformat(),
        }
    )
    return result


def batch_predict_with_monitoring(
    orders_csv: Union[str, Path],
    model_path: Optional[Union[str, Path]] = None,
):
    """
    批量预测并输出监控报告
    
    Args:
        orders_csv: 订单CSV文件
        model_path: 模型路径
    """
    # 预测
    df_result = predict_new_orders(
        new_orders_csv=orders_csv,
        model_path=model_path,
        output_csv=None
    )
    
    # 生成监控报告
    print("\n" + "="*80)
    print("📊 高风险订单明细")
    print("="*80)
    
    high_risk = df_result[df_result['risk_level'] == '高风险'].sort_values(
        'delay_probability', ascending=False
    )
    
    if len(high_risk) > 0:
        print(f"\n发现 {len(high_risk)} 个高风险订单：\n")
        for idx, row in high_risk.head(10).iterrows():
            print(f"订单号: {row.get('production_number', 'N/A')}")
            print(f"  物料: {row.get('material', 'N/A')}")
            print(f"  数量: {row.get('order_quantity', 0):.0f}")
            print(f"  延迟概率: {row['delay_probability']:.1%}")
            print(f"  建议: {row['recommendation']}")
            print("-" * 80)
    else:
        print("✅ 未发现高风险订单")
    
    print("="*80)


if __name__ == "__main__":
    """
    使用示例
    """
    
    # 示例1: 批量预测
    print("示例1: 批量预测新订单\n")
    
    # 假设您有新的订单CSV文件
    # new_orders_csv = "data/new_orders/orders_2026_01.csv"
    # model_path = "models/aps_xgb_model_20251224_194431.json"
    
    # df_predictions = predict_new_orders(
    #     new_orders_csv=new_orders_csv,
    #     model_path=model_path,
    #     output_csv="predictions_output.csv"
    # )
    
    # print(df_predictions[['production_number', 'delay_probability', 'risk_level']].head())
    
    
    # 示例2: 单个订单预测
    print("\n示例2: 单个订单预测\n")
    
    # order = {
    #     'production_number': 'P2026001',
    #     'material': 'CDX6291204R5011',
    #     'order_quantity': 15,
    #     'planned_start_date': '2026-02-01',
    #     'total_production_time': 2.5,
    #     'line_capacity': 50,
    #     'constraint': 1.2,
    #     # ... 其他必需字段
    # }
    
    # result = predict_single_order(order, model_path)
    # print(f"延迟概率: {result['delay_probability']:.1%}")
    # print(f"风险等级: {result['risk_level']}")
    # print(f"建议: {result['recommendation']}")
    
    
    # 示例3: 带监控的批量预测
    print("\n示例3: 批量预测 + 监控报告\n")
    
    # batch_predict_with_monitoring(
    #     orders_csv="data/new_orders/orders_2026_01.csv",
    #     model_path="models/aps_xgb_model_20251224_194431.json"
    # )
    
    
    print("\n" + "="*80)
    print("使用说明:")
    print("="*80)
    print("1. 准备新订单CSV文件")
    print("2. 确保包含必需字段：material, order_quantity, planned_start_date等")
    print("3. 运行预测脚本")
    print("4. 查看输出的预测结果CSV")
    print("5. 根据风险等级采取相应行动")
    print("="*80)
