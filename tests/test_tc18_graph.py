"""TC-18 và TC-05 — Knowledge Graph: kiểm xung đột và Graph-RAG.

* **TC-18** (AIS §11): "Hai module khai báo cùng uses Timer1 → bị chặn từ bước
  khai báo (P2), báo cáo nêu hai module và tài nguyên."
* **TC-05** (STP-04): "Sinh driver I2C → prompt chứa chunk TWBR/TWCR; không
  chứa chunk Timer1 không liên quan." Ở tầng đồ thị, đó là câu hỏi *chunk nào
  được CHỌN*; phần lắp vào prompt do composer làm và có test riêng.

Hai điều đáng canh nhất ở module này:

1.  **Mặc định độc chiếm.** Quên khai báo ``shareable`` phải dẫn tới cảnh báo
    thừa, không phải xung đột lọt lưới.
2.  **Chọn chunk tất định.** Cùng đầu vào phải cho cùng thứ tự chunk, nếu
    không thực nghiệm A/B của Chương 3 không tái lập được.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from eaa.graph import Conflict, GraphError, KnowledgeGraph
from eaa.kb import DatasheetStore, HardwareProfile

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


@dataclass
class Mod:
    """Đứng thay BacklogItem — kiểm xung đột phải chạy được với module CHƯA
    vào backlog (quy trình P2 kiểm ngay lúc khai báo)."""

    id: str
    uses: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@pytest.fixture()
def hardware() -> HardwareProfile:
    return HardwareProfile.load(DU_AN / "hardware_profile.yaml")


@pytest.fixture()
def datasheets() -> DatasheetStore:
    return DatasheetStore(DU_AN / "datasheets")


@pytest.fixture()
def kg(hardware: HardwareProfile, datasheets: DatasheetStore) -> KnowledgeGraph:
    return KnowledgeGraph.build(hardware, datasheets)


# --------------------------------------------------------------------------
# Dựng đồ thị tự động (FR-KG-01)
# --------------------------------------------------------------------------


def test_do_thi_dung_tu_dong_tu_ho_so_phan_cung(kg: KnowledgeGraph) -> None:
    assert kg.nodes_of_kind("mcu") == ["atmega328p"]
    assert set(kg.nodes_of_kind("peripheral")) == {"timer0", "timer1", "twi", "usart0"}
    assert set(kg.nodes_of_kind("component")) == {
        "imu",
        "motor_driver_left",
        "motor_driver_right",
    }
    assert "TCCR1A" in kg.nodes_of_kind("register")
    assert "PB1" in kg.nodes_of_kind("pin")


def test_chi_chunk_da_duyet_G2_co_mat_trong_do_thi(kg: KnowledgeGraph) -> None:
    """Chunk proposed không vào đồ thị → Graph-RAG không thể chọn phải nó."""
    chunks = set(kg.nodes_of_kind("chunk"))
    assert {"ds-012", "ds-021", "ds-022", "ds-031", "ds-041"} <= chunks
    assert "ds-032" not in chunks

    # ds-023 và ds-051 là chunk NHIỄU của bộ chuẩn TC-20. Chúng có mặt ở đây
    # đúng như mong muốn: một chunk nhiễu bị lọc ngay ở tầng đồ thị thì nó
    # không thử được bộ chọn. Việc loại chúng khỏi kết quả là việc của xếp
    # hạng, không phải của phép nạp.
    assert {"ds-023", "ds-051"} <= chunks


def test_thanh_ghi_noi_toi_chunk_tai_lieu_hoa_no(kg: KnowledgeGraph) -> None:
    assert "ds-021" in kg._edges_from("TWBR", "documented_in")
    assert "ds-012" in kg._edges_from("TCCR1A", "documented_in")


def test_linh_kien_noi_toi_chunk_theo_ma_linh_kien(kg: KnowledgeGraph) -> None:
    """Chunk khai báo device khớp part của linh kiện thì nối thẳng."""
    assert "ds-031" in kg._edges_from("imu", "documented_in")


# --------------------------------------------------------------------------
# TC-18 — kiểm xung đột tài nguyên
# --------------------------------------------------------------------------


def test_tc18_hai_module_cung_chiem_mot_bo_dem_bi_chan(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_stepper", uses=["timer1"])
    kg.add_module("kernel_tick", uses=["timer1"])

    xung_dot = kg.conflicts()
    assert len(xung_dot) == 1
    c = xung_dot[0]
    assert c.kind == "resource_shared"
    assert c.resource == "timer1"
    assert c.modules == ("drv_stepper", "kernel_tick")
    # Báo cáo phải nêu ĐÍCH DANH hai module và tài nguyên (yêu cầu của TC-18).
    assert "drv_stepper" in c.message and "kernel_tick" in c.message
    assert "timer1" in c.message
    assert c.evidence


def test_tc18_chan_ngay_luc_khai_bao_truoc_khi_vao_backlog(kg: KnowledgeGraph) -> None:
    """Quy trình P2: kiểm NGAY LÚC KHAI BÁO, không đợi tới lúc sinh mã."""
    kg.add_module("kernel_tick", uses=["timer1"])

    phat_hien = kg.check_module("drv_stepper", uses=["timer1"])
    assert [c.resource for c in phat_hien] == ["timer1"]

    # check_module không được để lại dấu vết: module bị từ chối thì đồ thị
    # phải y như trước khi kiểm.
    assert "drv_stepper" not in kg.nodes_of_kind("module")
    assert kg.modules_using("timer1") == ["kernel_tick"]


def test_giai_phap_cua_TC18_la_doi_sang_bo_dem_khac(kg: KnowledgeGraph) -> None:
    """Đúng tình huống Hình 2 của AIS: kernel_tick chuyển sang Timer0."""
    kg.add_module("drv_stepper", uses=["timer1"])
    assert kg.check_module("kernel_tick", uses=["timer0"]) == []


def test_tai_nguyen_khai_bao_dung_chung_thi_khong_bao_xung_dot(kg: KnowledgeGraph) -> None:
    """Bus nhiều thiết bị khai báo shareable: true — nhiều module cùng dùng được."""
    kg.add_module("drv_imu", uses=["twi"])
    kg.add_module("drv_eeprom", uses=["twi"])
    assert kg.conflicts() == []


def test_mac_dinh_la_doc_chiem_khong_phai_dung_chung(hardware: HardwareProfile) -> None:
    """Quên khai báo shareable → cảnh báo thừa, KHÔNG phải xung đột lọt lưới."""
    kg = KnowledgeGraph.build(hardware)
    assert kg._is_shareable("timer1") is False
    assert kg._is_shareable("twi") is True

    kg.add_module("a", uses=["usart0"])
    kg.add_module("b", uses=["usart0"])
    assert [c.resource for c in kg.conflicts()] == ["usart0"]


def test_khai_bao_tai_nguyen_khong_ton_tai_bi_bat(kg: KnowledgeGraph) -> None:
    """Sai chính tả trong 'uses' không được im lặng bỏ qua."""
    phat_hien = kg.check_module("drv_x", uses=["timer9"])
    assert [c.kind for c in phat_hien] == ["unknown_resource"]
    assert "timer9" in phat_hien[0].message


def test_hai_module_cung_dieu_khien_mot_chan_qua_hai_linh_kien(tmp_path) -> None:
    """Xung đột chỉ hiện sau một bước nữa trong đồ thị — đọc từng tệp mã không thấy.

    Dựng hồ sơ RIÊNG thay vì mượn hồ sơ dự án mẫu.
    ------------------------------------------------

    Bản trước dựa vào việc hai driver của `robot_balance` tình cờ dùng chung
    chân `enable: PB0`. Ngày 01/09/2026 đo trên bo thật cho thấy bo KHÔNG có nét
    ENABLE nào về vi điều khiển, nên trường ấy bị bỏ — và bài kiểm mất luôn thứ
    nó đang canh, dù engine không đổi một dòng.

    Một bài canh engine mà phụ thuộc vào dữ liệu dự án thì nó đo hai thứ cùng
    lúc và không nói được thứ nào vừa đổi. Dựng dữ liệu tối thiểu ngay tại đây
    thì nó chỉ còn đo đúng cái nó nói nó đo.
    """
    (tmp_path / "hardware_profile.yaml").write_text(
        "version: 1\nproject: thu\n"
        "mcu: {part: chip_bia, clock_hz: 16000000}\n"
        "components:\n"
        "  - id: linh_kien_a\n    part: bia\n    pins: {step: PX1, enable: PX0}\n"
        "  - id: linh_kien_b\n    part: bia\n    pins: {step: PX2, enable: PX0}\n",
        encoding="utf-8",
    )
    (tmp_path / "datasheets").mkdir()
    kg = KnowledgeGraph.build(
        HardwareProfile.load(tmp_path / "hardware_profile.yaml"),
        DatasheetStore(tmp_path / "datasheets"),
    )
    kg.add_module("mod_a", uses=["linh_kien_a"])
    kg.add_module("mod_b", uses=["linh_kien_b"])

    theo_chan = {c.resource: c for c in kg.conflicts() if c.kind == "pin_shared"}
    assert "PX0" in theo_chan, "hai linh kiện dùng chung chân PX0"
    assert theo_chan["PX0"].modules == ("mod_a", "mod_b")
    assert "PX1" not in theo_chan, "chân riêng của từng linh kiện thì không xung đột"


def test_mot_module_dung_hai_linh_kien_chung_chan_thi_khong_xung_dot(
    kg: KnowledgeGraph,
) -> None:
    """Một module tự điều phối hai driver là thiết kế hợp lệ, không phải tranh chấp."""
    kg.add_module("drv_motors", uses=["motor_driver_left", "motor_driver_right"])
    assert [c for c in kg.conflicts() if c.kind == "pin_shared"] == []


# --------------------------------------------------------------------------
# TC-05 — Graph-RAG chọn chunk theo quan hệ
# --------------------------------------------------------------------------


def test_tc05_module_bus_lay_dung_chunk_bus_khong_lay_chunk_bo_dem(
    kg: KnowledgeGraph,
) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"])
    chon = kg.chunks_for("drv_i2c_imu")

    assert "ds-021" in chon, "phải có chunk tốc độ bit bus (TWBR/TWCR)"
    assert "ds-022" in chon, "phải có chunk mã trạng thái bus"
    assert "ds-012" not in chon, "KHÔNG được lấy chunk bộ đếm không liên quan"
    assert "ds-041" not in chon, "KHÔNG được lấy chunk truyền nối tiếp không liên quan"
    assert len(chon) <= 3, "top-k = 3 theo AIS §4.2"


def test_tc05_module_bo_dem_lay_dung_chunk_bo_dem(kg: KnowledgeGraph) -> None:
    kg.add_module("kernel_tick", uses=["timer1"])
    chon = kg.chunks_for("kernel_tick")
    assert chon == ["ds-012"]
    assert "ds-021" not in chon


def test_chon_chunk_la_tat_dinh(kg: KnowledgeGraph) -> None:
    """Cùng đầu vào phải cho cùng thứ tự — điều kiện để A/B tái lập được."""
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"])
    lan_dau = kg.chunks_for("drv_i2c_imu")
    for _ in range(5):
        assert kg.chunks_for("drv_i2c_imu") == lan_dau


def test_chunk_phu_nhieu_thanh_ghi_hon_thi_xep_truoc(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi"])
    chon = kg.chunks_for("drv_i2c_imu", top_k=2)
    # ds-022 phủ TWSR+TWDR+TWCR (3), ds-021 phủ TWBR+TWSR+TWCR (3) — hòa điểm
    # nên xếp theo mã chunk, tất định.
    assert chon == ["ds-021", "ds-022"]


def test_select_chunks_tra_ve_chunk_day_du_de_ghep_prompt(
    kg: KnowledgeGraph, datasheets: DatasheetStore
) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"])
    chunks = kg.select_chunks("drv_i2c_imu", datasheets)
    assert all(c.is_active for c in chunks)
    assert all(c.body for c in chunks)
    assert any("TWBR" in c.registers for c in chunks)


def test_module_khong_dung_tai_nguyen_nao_thi_khong_co_chunk(kg: KnowledgeGraph) -> None:
    kg.add_module("pid_controller", uses=[])
    assert kg.chunks_for("pid_controller") == []


# --------------------------------------------------------------------------
# Thanh ghi và chân của một module — đầu vào cho RIC (AIS §6.2)
# --------------------------------------------------------------------------


def test_thanh_ghi_cua_module_di_qua_bus_cua_linh_kien(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_i2c_imu", uses=["imu"])
    thanh_ghi = set(kg.registers_for("drv_i2c_imu"))

    # Hai nguồn, và cả hai đều cần.
    #
    # Bus mà linh kiện nằm trên: không cấu hình được bus thì không nói chuyện
    # được với linh kiện.
    assert {"TWBR", "TWCR", "TWSR", "TWDR"} <= thanh_ghi
    # Thanh ghi của CHÍNH linh kiện. Cạnh này thêm vào ở TC-20: thiếu nó, trích
    # đoạn về con cảm biến không có đường nào để được xếp hạng cao, và bị một
    # trích đoạn cùng bus đẩy ra khỏi ba chỗ của prompt.
    assert {"WHO_AM_I", "PWR_MGMT_1"} <= thanh_ghi


def test_chan_cua_module_lay_tu_linh_kien(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_motor_l", uses=["motor_driver_left"])
    # Chân lấy từ hồ sơ dự án, và hồ sơ ấy sửa hai lần trong ngày 01/09/2026:
    # theo sơ đồ nguyên lý (bỏ chân enable, chuyển sang PORTD — SL-125), rồi
    # theo QUAN SÁT trên bo (động cơ 1 là bên PHẢI, không phải trái — SL-127).
    # Bên trái là D7/D6.
    assert kg.pins_for("drv_motor_l") == ["PD6", "PD7"]


# --------------------------------------------------------------------------
# Phân tích ảnh hưởng và checklist G3 (§5.4)
# --------------------------------------------------------------------------


def test_module_nao_dua_tren_mot_chunk(kg: KnowledgeGraph) -> None:
    """Nửa 'đồ thị' của truy vấn ngược cho tập lỗi thời (AIS §8.3)."""
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"])
    kg.add_module("kernel_tick", uses=["timer1"])

    assert kg.modules_documented_by("ds-021") == ["drv_i2c_imu"]
    assert kg.modules_documented_by("ds-012") == ["kernel_tick"]
    assert kg.modules_documented_by("ds-031") == ["drv_i2c_imu"]
    assert kg.modules_documented_by("khong-co-chunk-nay") == []


def test_doi_mot_tai_nguyen_thi_phai_xem_lai_nhung_gi(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi"])
    anh_huong = kg.impact_of("twi")
    assert anh_huong["modules"] == ["drv_i2c_imu"]
    assert "TWBR" in anh_huong["registers"]
    assert {"ds-021", "ds-022"} <= set(anh_huong["chunks"])
    assert "PC4" in anh_huong["pins"]

    with pytest.raises(GraphError):
        kg.impact_of("khong-ton-tai")


def test_checklist_G3_sinh_tu_do_thi(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi"])
    kg.add_module("drv_eeprom", uses=["twi"])
    checklist = kg.review_checklist("drv_i2c_imu")

    noi_dung = "\n".join(checklist)
    assert "twi" in noi_dung
    assert "ds-021" in noi_dung, "phải chỉ đúng chunk cần đối chiếu từng bit"
    assert "drv_eeprom" in noi_dung, "phải nhắc module khác cùng dùng tài nguyên"


def test_checklist_bao_thieu_tai_lieu_thay_vi_im_lang(hardware: HardwareProfile) -> None:
    """Không có kho chunk: mọi thanh ghi đều là mục phải nạp tài liệu qua G2."""
    kg = KnowledgeGraph.build(hardware)
    kg.add_module("kernel_tick", uses=["timer1"])
    assert any("KHÔNG có chunk nào" in dong for dong in kg.review_checklist("kernel_tick"))


# --------------------------------------------------------------------------
# K6 — nén hồ sơ phần cứng thành vài dòng sự kiện
# --------------------------------------------------------------------------


def test_facts_thay_the_ca_ho_so_phan_cung(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"])
    facts = kg.facts_for("drv_i2c_imu")

    noi_dung = "\n".join(facts)
    assert "twi" in noi_dung and "imu" in noi_dung
    assert "TWBR" in noi_dung
    assert "400000" in noi_dung, "tham số của ngoại vi phải đi kèm"
    assert len(facts) <= 8, "K6 là vài dòng ghi chú, không phải một tài liệu"


def test_facts_mang_theo_canh_bao_xung_dot(kg: KnowledgeGraph) -> None:
    kg.add_module("drv_stepper", uses=["timer1"])
    kg.add_module("kernel_tick", uses=["timer1"])
    assert any("XUNG ĐỘT" in d for d in kg.facts_for("kernel_tick"))


# --------------------------------------------------------------------------
# Lưu trữ graph.yaml (ADR-08)
# --------------------------------------------------------------------------


def test_ghi_roi_doc_lai_giu_nguyen_do_thi(kg: KnowledgeGraph, tmp_path: Path) -> None:
    kg.add_module("drv_i2c_imu", uses=["twi", "imu"], depends_on=["hal_bus"])
    path = tmp_path / "graph.yaml"
    kg.save(path)

    lai = KnowledgeGraph.load(path)
    assert len(lai) == len(kg)
    assert lai.resources_of("drv_i2c_imu") == ["imu", "twi"]
    assert lai.chunks_for("drv_i2c_imu") == kg.chunks_for("drv_i2c_imu")
    assert lai.registers_for("drv_i2c_imu") == kg.registers_for("drv_i2c_imu")


def test_graph_yaml_la_van_ban_nguoi_doc_duoc(kg: KnowledgeGraph, tmp_path: Path) -> None:
    """ADR-06: file phẳng theo dõi bằng Git."""
    path = tmp_path / "graph.yaml"
    kg.save(path)
    noi_dung = path.read_text(encoding="utf-8")
    assert "nodes:" in noi_dung and "edges:" in noi_dung
    assert "timer1" in noi_dung


def test_load_graph_khong_ton_tai_bao_loi(tmp_path: Path) -> None:
    with pytest.raises(GraphError, match="Không tìm thấy"):
        KnowledgeGraph.load(tmp_path / "khong-co.yaml")


# --------------------------------------------------------------------------
# Dựng kèm backlog
# --------------------------------------------------------------------------


def test_dung_do_thi_kem_backlog(
    hardware: HardwareProfile, datasheets: DatasheetStore
) -> None:
    kg = KnowledgeGraph.build(
        hardware,
        datasheets,
        modules=[
            Mod("drv_i2c_imu", uses=["twi", "imu"]),
            Mod("pid_controller", depends_on=["drv_i2c_imu"]),
        ],
    )
    assert set(kg.nodes_of_kind("module")) == {"drv_i2c_imu", "pid_controller"}
    assert kg._edges_from("pid_controller", "depends_on") == ["drv_i2c_imu"]
    assert kg.conflicts() == []


def test_ngoai_vi_thieu_id_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "hardware_profile.yaml").write_text(
        "peripherals:\n  - kind: timer\n", encoding="utf-8"
    )
    hs = HardwareProfile.load(tmp_path / "hardware_profile.yaml")
    with pytest.raises(GraphError, match="thiếu 'id'"):
        KnowledgeGraph.build(hs)
