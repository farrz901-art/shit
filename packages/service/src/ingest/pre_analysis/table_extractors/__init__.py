"""TableExtractor strategy 子包 (2026-07-06).

3 后端适配器各自一个文件:
- pymupdf_extractor.py (默认, 已装)
- camelot_extractor.py (可选 extras)
- pdfplumber_extractor.py (可选)

factory.py 提供 get_table_extractor(backend, params) 统一入口.
"""
