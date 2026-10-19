"""ArchiveHandler 单元测试"""

import struct
import zipfile
import zlib

import pytest

from src.ingest.pdf_processing.archive_handler import (
    ArchiveCorruptError,
    ArchiveHandler,
    ArchivePasswordError,
    ArchiveSecurityError,
    UnsupportedArchiveError,
)


class TestIsSupported:
    def test_zip_supported(self, tmp_path):
        """zip 是支持的格式"""
        f = tmp_path / "a.zip"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is True

    def test_rar_unsupported(self, tmp_path):
        """rar 不支持（用户决策：只 zip）"""
        f = tmp_path / "a.rar"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is False

    def test_7z_unsupported(self, tmp_path):
        """7z 不支持"""
        f = tmp_path / "a.7z"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is False

    def test_unsupported_format_raises(self, tmp_path):
        """extract 不支持格式抛 UnsupportedArchiveError"""
        f = tmp_path / "a.rar"
        f.write_bytes(b"")
        with pytest.raises(UnsupportedArchiveError):
            ArchiveHandler().extract(f, tmp_path)


@pytest.fixture
def sample_zip(tmp_path):
    """创建含 2 个文件的 zip fixture"""
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.txt", "hello")
        zf.writestr("sub/b.txt", "world")
    return zip_path


# ----- 传统 PKZIP 加密 zip 字节构造器 -----
# stdlib zipfile 写时会把 flag_bits 里的加密位重置，setpassword 也只对读生效。
# 这里手工拼一份带 encrypted 标志的 zip，足够测 flag_bits & 0x1 检测逻辑。
def _make_crc_table() -> list[int]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
        table.append(crc & 0xFFFFFFFF)
    return table


_CRC_TABLE = _make_crc_table()


def _crc32_byte(crc: int, b: int) -> int:
    return ((crc >> 8) ^ _CRC_TABLE[(crc ^ b) & 0xFF]) & 0xFFFFFFFF


def _pkzip_keys(password: bytes) -> tuple[int, int, int]:
    k0, k1, k2 = 0x12345678, 0x23456789, 0x34567890
    for p in password:
        k0 = _crc32_byte(k0, p)
        k1 = ((k1 + (k0 & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        k2 = _crc32_byte(k2, (k1 >> 24) & 0xFF)
    return k0, k1, k2


def _pkzip_encrypt_byte(keys, c: int):
    k0, k1, k2 = keys
    new_k0 = _crc32_byte(k0, c)
    new_k1 = ((k1 + (new_k0 & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
    new_k2 = _crc32_byte(k2, (new_k1 >> 24) & 0xFF)
    temp = (new_k2 | 2) & 0xFFFF
    keystream = ((temp * (temp ^ 1)) >> 8) & 0xFF
    return (new_k0, new_k1, new_k2), keystream ^ c


def _make_encrypted_zip_bytes(filename: bytes, data: bytes, password: bytes) -> bytes:
    """构造带 PKZIP 传统加密标志的 zip 字节流"""
    crc = zlib.crc32(data) & 0xFFFFFFFF
    keys = _pkzip_keys(password)
    encrypted = bytearray()
    # 12 字节加密头（11 字节随机 + 1 字节 check byte）
    for _ in range(12):
        keys, c = _pkzip_encrypt_byte(keys, 0)
        encrypted.append(c)
    for b in data:
        keys, c = _pkzip_encrypt_byte(keys, b)
        encrypted.append(c)
    enc_data = bytes(encrypted)

    # Local file header
    local = struct.pack(
        "<4sHHHHHIIIHH",
        b"PK\x03\x04",
        20,  # version needed
        0x0001,  # general purpose flag: encrypted
        0,  # compression = stored
        0,
        0,  # mod time / date
        crc,
        len(enc_data),
        len(data),
        len(filename),
        0,  # extra length
    )
    local_record = local + filename + enc_data

    # Central directory header
    cd = struct.pack(
        "<4sHHHHHHIIIHHHHHII",
        b"PK\x01\x02",
        20,
        20,
        0x0001,  # encrypted
        0,
        0,
        0,
        crc,
        len(enc_data),
        len(data),
        len(filename),
        0,
        0,
        0,
        0,
        0,
        0,
    )
    cd_record = cd + filename

    # End of central directory
    eocd = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",
        0,
        0,
        1,
        1,
        len(cd_record),
        len(local_record),
        0,
    )

    return local_record + cd_record + eocd


class TestExtract:
    def test_extract_creates_subdir_named_after_archive_stem(self, tmp_path, sample_zip):
        """解压产物在 <target>/sample/ 下（防解压冲突）"""
        result = ArchiveHandler().extract(sample_zip, tmp_path)
        assert (tmp_path / "sample" / "a.txt").exists()
        assert (tmp_path / "sample" / "sub" / "b.txt").exists()
        assert result == [
            tmp_path / "sample" / "a.txt",
            tmp_path / "sample" / "sub" / "b.txt",
        ]

    def test_extract_returns_list_of_files(self, tmp_path, sample_zip):
        """返回解压出的所有文件路径"""
        result = ArchiveHandler().extract(sample_zip, tmp_path)
        assert len(result) == 2
        assert all(p.is_file() for p in result)

    def test_extract_oversize_raises_security_error(self, tmp_path):
        """超过总大小上限抛 ArchiveSecurityError（防 zip bomb）"""
        zip_path = tmp_path / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("big.txt", "x" * 1000)
        # 限 100 字节，应该触发
        with pytest.raises(ArchiveSecurityError, match="超过大小限制"):
            ArchiveHandler(max_total_size=100).extract(zip_path, tmp_path)

    def test_extract_too_many_files_raises_security_error(self, tmp_path):
        """超过文件数上限抛 ArchiveSecurityError"""
        zip_path = tmp_path / "many.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(20):
                zf.writestr(f"f{i}.txt", "x")
        with pytest.raises(ArchiveSecurityError, match="超过文件数限制"):
            ArchiveHandler(max_file_count=10).extract(zip_path, tmp_path)

    def test_extract_blocks_zip_slip(self, tmp_path):
        """Zip Slip（路径穿越）抛 ArchiveSecurityError"""
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../evil.txt", "boom")
        with pytest.raises(ArchiveSecurityError, match="Zip Slip"):
            ArchiveHandler().extract(zip_path, tmp_path)

    def test_extract_password_protected_raises_password_error(self, tmp_path):
        """加密 zip 抛 ArchivePasswordError"""
        # stdlib zipfile 不会用 setpassword 真正加密（写时 flag_bits 被重置），
        # 改用手工构造一个带 encrypted 标志的 zip 字节流。
        # 内容不必真能解密——我们只测 flag 检测逻辑。
        zip_path = tmp_path / "encrypted.zip"
        zip_path.write_bytes(_make_encrypted_zip_bytes(b"a.txt", b"secret", b"pass"))

        with pytest.raises(ArchivePasswordError, match="加密"):
            ArchiveHandler().extract(zip_path, tmp_path)

    def test_extract_corrupt_zip_raises_corrupt_error(self, tmp_path):
        """损坏 zip 抛 ArchiveCorruptError"""
        bad = tmp_path / "corrupt.zip"
        bad.write_bytes(b"not a real zip")
        with pytest.raises(ArchiveCorruptError):
            ArchiveHandler().extract(bad, tmp_path)
