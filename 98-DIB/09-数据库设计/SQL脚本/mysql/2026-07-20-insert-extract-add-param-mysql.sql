-- 增加一条配置项: 多模态转换提示词配置，用于VL转换器
INSERT INTO p_mdm_sys_param (id, param_name, param_type, param_code, param_value, param_desc, del_flag, add_user_id, add_user_name, add_time, update_user_id, update_user_name, update_time)
VALUES (1528782784137068544, '多模态转换提示词', 2, 'CONVERTER_VL_PROMPT', '请将图片中的内容转换为标准的Markdown格式。

# 转换要求
1. **页面主标题**：使用 # 一级标题（每页最多一个，不超过15字）
2. **章节标题**：使用 ## 二级标题或 ### 三级标题
3. **表格处理**：识别表格结构并转换为Markdown表格格式（使用 | 分隔）
4. **列表处理**：将项目符号列表转换为标准Markdown列表（- 或 1. 2. 3.）
5. **普通文本**：保持原文段落结构，合理换行
6. **数据精确**：所有数字、专有名词必须100%精确复制
7. **忠实原文**：不要概括、补充或修改原文内容
8. **页眉信息**：使用引用块（> 页眉内容）
9. **单位信息**：使用粗体标注（**单位：万元**）
10. **适用性标识**：使用删除线（~~本报告适用于内部审计~~）

# 输出格式
直接输出Markdown格式的文本，不要有任何其他解释或说明。', '', 0, NULL, NULL, NULL, NULL, 'de', '2026-07-20 15:16:59');