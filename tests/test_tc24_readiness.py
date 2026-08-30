"""TC-24, TC-26 — vòng tự đánh giá đủ thông tin.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-24 | Thiếu chunk bắt buộc | báo ĐÍCH DANH thanh ghi; vòng sinh mã không mở; gợi ý ba bậc tìm kiếm |
| TC-26 | Hai giá trị khác nhau cho cùng thanh ghi | đánh dấu MÂU THUẪN; dừng chờ người; máy không tự chọn |

Hai test case này canh cùng một tính chất từ hai phía: **thiếu thông tin thì
dừng, không đoán.** Đây là ranh giới quan trọng nhất của tầng AI trong đề án,
vì một giá trị thanh ghi đoán ra trông y hệt một giá trị tra được — nó đi qua
compile, đi qua phân tích tĩnh, đi qua kiểm thử đơn vị, và chỉ lộ ra trên
thiết bị thật, nếu lộ ra.

TC-26 đặc biệt: điều được kiểm không phải "máy chọn đúng bản" mà là **máy
không chọn**. Độ mới không phải bằng chứng đúng (AIS §8.2).
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from eaa.graph import KnowledgeGraph
from eaa.kb import KnowledgeBase
from eaa.readiness import (
    MAX_SEARCH_ROUNDS,
    SEARCH_TIERS,
    ItemStatus,
    NotReady,
    Priority,
    ReadinessChecker,
    Ric,
    RicItem,
)

REPO = Path(__file__).resolve().parent.parent
DU_AN_MAU = REPO / "projects" / "robot_balance"


CHUNK_MAU_THUAN = """\
---
id: ds-021x
device: atmega328p
peripheral: twi
registers: [TWBR, TWSR]
topic: Tốc độ bit bus hai dây — bản từ nguồn khác
source: Application note AN-2201, tr.7
status: approved
---

## TWI — tốc độ bit theo tài liệu ứng dụng

