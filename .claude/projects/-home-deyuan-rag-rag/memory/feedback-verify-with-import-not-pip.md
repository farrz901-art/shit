---
name: feedback-verify-with-import
description: "验证 Python 包是否安装要用 `python -c \"import X\"`，不能只信 `pip show X` — pip 和 python 可能指向不同环境"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

**错误：** 在 [[project-mineru-docker-integration]] 调试中，我用 `pip show docker` 返回 "Package(s) not found" 就下结论"venv 里 docker 库没装"。但用户指出 docker 库在 venv 里其实是装好的。

**为什么犯这个错：** 在用户的 Windows + Git Bash 环境下，`which pip` 指向 `/c/Users/abcuc/AppData/Local/Python/bin/pip`（系统全局），而 `which python` 指向 `/.venv/Scripts/python`（venv）。两个命令在不同环境查东西，`pip show` 查的是系统全局，venv 里的 docker 自然找不到。

**教训：**
- 验证 Python 包是否安装：**用 `python -c "import X; print(X.__version__)"`**，因为它走的是当前激活的 python 的 site-packages
- `pip show X` 的结果取决于 `pip` 命令指向哪个环境，**不一定等于**当前 python 的环境
- 看到 `pip show` 报"未找到"时，**不要**立即下结论，先用 import 交叉验证
- 在 venv 里工作时，可以先 `which python && which pip` 检查两者是否一致；如果不一致要警觉

**How to apply:** 任何"包是否安装"的问题，第一反应是 `python -c "import X"`，不是 `pip show X`。
