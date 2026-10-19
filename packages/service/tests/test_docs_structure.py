"""文档结构守门测试

README 拆分 (2026-06-08):
- README 只留项目简介 + 快速启动 + 链接
- 详细内容进 docs/
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
README = REPO_ROOT / "README.md"
DOCS_DIR = REPO_ROOT / "docs"


class TestDocsSubdirsExist:
    """4 个 docs 主题文件必须存在 (deployment.md 2026-06-16 合进 README)"""

    def test_architecture_md_exists(self):
        assert (DOCS_DIR / "architecture.md").exists()

    def test_product_decoder_md_exists(self):
        assert (DOCS_DIR / "product-decoder.md").exists()

    def test_ingestion_md_exists(self):
        assert (DOCS_DIR / "ingestion.md").exists()

    def test_dev_conventions_md_exists(self):
        assert (DOCS_DIR / "dev-conventions.md").exists()


class TestReadmeLinksResolve:
    """README 里的所有相对链接必须指向真实文件"""

    def test_all_readme_links_resolve(self):
        import re

        content = README.read_text(encoding="utf-8")
        # 匹配 [text](./xxx) 或 [text](xxx) 形式
        links = re.findall(r"\]\((?!https?://|mailto:|#)([^)]+)\)", content)
        for link in links:
            # 去掉 anchor 部分
            link_path = link.split("#", 1)[0]
            if not link_path:
                continue
            target = (REPO_ROOT / link_path).resolve()
            assert target.exists(), f"README 链接指向不存在的文件: {link}"


class TestReadmeDoesNotContainExtractedSections:
    """README 不应再含详细 schema / YAML 示例 / API 列表（避免回滚）"""

    def test_readme_no_longer_has_detailed_api_table(self):
        """旧 README 的 API 详细表格应已搬走（curl 调用 + 页面链接不算）"""
        content = README.read_text(encoding="utf-8")
        # 找含 /decode 的行
        decode_lines = [line for line in content.splitlines() if "/decode" in line]
        # 排除 curl + 页面链接这种合理引用
        non_curl_lines = [
            line for line in decode_lines if "curl" not in line and "前端" not in line and "页面" not in line
        ]
        assert not non_curl_lines, f"README 不应再含 /decode 详细说明（已搬到 product-decoder.md）: {non_curl_lines}"

    def test_readme_no_longer_has_full_schema_example(self):
        """旧 README 的完整 JSON Schema 示例应已搬走"""
        content = README.read_text(encoding="utf-8")
        assert "efficiency_grade_zh" not in content, "README 不应再含完整 JSON Schema（已搬到 product-decoder.md）"
