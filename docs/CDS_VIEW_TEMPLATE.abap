*&---------------------------------------------------------------------*
*& CDS View Template for Production Order History
*& 生产订单历史数据 CDS View 模板
*& 
*& 用途: 为机器学习模型提供生产订单历史数据
*& 创建人: SAP 开发团队
*& 日期: 2026-01-05
*&---------------------------------------------------------------------*

@AbapCatalog.sqlViewName: 'ZPRODORDHIST'
@AbapCatalog.compiler.compareFilter: true
@AbapCatalog.preserveKey: true
@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'Production Order History for ML Training'
@OData.publish: true
@VDM.viewType: #CONSUMPTION

define view Z_PROD_ORDER_HISTORY
  as select from aufk as OrderHeader
  
  -- 生产订单数据
  association [0..1] to afko as _OrderData 
    on OrderHeader.aufnr = _OrderData.aufnr
  
  -- 销售订单关联
  association [0..1] to vbap as _SalesOrderItem
    on _OrderData.kdauf = _SalesOrderItem.vbeln
    and _OrderData.kdpos = _SalesOrderItem.posnr
  
  -- 物料描述
  association [0..1] to makt as _MaterialText
    on _OrderData.matnr = _MaterialText.matnr
    and _MaterialText.spras = $session.system_language
  
  -- 系统状态
  association [0..*] to jest as _Status
    on OrderHeader.objnr = _Status.objnr
  
{
  // 主键
  key OrderHeader.aufnr as OrderNumber,
  
  // 销售订单信息
  _OrderData.kdauf as SalesOrder,
  _OrderData.kdpos as SalesOrderItem,
  
  // 物料信息
  _OrderData.matnr as MaterialNumber,
  _MaterialText.maktx as MaterialDescription,
  
  // 状态信息
  OrderHeader.astkz as SystemStatus,
  
  // 数量信息
  @Semantics.quantity.unitOfMeasure: 'UnitOfMeasure'
  _OrderData.gamng as OrderQuantity,
  
  @Semantics.quantity.unitOfMeasure: 'UnitOfMeasure'
  _OrderData.wemng as ConfirmedQuantity,
  
  _OrderData.gmein as UnitOfMeasure,
  
  // 日期信息
  _OrderData.gstrp as BasicStartDate,
  _OrderData.gltrp as BasicFinishDate,
  _OrderData.getri as ActualFinishDate,
  
  // 时间信息（可选）
  _OrderData.gsuzp as BasicStartTime,
  _OrderData.gstrs as ActualStartDate,
  _OrderData.gstri as ActualStartTime,
  _OrderData.gltri as ActualFinishTime,
  
  // 创建信息
  OrderHeader.erdat as CreatedOn,
  OrderHeader.ernam as EnteredBy,
  
  // 生产信息
  _OrderData.fevor as ProductionSupervisor,
  _OrderData.dispo as MRPController
}

where
  // 只要已完成的订单（有实际完成日期）
  _OrderData.getri is not null
  
  // 只要已关闭的订单
  and OrderHeader.astkz like '%CLSD%'
  
  // 排除测试订单
  and OrderHeader.auart <> 'TEST';


*&---------------------------------------------------------------------*
*& CDS View for Material Master Data
*& 物料主数据 CDS View
*&---------------------------------------------------------------------*

@AbapCatalog.sqlViewName: 'ZMATMASTER'
@AbapCatalog.compiler.compareFilter: true
@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'Material Master for ML Training'
@OData.publish: true

define view Z_MATERIAL_MASTER
  as select from mara as Material
  
  association [0..1] to makt as _Text
    on Material.matnr = _Text.matnr
    and _Text.spras = $session.system_language
  
  -- 自定义表关联（需要创建）
  association [0..1] to ztable_fg_data as _FGData
    on Material.matnr = _FGData.matnr
  
{
  key Material.matnr as MaterialNumber,
  
  _Text.maktx as MaterialDescription,
  
  // 以下字段来自自定义表 ZTABLE_FG_DATA
  _FGData.arbpl as ProductionLine,
  _FGData.constraint_factor as ConstraintFactor,
  _FGData.earliest_start as EarliestStartDays,
  _FGData.prod_time as TotalProductionTime
}

where
  Material.lvorm is initial  // 未删除标记
  and Material.matnr like 'CDX%';  // 只要相关物料


*&---------------------------------------------------------------------*
*& CDS View for Line Capacity
*& 产线产能 CDS View
*&---------------------------------------------------------------------*

@AbapCatalog.sqlViewName: 'ZLINECAP'
@AbapCatalog.compiler.compareFilter: true
@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'Production Line Capacity'
@OData.publish: true

define view Z_LINE_CAPACITY
  as select from crhd as WorkCenter
  
  association [0..1] to kako as _Capacity
    on WorkCenter.objid = _Capacity.kapid
  
{
  key WorkCenter.arbpl as ProductionLine,
  
  // 标准产能
  _Capacity.kapaz as LineCapacity
}

where
  WorkCenter.werks = '1000'  // 工厂代码（根据实际调整）
  and WorkCenter.arbpl like 'VSC%';  // 只要相关产线


*&---------------------------------------------------------------------*
*& 注意事项
*&---------------------------------------------------------------------*
*
* 1. 自定义表 ZTABLE_FG_DATA 需要创建:
*    - MATNR (物料号)
*    - ARBPL (生产线)
*    - CONSTRAINT_FACTOR (最大日产能, INT4)
*    - EARLIEST_START (最早开始天数, INT4)
*    - PROD_TIME (生产时间, DEC 5,2)
*
* 2. 激活 CDS View 后，在 SEGW 中:
*    - 创建项目 Z_PROD_ORDER_ML
*    - 导入 CDS View
*    - 生成运行时对象
*    - 注册服务到 /IWFND/MAINT_SERVICE
*
* 3. 权限配置:
*    - 创建角色 Z_ML_DATA_ACCESS
*    - 分配给技术用户 ML_USER
*    - 包含权限: S_SERVICE, S_RFC, S_TABU_DIS
*
* 4. 测试 URL:
*    https://sap-server/sap/opu/odata/sap/ABB/Test/ZTTPP_APS/ProductionOrder/$metadata
*
*&---------------------------------------------------------------------*
