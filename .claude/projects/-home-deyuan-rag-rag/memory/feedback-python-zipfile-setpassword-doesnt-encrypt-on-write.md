---
name: feedback-python-zipfile-setpassword-doesnt-encrypt-on-write
description: Python stdlib zipfile.setpassword 只对读有效，写时不真加密且不留 flag_bits 0x1；测加密 zip 必须手工构造 PKZIP 加密字节
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5d26cefb-915c-4256-aa9f-e0d5a5f59c02
---

**问题**：Python stdlib `zipfile.setpassword(b"pass")` + `writestr("a.txt", ...)` 写出来的 zip **没有真加密**（flag_bits 加密位 0x1 被重置为 0），跟直觉相反。

**踩坑时间**：2026-06-02，Task 9 写 ArchiveHandler.extract 加密测试时
**影响**：原 plan 写的 `test_extract_password_protected` 用 `setpassword` 会 false-fail，import zipfile 加密检测路径没被测到
**正确做法**：测试里手工构造 PKZIP 传统加密算法的 zip 字节（CRCTable + 3-key stream cipher + LFH/CDH/EOCD 拼接），让 flag_bits 真带 0x0001。代码量约 80 行，但测的是真端到端。

**备选方案**：
- 用 `pyzipper`（额外依赖）写 AES 加密 zip
- 改测"if 0x1 flag detected 抛 ArchivePasswordError"的 mock 单元（违反"不信 mock"原则，不推荐）

**Why**：Python zipfile 模块的 `setpassword` 设计是给"读取别人加密的 zip"用的，**写**时是 plaintext，且不会因为 setpassword 而把 flag_bits 加密位设上。这是 stdlib 文档里写得不清楚的 trap。

**How to apply**：以后写"加密 zip"相关测试，**先**查 Python zipfile 写时是否真加密——默认不真。如果要真测试加密检测路径，必须手工构造 PKZIP 加密字节或换 `pyzipper`。如果只是测"能写入带密码的 zip 字段"，那 setpassword 的 stdlib 行为就是空操作。

**关联**：
- 跟 [[feedback-no-mock-for-external-systems]] 互补——避免 mock 反而要走更复杂的字节构造
- 跟 [[project-rag-pdf-pipeline]] 的 archive_handler 实现有关