| Thanh ghi | Bit | Giá trị | Ý nghĩa |
|---|---|---|---|
| TWBR | 7:0 | 72 | Hệ số chia tốc độ bit cho 100 kHz |
| TWSR | TWPS1:TWPS0 | 0 | Hệ số chia trước = 1 |
"""


@pytest.fixture()
def du_an(tmp_path: Path) -> Path:
    project = tmp_path / "du_an"
    project.mkdir()
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        shutil.copy(DU_AN_MAU / ten, project / ten)
    shutil.copytree(DU_AN_MAU / "datasheets", project / "datasheets")
    return project


def _checker(du_an: Path) -> ReadinessChecker:
    kb = KnowledgeBase.load(du_an)
    graph = KnowledgeGraph.build(kb.hardware, kb.datasheets)
    return ReadinessChecker(kb=kb, graph=graph)


def _go_tai_lieu_twi(du_an: Path) -> None:
    """Dựng cảnh "không còn trích đoạn nào về bus hai dây".

    Phải gỡ CẢ chunk chế độ slave (ds-023, thêm ở TC-20 làm nhiễu). Nó nói về
    TWCR, nên để lại thì thanh ghi ấy vẫn được coi là có tài liệu, và cảnh đang
    dựng không còn là cảnh muốn dựng.
    """
    for ten in (
        "atmega328p__twi_bitrate.md",
        "atmega328p__twi_status.md",
        "atmega328p__twi_slave.md",
    ):
        (du_an / "datasheets" / ten).unlink()


# --------------------------------------------------------------------------
# Đủ thông tin thì vòng sinh mã mở
# --------------------------------------------------------------------------


def test_du_thong_tin_thi_readiness_check_cho_qua(du_an: Path) -> None:
    checker = _checker(du_an)
    ric = checker.check("drv_bus_sensor", uses=["twi"])

    assert ric.ready
    assert {i.key for i in ric.by_status(ItemStatus.PRESENT)} >= {
        "TWBR", "TWCR", "TWSR", "TWDR"
    }
    assert all(i.sources for i in ric.by_status(ItemStatus.PRESENT))


def test_moi_muc_CO_deu_kem_con_tro_nguon(du_an: Path) -> None:
    """AIS §6.2 bước 2: trạng thái CÓ phải kèm con trỏ nguồn, không nói suông."""
    ric = _checker(du_an).build_ric("drv_bus_sensor", uses=["twi"])
    thanh_ghi = next(i for i in ric.items if i.key == "TWBR")
    assert thanh_ghi.status == ItemStatus.PRESENT
    assert "ds-021" in thanh_ghi.sources


def test_module_khong_dung_tai_nguyen_nao_thi_bang_kiem_rong(du_an: Path) -> None:
    ric = _checker(du_an).check("pid_controller")
    assert ric.ready
    assert "không đụng tài nguyên nào" in ric.render()


# --------------------------------------------------------------------------
# TC-24 — thiếu chunk bắt buộc
# --------------------------------------------------------------------------


def test_tc24_xoa_chunk_bat_buoc_thi_vong_sinh_ma_khong_mo(du_an: Path) -> None:
    _go_tai_lieu_twi(du_an)

    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_bus_sensor", uses=["twi"])

    thong_diep = str(loi.value)
    assert "Vòng sinh mã KHÔNG mở" in thong_diep
    assert "cấm đoán" in thong_diep


def test_tc24_bao_DICH_DANH_thanh_ghi_con_thieu(du_an: Path) -> None:
    """Không được báo "thiếu tài liệu" chung chung — phải nêu tên thanh ghi."""
    _go_tai_lieu_twi(du_an)

    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_bus_sensor", uses=["twi"])

    thong_diep = str(loi.value)
    for reg in ("TWBR", "TWCR", "TWSR", "TWDR"):
        assert reg in thong_diep, f"không nêu đích danh {reg}"

    thieu = {i.key for i in loi.value.ric.missing_must}
    assert thieu == {"TWBR", "TWCR", "TWSR", "TWDR"}


def test_tc24_goi_y_du_ba_bac_tim_kiem(du_an: Path) -> None:
    _go_tai_lieu_twi(du_an)

    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_bus_sensor", uses=["twi"])

    thong_diep = str(loi.value)
    for bac in SEARCH_TIERS:
        assert f"Bậc {bac.level}" in thong_diep
        assert bac.name in thong_diep
    # Bậc 2 phải nhắc rằng hỏi người là hỏi ĐÍCH DANH.
    assert "ĐÍCH DANH" in thong_diep
    # Bậc 3 phải nhắc giới hạn nguồn.
    assert "nguồn cho phép" in thong_diep


def test_tc24_qua_hai_vong_tim_thi_chuyen_nguoi(du_an: Path) -> None:
    """Mỗi mục chỉ được tối đa hai vòng tìm trước khi chuyển người (AIS §6.2)."""
    ric = Ric(
        module_id="m",
        items=[
            RicItem(
                key="REG_X",
                kind="thanh ghi",
                status=ItemStatus.MISSING,
                search_rounds=MAX_SEARCH_ROUNDS,
            )
        ],
    )
    assert "chuyển kỹ sư xử lý" in ric.guidance()


def test_muc_Should_thieu_thi_khong_chan(du_an: Path) -> None:
    ric = Ric(
        module_id="m",
        items=[
            RicItem(key="a", kind="tham số", status=ItemStatus.MISSING, priority=Priority.SHOULD)
        ],
    )
    assert ric.ready


def test_chan_khong_co_trong_so_do_noi_day_bi_bao_thieu(du_an: Path) -> None:
    ho_so = du_an / "hardware_profile.yaml"
    ho_so.write_text(
        ho_so.read_text(encoding="utf-8").replace("  PB1:", "  PB1_da_doi_ten:"),
        encoding="utf-8",
    )
    ric = _checker(du_an).build_ric("drv_motor", uses=["motor_driver_left"])
    thieu = {i.key for i in ric.items if i.status == ItemStatus.MISSING}
    assert "PB1" in thieu


def test_tai_nguyen_khong_ton_tai_bi_bao_thieu(du_an: Path) -> None:
    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_x", uses=["timer_khong_co_that"])
    assert "timer_khong_co_that" in str(loi.value)


# --------------------------------------------------------------------------
# TC-26 — mâu thuẫn thì người phân xử
# --------------------------------------------------------------------------


def test_tc26_hai_gia_tri_khac_nhau_cho_cung_thanh_ghi_la_MAU_THUAN(
    du_an: Path,
) -> None:
    (du_an / "datasheets" / "twi_bitrate_an.md").write_text(
        CHUNK_MAU_THUAN, encoding="utf-8"
    )

    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_bus_sensor", uses=["twi"])

    mau_thuan = loi.value.ric.conflicts
    assert [i.key for i in mau_thuan] == ["TWBR"]
    assert set(mau_thuan[0].sources) == {"ds-021", "ds-021x"}
    assert "12" in mau_thuan[0].detail and "72" in mau_thuan[0].detail


def test_tc26_may_KHONG_tu_chon_ban_nao(du_an: Path) -> None:
    """Điều được kiểm không phải "chọn đúng" mà là "không chọn"."""
    (du_an / "datasheets" / "twi_bitrate_an.md").write_text(
        CHUNK_MAU_THUAN, encoding="utf-8"
    )

    with pytest.raises(NotReady) as loi:
        _checker(du_an).check("drv_bus_sensor", uses=["twi"])

    huong_dan = loi.value.ric.guidance()
    assert "Máy KHÔNG tự chọn" in huong_dan
    assert "phân xử tại G2" in huong_dan
    # Không được gợi ý chọn theo độ mới hay theo nguồn nào "có vẻ" chính thống.
    assert "mới hơn" not in huong_dan


def test_tc26_mau_thuan_chan_ke_ca_o_muc_Should() -> None:
    """Kho tri thức tự mâu thuẫn là vấn đề của cả kho, không riêng một mục."""
    muc = RicItem(
        key="REG_X",
        kind="thanh ghi",
        status=ItemStatus.CONFLICT,
        priority=Priority.SHOULD,
        sources=("a", "b"),
    )
    assert muc.blocking
    assert not Ric(module_id="m", items=[muc]).ready


def test_hai_chunk_cung_gia_tri_thi_khong_phai_mau_thuan(du_an: Path) -> None:
    """Hai nguồn xác nhận lẫn nhau là tin tốt, không phải cờ báo động."""
    trung_khop = CHUNK_MAU_THUAN.replace("| 72 |", "| 12 |").replace(
        "ds-021x", "ds-021y"
    ).replace("100 kHz", "400 kHz")
    (du_an / "datasheets" / "twi_bitrate_khop.md").write_text(
        trung_khop, encoding="utf-8"
    )

    ric = _checker(du_an).check("drv_bus_sensor", uses=["twi"])
    assert ric.ready
    twbr = next(i for i in ric.items if i.key == "TWBR")
    assert set(twbr.sources) == {"ds-021", "ds-021y"}


def test_chunk_da_deprecated_khong_gay_mau_thuan(du_an: Path) -> None:
    """Chỉ bản active mới được tính — bản đã bị thay không còn tiếng nói."""
    (du_an / "datasheets" / "twi_bitrate_an.md").write_text(
        CHUNK_MAU_THUAN.replace("status: approved", "status: deprecated"),
        encoding="utf-8",
    )
    assert _checker(du_an).check("drv_bus_sensor", uses=["twi"]).ready


def test_chunk_chua_duyet_G2_khong_gay_mau_thuan(du_an: Path) -> None:
    (du_an / "datasheets" / "twi_bitrate_an.md").write_text(
        CHUNK_MAU_THUAN.replace("status: approved", "status: proposed"),
        encoding="utf-8",
    )
    assert _checker(du_an).check("drv_bus_sensor", uses=["twi"]).ready


# --------------------------------------------------------------------------
# Trình bày
# --------------------------------------------------------------------------


def test_bang_kiem_in_ra_doc_duoc(du_an: Path) -> None:
    ric = _checker(du_an).build_ric("drv_bus_sensor", uses=["twi"])
    van_ban = ric.render()

    assert "Bảng kiểm thông tin cần — drv_bus_sensor" in van_ban
    assert "CÓ" in van_ban and "THIẾU" in van_ban and "MÂU THUẪN" in van_ban
    assert "TWBR" in van_ban


def test_muc_mau_thuan_xep_len_dau_bang(du_an: Path) -> None:
    """Mâu thuẫn là thứ cần người xử lý trước, nên nó phải đập vào mắt trước."""
    ric = Ric(
        module_id="m",
        items=[
            RicItem(key="AAA", kind="thanh ghi", status=ItemStatus.PRESENT, sources=("x",)),
            RicItem(key="ZZZ", kind="thanh ghi", status=ItemStatus.CONFLICT, sources=("a", "b")),
        ],
    )
    dong = ric.render().splitlines()
    vi_tri_mau_thuan = next(i for i, d in enumerate(dong) if "ZZZ" in d)
    vi_tri_co = next(i for i, d in enumerate(dong) if "AAA" in d)
    assert vi_tri_mau_thuan < vi_tri_co
