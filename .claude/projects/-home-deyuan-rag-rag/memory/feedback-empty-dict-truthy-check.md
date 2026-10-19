---
name: feedback-empty-dict-truthy-check
description: "isinstance(empty_dict, dict) 为 True, 但 empty_dict 走\"字典有数据\"分支会返空值. 必须加 truthy 守卫"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

在 `decode-llm-view` (2026-06-12) Task 2 实现 `build_llm_view` 时: cfg 顶层有 `manufacturer: Siemens` 字符串 (没 `metadata.manufacturer` 字典). 实现写:
```python
mfr_meta = meta.get("manufacturer", {})
if isinstance(mfr_meta, dict):  # ← bug: 空 {} 也是 dict
    mfr_zh = mfr_meta.get("zh") or mfr_meta.get("code", "")
    # mfr_meta.get("zh") 返 None, 然后 or "" → mfr_zh = ""
```
结果: `厂商: ` / `Manufacturer: ` / `系列: ` / `Series: ` 全空. 8 个 unit test 全过 (它们只 assert "key 存在" 不 assert 值真). 实际 `curl /decode` 才发现空值.

**Why**: unit test 弱 (assert key 存在 而不是 assert 值真), 加上 isinstance 不做 truthy check — 两个失误叠加导致 bug 漏到集成层.

**How to apply**:
- isinstance(x, dict) 必须配 `and x:` (truthy check), 不然空 dict 走"有数据"分支
- 类似: `if isinstance(x, list):` 必须 `and x:`, `if isinstance(x, str):` 已经隐含 truthy
- Unit test 应该 assert 真值 (`assert "厂商: Siemens" in llm`) 不只 assert key 存在 (`assert any("厂商:" in line for line in llm)`)
- 关联: [[feedback-tdd-test-real-behavior-not-just-no-crash]] / [[feedback-no-mock-for-external-systems]] (curl 集成测试抓到了 unit test 漏的真 bug)
