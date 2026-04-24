"""
查看生产时间预测结果
按物料汇总统计，方便计划员查看
"""
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger


def main():
    """查看最新的生产时间预测结果"""
    
    # 加载最新的预测结果
    predictions_dir = Path("predictions")
    
    # 找到最新的预测文件
    prediction_files = list(predictions_dir.glob("production_time_predictions_*.csv"))
    if not prediction_files:
        logger.error("未找到预测结果文件")
        return
    
    latest_file = max(prediction_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"加载预测文件: {latest_file}")
    
    # 读取数据
    df = pd.read_csv(latest_file)
    
    logger.info("\n" + "=" * 80)
    logger.info("生产时间预测结果汇总")
    logger.info("=" * 80)
    
    # 基本统计
    logger.info(f"\n📊 整体统计:")
    logger.info(f"  预测订单数: {len(df)}")
    logger.info(f"  平均实际生产时间: {df['actual'].mean():.2f} 天")
    logger.info(f"  平均预测生产时间: {df['predicted'].mean():.2f} 天")
    logger.info(f"  平均绝对误差: {df['abs_error'].mean():.2f} 天")
    logger.info(f"  RMSE: {(df['error']**2).mean()**0.5:.2f} 天")
    
    # 按物料汇总
    logger.info("\n" + "=" * 80)
    logger.info("📦 按物料汇总统计")
    logger.info("=" * 80)
    
    material_stats = df.groupby(['material', 'material_description']).agg({
        'production_number': 'count',
        'order_quantity': 'sum',
        'actual': 'mean',
        'predicted': 'mean',
        'abs_error': 'mean',
        'error': lambda x: (x**2).mean()**0.5  # RMSE
    }).round(2)
    
    material_stats.columns = ['订单数', '总数量', '实际均值(天)', '预测均值(天)', '平均误差(天)', 'RMSE(天)']
    material_stats = material_stats.sort_values('订单数', ascending=False)
    
    # 显示前20个物料
    logger.info(f"\nTop 20 物料 (按订单数排序):\n")
    print(material_stats.head(20).to_string())
    
    # 按生产线汇总
    logger.info("\n" + "=" * 80)
    logger.info("🏭 按生产线汇总统计")
    logger.info("=" * 80)
    
    line_stats = df.groupby('production_line').agg({
        'production_number': 'count',
        'order_quantity': 'sum',
        'actual': 'mean',
        'predicted': 'mean',
        'abs_error': 'mean',
        'error': lambda x: (x**2).mean()**0.5  # RMSE
    }).round(2)
    
    line_stats.columns = ['订单数', '总数量', '实际均值(天)', '预测均值(天)', '平均误差(天)', 'RMSE(天)']
    
    logger.info("\n")
    print(line_stats.to_string())
    
    # 识别预测误差较大的订单
    logger.info("\n" + "=" * 80)
    logger.info("⚠️  预测误差最大的10个订单")
    logger.info("=" * 80)
    
    top_errors = df.nlargest(10, 'abs_error')[
        ['production_number', 'material', 'material_description', 
         'order_quantity', 'actual', 'predicted', 'error', 'abs_error']
    ]
    
    logger.info("\n")
    print(top_errors.to_string(index=False))
    
    # 预测准确度分布
    logger.info("\n" + "=" * 80)
    logger.info("📈 预测准确度分布")
    logger.info("=" * 80)
    
    # 按误差范围分组
    df['error_range'] = pd.cut(
        df['abs_error'],
        bins=[0, 0.25, 0.5, 1.0, 2.0, float('inf')],
        labels=['极优 (<0.25天)', '优 (0.25-0.5天)', '良 (0.5-1天)', '中 (1-2天)', '差 (>2天)']
    )
    
    accuracy_dist = df['error_range'].value_counts().sort_index()
    accuracy_pct = (accuracy_dist / len(df) * 100).round(1)
    
    logger.info("\n误差范围分布:")
    for range_name, count in accuracy_dist.items():
        pct = accuracy_pct[range_name]
        logger.info(f"  {range_name:20s}: {count:4d} 订单 ({pct:5.1f}%)")
    
    # 保存汇总报告
    logger.info("\n" + "=" * 80)
    logger.info("💾 保存汇总报告")
    logger.info("=" * 80)
    
    # 保存物料汇总
    material_report_path = predictions_dir / "production_time_summary_by_material.csv"
    material_stats.to_csv(material_report_path)
    logger.info(f"✓ 物料汇总已保存: {material_report_path}")
    
    # 保存生产线汇总
    line_report_path = predictions_dir / "production_time_summary_by_line.csv"
    line_stats.to_csv(line_report_path)
    logger.info(f"✓ 生产线汇总已保存: {line_report_path}")
    
    # 保存高误差订单
    error_report_path = predictions_dir / "production_time_high_errors.csv"
    df.nlargest(50, 'abs_error').to_csv(error_report_path, index=False)
    logger.info(f"✓ 高误差订单已保存: {error_report_path}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ 分析完成！")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
