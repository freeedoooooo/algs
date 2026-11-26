"""Agent 编排层：LLM 只做选/生成/判断，值必须回锚，人不审的才自动放行。

本包不写 staging、不改 values/original/lineage；所有产物是规则草稿或判断建议，
进入执行层前必须过确定性校验。凭据只走 config 环境变量，不入库不打印。
"""
