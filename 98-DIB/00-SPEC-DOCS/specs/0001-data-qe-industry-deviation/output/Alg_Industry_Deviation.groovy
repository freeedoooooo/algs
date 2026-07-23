package indexFunc.industry

import cn.hutool.db.sql.SqlUtil
import com.dib.agent.data.source.DataQueryInfrastructure
import com.dib.agent.data.web.config.constant.DibIndexConst
import com.dib.agent.data.web.model.index.req.DataIndexCalcReq
import com.dib.agent.data.web.util.DibSqlBuilder
import com.dib.agent.data.web.util.IndexSqlUtil
import com.dib.agent.data.web.util.SpringContextUtil
import org.slf4j.Logger
import org.slf4j.LoggerFactory

/**
 * 行业偏离度算子
 * 
 * 算法步骤：
 * 1. 行业动态级别调整（三级→二级→一级）
 * 2. 计算行业中位数和中位差
 * 3. 计算全局中位差中位数 m1
 * 4. 计算有效值范围 [m - 3*m1, m + 3*m1]
 * 5. 剔除异常值，计算行业均值
 * 6. 计算行业偏离度
 *
 * @author AI Assistant
 * @since 2026-03-05
 */
List<Map<String, Object>> calc(
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
) {
    Logger log = LoggerFactory.getLogger(this.class)
    DataIndexCalcReq calcReq = getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME) as DataIndexCalcReq
    
    log.info("【行业算子】开始计算指标 {} 的行业偏离度", calcReq.getIndexCode())
    log.debug("【行业算子】度量字段 = {}", measureField)
    log.debug("【行业算子】公司维度字段 = {}", companyDimField)
    log.debug("【行业算子】行业维度字段 = L1:{}, L2:{}, L3:{}", industryL1Field, industryL2Field, industryL3Field)
    
    try {
        // 参数校验
        if (!measureField) {
            throw new IllegalArgumentException("度量字段不能为空")
        }
        if (!companyDimField) {
            throw new IllegalArgumentException("公司维度字段不能为空")
        }
        if (!industryL1Field || !industryL2Field || !industryL3Field) {
            throw new IllegalArgumentException("行业维度字段不能为空")
        }
        
        // 获取数据源编码
        String dataSourceCode = IndexSqlUtil.getDataSourceCode(calcReq)
        log.debug("【行业算子】数据源编码 = {}", dataSourceCode)
        
        // 获取表名和基础查询（参考 Alg1、Alg6）
        DibSqlBuilder dibSqlBuilder = IndexSqlUtil.generateSqlBuilder(calcReq)
        String tableName = dibSqlBuilder.getTableName()
        log.debug("【行业算子】表名 = {}", tableName)
        
        // 构建 SQL
        String sql = buildIndustryDeviationSql(
            tableName, 
            measureField, 
            companyDimField,
            industryL1Field,
            industryL2Field,
            industryL3Field
        )
        
        log.debug("【行业算子】SQL =\n {}", SqlUtil.formatSql(sql))
        
        // 执行查询
        List<Map<String, Object>> resultList = SpringContextUtil.getBean(DataQueryInfrastructure.class)
            .queryRows(dataSourceCode, sql)
        
        // 结果校验
        if (resultList.isEmpty()) {
            log.warn("【行业算子】未查询到数据，请检查输入参数和数据源")
        }
        
        log.info("【行业算子】计算完成，返回 {} 条记录", resultList.size())
        
        return resultList
        
    } catch (Exception e) {
        log.error("【行业算子】计算失败：{}", e.getMessage(), e)
        throw e
    }
}

/**
 * 构建行业偏离度计算 SQL
 * 
 * @param tableName 表名
 * @param measureField 度量字段名
 * @param companyDimField 公司维度字段名
 * @param industryL1Field 一级行业维度字段名
 * @param industryL2Field 二级行业维度字段名
 * @param industryL3Field 三级行业维度字段名
 * @return SQL 语句
 */
