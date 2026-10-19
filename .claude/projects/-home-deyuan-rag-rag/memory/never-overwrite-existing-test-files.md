---
name: never-overwrite-existing-test-files
description: 禁止用 cat > 覆盖已有测试文件，必须先 Read 确认文件是否存在
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 40b50c82-bcaa-46f9-bfde-2226c5d4ba80
---

写测试文件时，禁止用 `cat > path << 'EOF'` 覆盖已有文件。这会把原有测试全部抹掉。

**为什么：** 2026-06-21 写后端测试时，用 `cat > tests/health/test_cache.py` 覆盖了已有 8 个测试的文件，只留了 2 个；用 `cat > tests/generation/test_query_engine.py` 覆盖了已有 4 个测试的文件，少了 `test_build_query_engine_callable`。用户指出后才发现。

**怎么避免：**
1. 写文件前先 `Read` 或 `ls` 确认目标是否存在
2. 如果文件已存在，用 `Edit` 追加或修改，不要用 `Write` 或 `cat >` 全量覆盖
3. 不确定时先 `ls` 看一眼
