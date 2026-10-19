"""压缩包解压处理器（zip only）

设计：
- 零依赖（用 stdlib zipfile）
- 防 zip bomb：max_total_size + max_file_count 双保险
- 防 zip slip：解压时校验路径在 target_dir 内
- 嵌套深度可配：max_depth=1 不递归
"""

from __future__ import annotations

import zipfile
from pathlib import Path


class ArchiveError(Exception):
    """压缩包处理基类异常"""


class UnsupportedArchiveError(ArchiveError):
    """不支持的压缩格式（不是 .zip）"""


class ArchiveSecurityError(ArchiveError):
    """超过安全限制（zip bomb / zip slip）"""


class ArchivePasswordError(ArchiveError):
    """加密压缩包（不支持）"""


class ArchiveCorruptError(ArchiveError):
    """压缩包损坏 / 无法读取"""


class ArchiveHandler:
    """解压压缩包到目标目录"""

    SUPPORTED_EXTENSIONS = [".zip"]

    def __init__(
        self,
        max_depth: int = 1,
        max_total_size: int = 1 << 30,
        max_file_count: int = 10_000,
    ):
        self.max_depth = max_depth
        self.max_total_size = max_total_size
        self.max_file_count = max_file_count

    def is_supported(self, archive_path: Path) -> bool:
        """是否支持的压缩格式"""
        return archive_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, archive_path: Path, target_dir: Path, depth: int = 1) -> list[Path]:
        """解压到 <target_dir>/<archive_stem>/，返回解压出的所有文件路径

        修复前：直接用 zipfile.extractall()，无任何安全校验（zip bomb / zip slip 风险）
        修复后：分 entry 校验
            1. 加密检测：flag_bits & 0x1 → 抛 ArchivePasswordError
            2. Zip Slip 防御：resolve().is_relative_to(extract_root)
            3. 累计 file_size，超过 max_total_size → 抛 ArchiveSecurityError
            4. 累计文件数，超过 max_file_count → 抛 ArchiveSecurityError
        为什么：zip bomb 攻击者用极小压缩体积骗解压，file_size（解压后）才是真正要拦的

        Args:
            archive_path: 压缩包绝对路径
            target_dir: 解压根目录（产物放 <target_dir>/<archive_stem>/）
            depth: 当前嵌套深度（递归解压用，默认 1）

        Returns:
            解压出的所有文件路径（绝对）

        Raises:
            UnsupportedArchiveError: 不支持的格式
            ArchiveSecurityError: 超过大小/文件数上限 / Zip Slip
            ArchivePasswordError: 加密压缩包
            ArchiveCorruptError: 损坏的压缩包
        """
        if not self.is_supported(archive_path):
            raise UnsupportedArchiveError(
                f"不支持的压缩格式: {archive_path.suffix}（当前只支持 {self.SUPPORTED_EXTENSIONS}）"
            )

        # 准备解压目标子目录
        archive_stem = archive_path.stem
        extract_root = (target_dir / archive_stem).resolve()
        extract_root.mkdir(parents=True, exist_ok=True)

        results: list[Path] = []
        total_size = 0
        file_count = 0

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # 检查加密（python 3.14 zipfile 无 is_encrypted 全部 info 的便捷方法，
                # 遍历 info 看 flag_bits）
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # 0x1 = encrypted
                        raise ArchivePasswordError(f"压缩包加密，无法解压: {archive_path.name}（请手动解压）")

                # 解压每个 entry
                for info in zf.infolist():
                    # Zip Slip 防御：解析后的目标路径必须在 extract_root 内
                    target_path = (extract_root / info.filename).resolve()
                    if not target_path.is_relative_to(extract_root):
                        raise ArchiveSecurityError(f"Zip Slip 检测: {info.filename} 试图跳出 {extract_root}")

                    # 大小累计
                    total_size += info.file_size
                    if total_size > self.max_total_size:
                        raise ArchiveSecurityError(f"解压超过大小限制 {self.max_total_size} 字节: {archive_path.name}")

                    file_count += 1
                    if file_count > self.max_file_count:
                        raise ArchiveSecurityError(f"解压超过文件数限制 {self.max_file_count}: {archive_path.name}")

                    # 实际解压
                    zf.extract(info, extract_root)
                    if target_path.is_file():
                        results.append(target_path)
        except zipfile.BadZipFile as e:
            raise ArchiveCorruptError(f"压缩包损坏: {archive_path.name} - {e}")

        return results