private String buildIndustryDeviationSql(
    String tableName,
    String measureField,
    String companyDimField,
    String industryL1Field,
    String industryL2Field,
    String industryL3Field
) {
    // 构建完整 SQL（使用 CTE 链式查询）
    String sql = """
        WITH 
        -- Step 1: 获取基础数据
        base_data AS (
            SELECT 
                report_date,
                ${companyDimField} as company_code,
                ${industryL1Field} as industry_l1_code,
                ${industryL2Field} as industry_l2_code,
                ${industryL3Field} as industry_l3_code,
                ${measureField} as origin_value
            FROM ${tableName}
            WHERE ${measureField} IS NOT NULL
        ),
        
        -- Step 2: 统计三级行业公司数量
        industry_l3_count AS (
            SELECT 
                industry_l3_code,
                COUNT(DISTINCT company_code) as company_count
            FROM base_data
            GROUP BY industry_l3_code
        ),
        
        -- Step 3: 统计二级行业公司数量
        industry_l2_count AS (
            SELECT 
                industry_l2_code,
                COUNT(DISTINCT company_code) as company_count
            FROM base_data
            GROUP BY industry_l2_code
        ),
        
        -- Step 4: 统计一级行业公司数量
        industry_l1_count AS (
            SELECT 
                industry_l1_code,
                COUNT(DISTINCT company_code) as company_count
            FROM base_data
            GROUP BY industry_l1_code
        ),
        
        -- Step 5: 确定每个公司的最终行业级别
        company_final_industry AS (
            SELECT 
                b.report_date,
                b.company_code,
                b.origin_value,
                CASE 
                    WHEN COALESCE(l3.company_count, 0) >= 5 THEN 3
                    WHEN COALESCE(l2.company_count, 0) >= 5 THEN 2
                    ELSE 1
                END as industry_level,
                CASE 
                    WHEN COALESCE(l3.company_count, 0) >= 5 THEN b.industry_l3_code
                    WHEN COALESCE(l2.company_count, 0) >= 5 THEN b.industry_l2_code
                    ELSE b.industry_l1_code
                END as industry_code
            FROM base_data b
            LEFT JOIN industry_l3_count l3 ON b.industry_l3_code = l3.industry_l3_code
            LEFT JOIN industry_l2_count l2 ON b.industry_l2_code = l2.industry_l2_code
            LEFT JOIN industry_l1_count l1 ON b.industry_l1_code = l1.industry_l1_code
        ),
        
        -- Step 6: 计算每个行业的中位数（参考 Alg6）
        industry_median AS (
            SELECT
                industry_code,
                AVG(origin_value) as median_value
            FROM (
                SELECT
                    industry_code,
                    origin_value,
                    ROW_NUMBER() OVER (PARTITION BY industry_code ORDER BY origin_value) as rn,
                    COUNT(*) OVER (PARTITION BY industry_code) as cnt
                FROM company_final_industry
            ) ranked
            WHERE 
                CASE 
                    WHEN cnt % 2 = 1 THEN rn = FLOOR(cnt / 2) + 1
                    ELSE rn IN (cnt DIV 2, cnt DIV 2 + 1)
                END
            GROUP BY industry_code
        ),
        
        -- Step 7: 计算每个公司的中位差
        company_median_diff AS (
            SELECT
                c.report_date,
                c.company_code,
                c.origin_value,
                c.industry_level,
                c.industry_code,
                m.median_value,
                ABS(c.origin_value - m.median_value) as median_diff
            FROM company_final_industry c
            JOIN industry_median m ON c.industry_code = m.industry_code
        ),
        
        -- Step 8: 计算全局中位差的中位数 m1
        global_median_diff AS (
            SELECT
                AVG(median_diff) as m1
            FROM (
                SELECT
                    median_diff,
                    ROW_NUMBER() OVER (ORDER BY median_diff) as rn,
                    COUNT(*) OVER () as cnt
                FROM company_median_diff
            ) ranked
            WHERE 
                CASE 
                    WHEN cnt % 2 = 1 THEN rn = FLOOR(cnt / 2) + 1
                    ELSE rn IN (cnt DIV 2, cnt DIV 2 + 1)
                END
        ),
        
        -- Step 9: 计算每个行业的有效值范围
        industry_valid_range AS (
            SELECT
                m.industry_code,
                m.median_value,
                g.m1,
                m.median_value - 3 * g.m1 as valid_range_min,
                m.median_value + 3 * g.m1 as valid_range_max
            FROM industry_median m
            CROSS JOIN global_median_diff g
        ),
        
        -- Step 10: 剔除异常值，计算行业均值
        industry_avg AS (
            SELECT
                c.industry_code,
                AVG(c.origin_value) as industry_avg
            FROM company_median_diff c
            JOIN industry_valid_range r ON c.industry_code = r.industry_code
            WHERE c.origin_value BETWEEN r.valid_range_min AND r.valid_range_max
            GROUP BY c.industry_code
        ),
        
        -- Step 11: 计算最终结果
        final_result AS (
            SELECT
                c.report_date,
                c.report_date as dim_report_date,
                c.company_code,
                c.company_code as dim_company_code,
                c.industry_level,
                c.industry_code,
                c.origin_value,
                c.median_value,
                c.median_diff,
                r.valid_range_min,
                r.valid_range_max,
                a.industry_avg,
                CASE 
                    WHEN a.industry_avg != 0 THEN 
                        (c.origin_value - a.industry_avg) / ABS(a.industry_avg)
                    ELSE 
                        c.origin_value - a.industry_avg
                END as industry_deviation
            FROM company_median_diff c
            JOIN industry_valid_range r ON c.industry_code = r.industry_code
            JOIN industry_avg a ON c.industry_code = a.industry_code
        )
        
        SELECT 
            report_date,
            dim_report_date,
            company_code,
            dim_company_code,
            industry_level,
            industry_code,
            origin_value,
            median_value,
            median_diff,
            valid_range_min,
            valid_range_max,
            industry_avg,
            industry_deviation,
            industry_deviation as index_value
        FROM final_result
        ORDER BY industry_code, company_code
    """
    
    return sql
}
