/**
 * Knowledge 模块对外 API
 * @client-bff
 */
// Knowledge 模块对外 API (2026-06-14) 批量出口
// (2026-06-15) 批量迁出: 通用组件 (BackLink/FileDropzone/EnvBadge/HealthDot/TaskStatusBadge/StatCard/
//   PageHero/EntryCard/ErrorBoundary) → components/common/; knowledge 内组件 (ActiveSwitch) →
//   App/[locale]/knowledge/_components/.
// (2026-06-15) 删 KnowledgeEmptyState (零生产调用方 + 死代码, 跟 [feedback-no-shim-no-minimal-changes] 一致)
// 留本 barrel 的只剩强 KG/domain 耦合的
//   (DatasetSwitcher / DomainSwitcher / KnowledgeTabs / SchemaBrowser / SchemaFieldRenderer)
export * from "./dataset-switcher";
export * from "./domain-switcher";
export * from "./knowledge-tabs";
export * from "./schema-browser";
export * from "./schema-field-renderer";
