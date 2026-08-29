"""Interface PlatformPack — FR-PLT-02, NFR-05, ADR-09.

Không có mã TC riêng trong EAA-STP-04 vì tính tổng quát được chốt sau khi kế
hoạch kiểm thử phát hành (nó đến cùng ADR-09). TC-38 canh chiều "engine không
biết gì về phần cứng"; bộ test này canh chiều còn lại: **pack khai báo đủ và
đúng để engine không cần biết**.

Hai chiều đó phải cùng xanh thì câu "thêm họ MCU mới = thêm một pack, không
sửa engine" mới là một sự thật kiểm chứng được chứ không phải một nguyện vọng.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from eaa.platform import (
    CONFIRM_REQUIRED_CAPABILITIES,
    REQUIRED_CAPABILITIES,
    PackError,
    PackManifest,
    ParseSpec,
    ToolInvocation,
    discover_packs,
    load_manifest,
)

PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"


def _viet_pack(tmp_path: Path, noi_dung: str) -> Path:
    root = tmp_path / "mypack"
    root.mkdir()
    (root / "pack.yaml").write_text(textwrap.dedent(noi_dung), encoding="utf-8")
    return root


PACK_TOI_THIEU = """
    pack: demo
    version: 0.1.0
    capabilities:
      compile:
        command: [cc, -o, "{output}", "{source}"]
      size:
        command: [sizer, "{binary}"]
      static:
        command: [linter, "{source}"]
    """


# --------------------------------------------------------------------------
# Pack AVR thật của MVP
# --------------------------------------------------------------------------


def test_pack_avr_nap_duoc_va_du_nang_luc() -> None:
    manifest = load_manifest(PACKS_DIR / "avr")

    assert manifest.name == "avr"
    for nang_luc in REQUIRED_CAPABILITIES:
        assert manifest.has(nang_luc), f"pack AVR thiếu năng lực {nang_luc}"
    assert manifest.has("flash") and manifest.has("sim")


def test_pack_avr_khai_bao_nap_firmware_can_xac_nhan() -> None:
    """FR-DIA-02: nạp firmware luôn cần người xác nhận."""
    manifest = load_manifest(PACKS_DIR / "avr")
    assert manifest.invocation("flash").requires_confirmation is True


def test_pack_avr_do_kich_thuoc_tra_ve_du_so_lieu_cho_nguong_de_cuong() -> None:
    """Ngưỡng Flash < 50% / RAM < 40% (STP-04 §5) cần đúng các khóa này."""
    metrics = load_manifest(PACKS_DIR / "avr").invocation("size").parse.metric_regex
    for khoa in ("flash_bytes", "flash_pct", "sram_bytes", "sram_pct"):
        assert khoa in metrics, f"pack AVR không đo được {khoa}"


def test_discover_packs_thay_pack_avr() -> None:
    packs = discover_packs(PACKS_DIR)
    assert "avr" in packs
    assert all(isinstance(p, PackManifest) for p in packs.values())


# --------------------------------------------------------------------------
# Lược đồ manifest — pack sai phải bị chặn NGAY LÚC NẠP
# --------------------------------------------------------------------------


def test_pack_toi_thieu_hop_le(tmp_path: Path) -> None:
    manifest = load_manifest(_viet_pack(tmp_path, PACK_TOI_THIEU))
    assert manifest.name == "demo"
    assert not manifest.has("flash")


def test_thieu_nang_luc_bat_buoc_bi_chan(tmp_path: Path) -> None:
    root = _viet_pack(
        tmp_path,
        """
        pack: demo
        version: 0.1.0
        capabilities:
          compile:
            command: [cc, "{source}"]
        """,
    )
    with pytest.raises(PackError, match="thiếu năng lực bắt buộc"):
        load_manifest(root)


@pytest.mark.parametrize("nang_luc", sorted(CONFIRM_REQUIRED_CAPABILITIES))
def test_nang_luc_cham_thiet_bi_that_ma_khong_can_xac_nhan_bi_tu_choi(
    tmp_path: Path, nang_luc: str
) -> None:
    """Không thể có pack nào lách yêu cầu xác nhận của con người."""
    root = _viet_pack(
        tmp_path,
        f"""
        pack: demo
        version: 0.1.0
        capabilities:
          compile:
            command: [cc, "{{source}}"]
          size:
            command: [sizer, "{{binary}}"]
          static:
            command: [linter, "{{source}}"]
          {nang_luc}:
            command: [loader, "{{binary}}"]
        """,
    )
    with pytest.raises(PackError, match="requires_confirmation"):
        load_manifest(root)


def test_nang_luc_la_bi_tu_choi_thay_vi_bo_qua_am_tham(tmp_path: Path) -> None:
    root = _viet_pack(
        tmp_path,
        """
        pack: demo
        version: 0.1.0
        capabilities:
          compile: {command: [cc, "{source}"]}
          size: {command: [sizer, "{binary}"]}
          static: {command: [linter, "{source}"]}
          teleport: {command: [beam, "{binary}"]}
        """,
    )
    with pytest.raises(PackError, match="không nhận biết"):
        load_manifest(root)


def test_command_dang_chuoi_shell_bi_tu_choi(tmp_path: Path) -> None:
    """Chạy qua shell mở đường chèn lệnh và làm mẫu lệ thuộc hệ điều hành."""
    root = _viet_pack(
        tmp_path,
        """
        pack: demo
        version: 0.1.0
        capabilities:
          compile:
            command: "cc -o out {source}"
          size: {command: [sizer, "{binary}"]}
          static: {command: [linter, "{source}"]}
        """,
    )
    with pytest.raises(PackError, match="danh sách argv"):
        load_manifest(root)


def test_yaml_hong_va_thieu_truong_bat_buoc(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "pack.yaml").write_text("pack: [khong: dong]: :", encoding="utf-8")
    with pytest.raises(PackError, match="YAML không hợp lệ"):
        load_manifest(root)

    (root / "pack.yaml").write_text("version: 1.0\n", encoding="utf-8")
    with pytest.raises(PackError, match="thiếu trường bắt buộc"):
        load_manifest(root)


def test_khong_co_manifest_bao_loi_ro_rang(tmp_path: Path) -> None:
    with pytest.raises(PackError, match="Không tìm thấy manifest"):
        load_manifest(tmp_path / "khong-ton-tai")


def test_regex_hong_trong_pack_bi_bat_luc_nap(tmp_path: Path) -> None:
    root = _viet_pack(
        tmp_path,
        """
        pack: demo
        version: 0.1.0
        capabilities:
          compile:
            command: [cc, "{source}"]
            parse: {error_regex: "([unclosed"}
          size: {command: [sizer, "{binary}"]}
          static: {command: [linter, "{source}"]}
        """,
    )
    with pytest.raises(PackError, match="biểu thức chính quy"):
        load_manifest(root)


def test_metric_regex_phai_co_dung_mot_nhom_bat() -> None:
    with pytest.raises(PackError, match="đúng 1 nhóm"):
        ParseSpec(metric_regex={"flash_bytes": r"Program:\s+\d+"})
    with pytest.raises(PackError, match="đúng 1 nhóm"):
        ParseSpec(metric_regex={"flash_bytes": r"(a)(b)"})
    ParseSpec(metric_regex={"flash_bytes": r"Program:\s+(\d+)"})  # hợp lệ


# --------------------------------------------------------------------------
# Dựng argv từ mẫu
# --------------------------------------------------------------------------


def test_resolve_thay_dung_cho_giu() -> None:
    goi = ToolInvocation(command=("cc", "-o", "{output}", "{source}"))
    assert goi.placeholders() == {"output", "source"}
    assert goi.resolve({"output": "a.elf", "source": "a.c"}) == [
        "cc",
        "-o",
        "a.elf",
        "a.c",
    ]


def test_resolve_thieu_tham_so_thi_bao_loi_chu_khong_de_lai_cho_giu() -> None:
    """Một argv còn nguyên "{output}" sẽ tạo ra file tên "{output}" — im lặng
    sai còn tệ hơn dừng lại."""
    goi = ToolInvocation(command=("cc", "-o", "{output}", "{source}"))
    with pytest.raises(PackError, match="Thiếu tham số"):
        goi.resolve({"source": "a.c"})


def test_command_rong_va_timeout_am_bi_tu_choi() -> None:
    with pytest.raises(PackError):
        ToolInvocation(command=())
    with pytest.raises(PackError):
        ToolInvocation(command=("cc",), timeout_s=0)
