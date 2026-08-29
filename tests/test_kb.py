"""Bộ nạp Knowledge Base — FR-KB-01/02, FR-RAG-01, FR-KLC-01.

Bất biến trọng tâm được canh ở đây: **truy vấn mặc định chỉ thấy bản active.**
Chunk còn ở trạng thái ``proposed`` là thứ máy vừa trích xuất nhưng người chưa
duyệt tại G2. Nếu nó lọt vào một truy xuất bình thường thì toàn bộ lập luận
chống ảo giác của đề án sụp: mã sinh ra sẽ có trích dẫn đàng hoàng, trỏ tới
một trích đoạn chưa ai đối chiếu (AIS §12 — "ảo giác có đóng dấu").
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from eaa.kb import (
    ACTIVE,
    DEPRECATED,
    PROPOSED,
    Chunk,
    Constraints,
    DatasheetStore,
    HardwareProfile,
    KbError,
    KnowledgeBase,
    PromptLibrary,
    content_hash,
)

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


@pytest.fixture()
def kho() -> DatasheetStore:
    return DatasheetStore(DU_AN / "datasheets")


def _viet_chunk(thu_muc: Path, ten: str, frontmatter: str, than: str = "Nội dung.") -> Path:
    path = thu_muc / ten
    path.write_text(
        "---\n" + textwrap.dedent(frontmatter).strip() + "\n---\n\n" + than + "\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------
# Hard Constraints Spec
# --------------------------------------------------------------------------


def test_nap_rang_buoc_du_an_mau() -> None:
    rb = Constraints.load(DU_AN / "constraints.yaml")
    assert rb.platform == "avr"
    assert rb.version == 1
    assert rb.limits["flash_pct_max"] == 50
    assert rb.limits["sram_pct_max"] == 40
    assert "delay()" in rb.forbidden
    assert rb.style["arithmetic"] == "integer"
    assert rb.content_version.startswith("sha256:")


def test_platform_params_chuyen_tiep_ma_khong_dien_giai() -> None:
    """Engine không được biết khóa nào nghĩa là gì — chỉ chuyển tiếp (FR-PLT-01)."""
    params = Constraints.load(DU_AN / "constraints.yaml").platform_params()
    assert params["platform"] == "avr"
    assert params["clock_hz"] == 16000000
    assert params["flash_pct_max"] == 50          # khóa lồng trong limits cũng có mặt
    assert "forbidden" not in params              # danh sách không phải tham số vô hướng
    assert "limits" not in params


def test_rang_buoc_thieu_platform_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "constraints.yaml").write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(KbError, match="platform"):
        Constraints.load(tmp_path / "constraints.yaml")


def test_content_hash_doi_khi_chu_thich_doi(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("platform: avr\n", encoding="utf-8")
    truoc = content_hash(path)
    path.write_text("platform: avr\n# chỉ thêm một chú thích\n", encoding="utf-8")
    assert content_hash(path) != truoc


# --------------------------------------------------------------------------
# Datasheet Store — vòng đời và truy xuất
# --------------------------------------------------------------------------


def test_nap_du_chunk_cua_du_an_mau(kho: DatasheetStore) -> None:
    assert len(kho.all()) == 6
    assert {c.id for c in kho.active()} == {"ds-012", "ds-021", "ds-022", "ds-031", "ds-041"}


def test_chunk_chua_duyet_G2_khong_lot_vao_truy_xuat(kho: DatasheetStore) -> None:
    """ds-032 đang ở trạng thái proposed."""
    de_xuat = next(c for c in kho.all() if c.id == "ds-032")
    assert de_xuat.status == PROPOSED
    assert not de_xuat.is_active

    assert de_xuat not in kho.active()
    assert kho.by_register("ACCEL_XOUT_H") == []
    assert kho.by_peripheral("imu") == [c for c in kho.active() if c.peripheral == "imu"]

    with pytest.raises(KbError, match="đã duyệt G2"):
        kho.get("ds-032")

    # Vẫn tra được khi cố ý yêu cầu — để đối chiếu lịch sử, không để đưa vào prompt.
    assert kho.get("ds-032", include_inactive=True).id == "ds-032"
    assert len(kho.by_register("ACCEL_XOUT_H", include_inactive=True)) == 1


def test_khop_ten_thanh_ghi_la_khop_chinh_xac(kho: DatasheetStore) -> None:
    """ADR-07: tên thanh ghi là định danh mạnh; khớp gần đúng đẻ ra ảo giác có nguồn."""
    assert [c.id for c in kho.by_register("TWBR")] == ["ds-021"]
    assert [c.id for c in kho.by_register("twbr")] == ["ds-021"]   # không phân biệt hoa thường
    assert kho.by_register("TWB") == []                            # không khớp một phần
    assert kho.by_register("TWBR2") == []
    assert kho.by_register("TCCR1B") != kho.by_register("TCCR0B")


def test_truy_xuat_theo_nhieu_thanh_ghi_khong_lap_va_giu_thu_tu(kho: DatasheetStore) -> None:
    ket_qua = kho.by_registers(["TWBR", "TWCR", "TWSR", "TCCR1A"])
    ids = [c.id for c in ket_qua]
    assert ids == ["ds-021", "ds-022", "ds-012"]
    assert len(ids) == len(set(ids)), "cùng một chunk không được xuất hiện hai lần"


def test_trich_dan_bat_buoc_dung_dinh_dang(kho: DatasheetStore) -> None:
    """FR-RAG-02: mã cấu hình thanh ghi phải mang '// ref: <chunk id>'."""
    chunk = kho.get("ds-012")
    assert chunk.citation.startswith("// ref: ds-012")
    assert "tr.140" in chunk.citation


def test_tap_thanh_ghi_co_tai_lieu_chi_gom_ban_active(kho: DatasheetStore) -> None:
    regs = kho.registers()
    assert "TWBR" in regs and "TCCR1A" in regs
    assert "ACCEL_XOUT_H" not in regs, "thanh ghi chỉ có trong chunk proposed thì coi như CHƯA có tài liệu"


# --------------------------------------------------------------------------
# Datasheet Store — lược đồ sai phải bị chặn ngay lúc nạp
# --------------------------------------------------------------------------


def test_thieu_frontmatter_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("Chỉ có nội dung, không có metadata.\n", encoding="utf-8")
    with pytest.raises(KbError, match="frontmatter"):
        DatasheetStore(tmp_path).all()


@pytest.mark.parametrize("thieu", ["id", "device", "peripheral", "status"])
def test_thieu_truong_bat_buoc_bi_tu_choi(tmp_path: Path, thieu: str) -> None:
    truong = {
        "id": "ds-001",
        "device": "chip",
        "peripheral": "bus",
        "status": ACTIVE,
    }
    del truong[thieu]
    _viet_chunk(tmp_path, "a.md", "\n".join(f"{k}: {v}" for k, v in truong.items()))
    with pytest.raises(KbError, match=thieu):
        DatasheetStore(tmp_path).all()


def test_status_la_bi_tu_choi(tmp_path: Path) -> None:
    _viet_chunk(tmp_path, "a.md", "id: ds-1\ndevice: c\nperipheral: b\nstatus: chac_la_ok")
    with pytest.raises(KbError, match="status"):
        DatasheetStore(tmp_path).all()


def test_chunk_rong_bi_tu_choi(tmp_path: Path) -> None:
    _viet_chunk(tmp_path, "a.md", f"id: ds-1\ndevice: c\nperipheral: b\nstatus: {ACTIVE}", than="")
    with pytest.raises(KbError, match="rỗng"):
        DatasheetStore(tmp_path).all()


def test_trung_id_chunk_bi_tu_choi(tmp_path: Path) -> None:
    for ten in ("a.md", "b.md"):
        _viet_chunk(tmp_path, ten, f"id: ds-1\ndevice: c\nperipheral: b\nstatus: {ACTIVE}")
    with pytest.raises(KbError, match="Trùng id"):
        DatasheetStore(tmp_path).all()


def test_kho_khong_ton_tai_thi_rong_chu_khong_no(tmp_path: Path) -> None:
    """Dự án mới chưa nạp tài liệu nào là chuyện bình thường."""
    assert DatasheetStore(tmp_path / "chua-co").all() == []


# --------------------------------------------------------------------------
# Chuỗi supersede — nền của tập lỗi thời (AIS §8.3)
# --------------------------------------------------------------------------


def test_supersede_hop_le(tmp_path: Path) -> None:
    _viet_chunk(
        tmp_path,
        "cu.md",
        f"""
        id: ds-100
        device: c
        peripheral: b
        registers: [REG_A]
        status: {DEPRECATED}
        superseded_by: ds-101
        """,
    )
    _viet_chunk(
        tmp_path,
        "moi.md",
        f"""
        id: ds-101
        device: c
        peripheral: b
        registers: [REG_A]
        status: {ACTIVE}
        supersedes: ds-100
        """,
    )
    kho = DatasheetStore(tmp_path)
    assert [c.id for c in kho.active()] == ["ds-101"]
    assert [c.id for c in kho.by_register("REG_A")] == ["ds-101"]
    # Bản cũ không bị xóa — lịch sử truy vết không đứt.
    assert kho.get("ds-100", include_inactive=True).status == DEPRECATED


def test_supersede_tro_toi_chunk_khong_ton_tai_bi_bat(tmp_path: Path) -> None:
    _viet_chunk(
        tmp_path,
        "moi.md",
        f"id: ds-101\ndevice: c\nperipheral: b\nstatus: {ACTIVE}\nsupersedes: ds-khong-co",
    )
    with pytest.raises(KbError, match="không tồn tại"):
        DatasheetStore(tmp_path).all()


def test_ban_bi_thay_ma_van_active_bi_bat(tmp_path: Path) -> None:
    """Hai bản cùng active cho một thanh ghi là mâu thuẫn im lặng — phải kêu."""
    _viet_chunk(tmp_path, "cu.md", f"id: ds-100\ndevice: c\nperipheral: b\nstatus: {ACTIVE}")
    _viet_chunk(
        tmp_path,
        "moi.md",
        f"id: ds-101\ndevice: c\nperipheral: b\nstatus: {ACTIVE}\nsupersedes: ds-100",
    )
    with pytest.raises(KbError, match="deprecated"):
        DatasheetStore(tmp_path).all()


# --------------------------------------------------------------------------
# Hardware Profile
# --------------------------------------------------------------------------


def test_nap_ho_so_phan_cung_du_an_mau() -> None:
    hs = HardwareProfile.load(DU_AN / "hardware_profile.yaml")
    assert len(hs.peripherals) == 4
    assert len(hs.components) == 3
    assert len(hs.pin_map) == 9
    assert hs.power["separated"] is True


def test_thanh_ghi_cau_hinh_mot_ngoai_vi() -> None:
    """Đây là cạnh configured_by mà Knowledge Graph sẽ dựng lên (FR-KG-01)."""
    hs = HardwareProfile.load(DU_AN / "hardware_profile.yaml")
    assert hs.registers_of("twi") == ("TWBR", "TWCR", "TWSR", "TWDR")
    assert "TCCR1A" in hs.registers_of("timer1")
    assert hs.registers_of("khong-co") == ()
    assert hs.peripheral("TIMER1") is not None, "tra cứu không phân biệt hoa thường"


def test_trung_id_ngoai_vi_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "hardware_profile.yaml").write_text(
        "peripherals:\n  - id: t1\n  - id: t1\n", encoding="utf-8"
    )
    with pytest.raises(KbError, match="trùng id ngoại vi"):
        HardwareProfile.load(tmp_path / "hardware_profile.yaml")


# --------------------------------------------------------------------------
# Prompt Library — xếp lớp pack ← dự án
# --------------------------------------------------------------------------


def test_mau_cua_du_an_ghi_de_mau_cua_pack(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    duan = tmp_path / "duan"
    pack.mkdir()
    duan.mkdir()
    (pack / "driver.md").write_text("---\nid: driver\n---\nBản của pack\n", encoding="utf-8")
    (pack / "chung.md").write_text("---\nid: chung\n---\nChỉ pack có\n", encoding="utf-8")
    (duan / "driver.md").write_text("---\nid: driver\n---\nBản của dự án\n", encoding="utf-8")

    thu_vien = PromptLibrary(pack, duan)
    assert thu_vien.get("driver").body == "Bản của dự án"
    assert thu_vien.get("driver").origin == "project"
    assert thu_vien.get("chung").origin == "pack"
    assert len(thu_vien.all()) == 2


def test_mau_khong_co_frontmatter_lay_ten_tep_lam_id(tmp_path: Path) -> None:
    tmp_path.joinpath("sinh_ma.md").write_text("Nội dung trần.\n", encoding="utf-8")
    assert PromptLibrary(tmp_path, None).get("sinh_ma").body == "Nội dung trần."


def test_mau_khong_ton_tai_bao_loi_kem_danh_sach_dang_co(tmp_path: Path) -> None:
    tmp_path.joinpath("a.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(KbError, match="đang có"):
        PromptLibrary(tmp_path, None).get("khong-co")


# --------------------------------------------------------------------------
# Gộp
# --------------------------------------------------------------------------


def test_nap_toan_bo_knowledge_base_cua_du_an_mau() -> None:
    kb = KnowledgeBase.load(DU_AN, pack_prompts_dir=REPO / "packs" / "avr" / "prompts")
    assert kb.platform == "avr"
    assert kb.constraints.limits["control_loop_ms"] == 10
    assert len(kb.datasheets.active()) == 5
    assert kb.hardware.registers_of("timer1")


def test_nap_knowledge_base_thu_muc_khong_ton_tai(tmp_path: Path) -> None:
    with pytest.raises(KbError, match="Không có thư mục dự án"):
        KnowledgeBase.load(tmp_path / "khong-co")
