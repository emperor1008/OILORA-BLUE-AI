"""Tests for file upload and validation."""

import os

from app.services.file_service import FileService


class TestFileService:
    """Test suite for file validation and upload service."""

    def test_sanitize_filename_normal(self):
        """Test normal filenames pass through."""
        assert FileService.sanitize_filename("data.tif") == "data.tif"
        assert FileService.sanitize_filename("my_file.csv") == "my_file.csv"

    def test_sanitize_filename_path_traversal(self):
        """Test path traversal is removed."""
        result = FileService.sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_filename_dangerous_chars(self):
        """Test dangerous characters are sanitized."""
        result = FileService.sanitize_filename('file<name>:test|"data*.nc')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "*" not in result

    def test_sanitize_filename_null_bytes(self):
        """Test null bytes are removed."""
        result = FileService.sanitize_filename("file\x00.tif")
        assert "\x00" not in result
        assert result == "file.tif"

    def test_sanitize_filename_empty(self):
        """Test empty filename gets fallback."""
        assert FileService.sanitize_filename("") == "unnamed_file"
        assert FileService.sanitize_filename("...") == "unnamed_file"

    def test_sanitize_filename_long(self):
        """Test very long filenames are truncated."""
        long_name = "a" * 300 + ".tif"
        result = FileService.sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".tif")

    def test_validate_extension_sar(self):
        """Test SAR file extension validation."""
        ok, _ = FileService.validate_file_extension("scene.tif", "sar")
        assert ok is True
        ok, _ = FileService.validate_file_extension("scene.tiff", "sar")
        assert ok is True
        ok, msg = FileService.validate_file_extension("scene.txt", "sar")
        assert ok is False
        assert "Invalid extension" in msg

    def test_validate_extension_ais(self):
        """Test AIS file extension validation."""
        ok, _ = FileService.validate_file_extension("vessels.csv", "ais")
        assert ok is True
        ok, _ = FileService.validate_file_extension("vessels.parquet", "ais")
        assert ok is True
        ok, _ = FileService.validate_file_extension("vessels.tif", "ais")
        assert ok is False

    def test_validate_extension_environmental(self):
        """Test environmental file extension validation."""
        ok, _ = FileService.validate_file_extension("wind.nc", "environmental")
        assert ok is True
        ok, _ = FileService.validate_file_extension("ocean.nc4", "environmental")
        assert ok is True
        ok, _ = FileService.validate_file_extension("ocean.csv", "environmental")
        assert ok is False

    def test_validate_file_size_empty(self, tmp_path):
        """Test empty file is rejected."""
        empty_file = tmp_path / "empty.tif"
        empty_file.write_bytes(b"")
        ok, msg = FileService.validate_file_size(str(empty_file))
        assert ok is False
        assert "empty" in msg.lower()

    def test_validate_file_size_valid(self, tmp_path):
        """Test valid file size passes."""
        test_file = tmp_path / "data.tif"
        test_file.write_bytes(b"\x00" * 1024)  # 1 KB
        ok, _ = FileService.validate_file_size(str(test_file))
        assert ok is True

    def test_check_magic_bytes_geotiff(self, tmp_path):
        """Test GeoTIFF magic byte detection."""
        tiff_file = tmp_path / "scene.tif"
        # TIFF LE magic bytes
        tiff_file.write_bytes(b"II\x2a\x00" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(tiff_file), "sar")
        assert ok is True
        assert "Valid" in msg

    def test_check_magic_bytes_mask_tiff(self, tmp_path):
        """Test TIFF masks pass mask magic-byte validation."""
        tiff_file = tmp_path / "mask.tif"
        tiff_file.write_bytes(b"II\x2a\x00" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(tiff_file), "mask")
        assert ok is True
        assert "TIFF" in msg

    def test_check_magic_bytes_mask_png(self, tmp_path):
        """Test PNG masks pass mask magic-byte validation (regression: the mask
        branch used to be unreachable, so PNG masks were always rejected)."""
        png_file = tmp_path / "mask.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(png_file), "mask")
        assert ok is True
        assert "PNG" in msg

    def test_check_magic_bytes_mask_jpeg(self, tmp_path):
        """Test JPEG masks pass mask magic-byte validation."""
        jpeg_file = tmp_path / "mask.jpg"
        jpeg_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(jpeg_file), "mask")
        assert ok is True
        assert "JPEG" in msg

    def test_check_magic_bytes_mask_rejects_text(self, tmp_path):
        """Test non-image files are rejected as masks."""
        txt_file = tmp_path / "mask.png"
        txt_file.write_bytes(b"not really a png\n")
        ok, msg = FileService.check_magic_bytes(str(txt_file), "mask")
        assert ok is False
        assert "Expected" in msg

    def test_check_magic_bytes_png_rejected_as_sar(self, tmp_path):
        """Test PNG files are rejected as SAR imagery."""
        png_file = tmp_path / "scene.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(png_file), "sar")
        assert ok is False
        assert "Expected TIFF/GeoTIFF" in msg

    def test_check_magic_bytes_netcdf(self, tmp_path):
        """Test NetCDF magic byte detection."""
        nc_file = tmp_path / "data.nc"
        # HDF5/NetCDF4 magic bytes
        nc_file.write_bytes(b"\x89\x48\x44\x46" + b"\x00" * 100)
        ok, _ = FileService.check_magic_bytes(str(nc_file), "environmental")
        assert ok is True

    def test_check_magic_bytes_executable_rejected(self, tmp_path):
        """Test executable files are rejected."""
        exe_file = tmp_path / "malware.tif"
        # Windows PE magic bytes
        exe_file.write_bytes(b"MZ" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(exe_file), "sar")
        assert ok is False
        assert "executable" in msg.lower()

    def test_check_magic_bytes_elf_rejected(self, tmp_path):
        """Test ELF executables are rejected."""
        elf_file = tmp_path / "program.tif"
        elf_file.write_bytes(b"\x7fELF" + b"\x00" * 100)
        ok, msg = FileService.check_magic_bytes(str(elf_file), "sar")
        assert ok is False
        assert "executable" in msg.lower()

    def test_compute_sha256(self, tmp_path):
        """Test SHA-256 checksum computation."""
        test_file = tmp_path / "data.txt"
        test_file.write_bytes(b"Hello, Oilora Blue AI!")
        checksum = FileService.compute_sha256(str(test_file))
        assert len(checksum) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_compute_sha256_deterministic(self, tmp_path):
        """Test SHA-256 is deterministic."""
        test_file = tmp_path / "data.txt"
        test_file.write_bytes(b"Consistent data")
        c1 = FileService.compute_sha256(str(test_file))
        c2 = FileService.compute_sha256(str(test_file))
        assert c1 == c2

    def test_compute_sha256_different_files(self, tmp_path):
        """Test different files produce different checksums."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"File A")
        f2.write_bytes(b"File B")
        assert FileService.compute_sha256(str(f1)) != FileService.compute_sha256(str(f2))

    def test_validate_path_safety(self, tmp_path):
        """Test path traversal detection."""
        allowed = str(tmp_path / "uploads")
        os.makedirs(allowed, exist_ok=True)

        # Safe path
        safe = os.path.join(allowed, "file.tif")
        assert FileService.validate_path_safety(safe, allowed) is True

        # Unsafe path
        unsafe = os.path.join(tmp_path, "..", "etc", "passwd")
        assert FileService.validate_path_safety(unsafe, allowed) is False

    def test_get_mime_type(self):
        """Test MIME type detection."""
        assert FileService.get_mime_type("data.tif") == "image/tiff"
        assert FileService.get_mime_type("vessels.csv") == "text/csv"
        assert FileService.get_mime_type("wind.nc") == "application/x-netcdf"
        assert FileService.get_mime_type("vessels.parquet") == "application/octet-stream"

    def test_validate_upload_integration(self, tmp_path):
        """Test full upload validation pipeline."""
        # Create a valid GeoTIFF-like file inside the data directory
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        tiff_file = data_dir / "scene.tif"
        tiff_file.write_bytes(b"II\x2a\x00" + b"\x00" * 1024)

        result = FileService.validate_upload(str(tiff_file), "scene.tif", "sar")
        assert result["valid"] is True
        assert result["errors"] == []
        assert "sha256" in result["metadata"]
        assert result["metadata"]["mime_type"] == "image/tiff"

    def test_validate_upload_wrong_extension(self, tmp_path):
        """Test validation catches wrong extensions."""
        txt_file = tmp_path / "data.txt"
        txt_file.write_bytes(b"Hello")

        result = FileService.validate_upload(str(txt_file), "data.txt", "sar")
        assert result["valid"] is False
        assert any("extension" in e.lower() for e in result["errors"])

    def test_validate_upload_executable(self, tmp_path):
        """Test executable files are rejected."""
        exe_file = tmp_path / "sneaky.tif"
        exe_file.write_bytes(b"MZ" + b"\x00" * 1024)

        result = FileService.validate_upload(str(exe_file), "sneaky.tif", "sar")
        assert result["valid"] is False
        assert any("executable" in e.lower() for e in result["errors"])
