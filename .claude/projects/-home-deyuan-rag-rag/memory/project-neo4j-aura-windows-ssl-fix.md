---
name: project-neo4j-aura-windows-ssl-fix
description: "Neo4j Aura 在 Windows 上 Python 默认 ssl 不认, 需用 certifi + URI scheme 改写"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# Neo4j Aura + Windows + Python ssl 修复

**问题**: Neo4j Aura 实例用 `neo4j+s://` scheme 连, 在 Windows 上 Python 默认 ssl 报 `certificate verify failed: self-signed certificate in certificate chain`.

**根因** (3 层):
1. **neo4j 6.x driver 限制**: `ssl_context` 只能配 `bolt://` / `neo4j://` (明文) scheme. `bolt+s://` / `neo4j+s://` 强制走系统 trust store, 改不了.
2. **Windows Python ssl 不全**: Python 3.14 自带 `ssl` 不含 Aura 用的 DigiCert / Let's Encrypt CA (0 个).
3. **certifi 有 CA 但 driver 默认不用**: `certifi` 包在 .venv 里, 含 21 个 DigiCert CA, 但 driver 不会自动用.

**修复** (`scripts/neo4j_import.py`):

1. 抽 `_normalize_uri_for_ssl_context(uri)` helper:
   - `neo4j+s://X` → `neo4j://X` (保 scheme 族)
   - `bolt+s://X` → `bolt://X` (保 scheme 族)
   - `neo4j+ssc://X` → `neo4j://X`
   - `bolt+ssc://X` → `bolt://X`
   - 无 +s/+ssc → 原样返回

2. driver 创建时显式传 `ssl_context`:
   ```python
   ssl_context = ssl.create_default_context(cafile=certifi.where())
   self._driver = GraphDatabase.driver(
       _normalize_uri_for_ssl_context(self.uri),  # 改写后
       auth=(self.user, self.password),
       ssl_context=ssl_context,
   )
   ```

3. 用户 `.env.example` 的 URI 不用改 (还是 `neo4j+s://...`), 脚本内部处理.

**安全性**: 跟 `+s` 等同 (SSL 加密 + CA 验证), 跨平台可移植 (Linux/Mac 也工作).

**Why**: 用户填了 Aura 真凭证在 .env.example, 跑 `check` 报 SSL 错, 卡在 connect 阶段.

**How to apply**:
- 新加 Neo4j 连接代码 (Python): 用 certifi + 显式 ssl_context, 别信系统 trust
- 不要用 `neo4j+ssc://` (skip verify, 不安全)
- URI scheme 改写时**保 scheme 族** (neo4j+s→neo4j, bolt+s→bolt), 别都改成 neo4j
- 测试: 真连真实 Aura 实例, 验 SSL 不报

**Related**: [[feedback-check-pyproject-deps-match-actual-imports]] (这次 bug 暴露 certifi 没在 deps 里 - 应该显式声明, 不能光靠 transitive), [[feedback-debug-distinguish-root-causes]] (3 层根因不能合并, 每次修一层都要验)
