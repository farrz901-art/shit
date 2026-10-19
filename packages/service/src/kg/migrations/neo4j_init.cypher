-- Neo4j dataset label 索引 (2026-07-01 markdown extract KG spec PR1, v3)
--
-- 用途: 给 :Motor :Plc 等 dataset label 建索引, 加速 WHERE n:`Motor` 过滤
--
-- v3 设计: 项目用 Neo4j Community Edition (1 database only), 用 dataset label 隔离
-- env KG_ALLOWED_DATASETS 白名单控制允许的 dataset (motor/plc/sensor)
-- v3: 不加 (label,key) 唯一约束 (不同 dataset 同一 key 可合法存在)
--
-- 运行: uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor

-- :Motor 索引 (对 Product / Spec / Series / Standard 业务 label 加 dataset 联合索引)
CREATE INDEX motor_product_idx IF NOT EXISTS FOR (n:Product) ON (n:`Motor`);
CREATE INDEX motor_spec_idx IF NOT EXISTS FOR (n:Spec) ON (n:`Motor`);
CREATE INDEX motor_series_idx IF NOT EXISTS FOR (n:Series) ON (n:`Motor`);
CREATE INDEX motor_standard_idx IF NOT EXISTS FOR (n:Standard) ON (n:`Motor`);

-- :Plc 索引
CREATE INDEX plc_product_idx IF NOT EXISTS FOR (n:Product) ON (n:`Plc`);
CREATE INDEX plc_spec_idx IF NOT EXISTS FOR (n:Spec) ON (n:`Plc`);
CREATE INDEX plc_series_idx IF NOT EXISTS FOR (n:Series) ON (n:`Plc`);
CREATE INDEX plc_standard_idx IF NOT EXISTS FOR (n:Standard) ON (n:`Plc`);

-- :Sensor 索引
CREATE INDEX sensor_product_idx IF NOT EXISTS FOR (n:Product) ON (n:`Sensor`);
CREATE INDEX sensor_spec_idx IF NOT EXISTS FOR (n:Spec) ON (n:`Sensor`);
CREATE INDEX sensor_series_idx IF NOT EXISTS FOR (n:Series) ON (n:`Sensor`);
CREATE INDEX sensor_standard_idx IF NOT EXISTS FOR (n:Standard) ON (n:`Sensor`);