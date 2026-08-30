"""TC-62 — bậc hai hiểu ngữ nghĩa, đặt SAU bậc khớp từ khóa.

Hai chỗ trong sản phẩm nhận câu tiếng Việt tự do mà xử lý bằng khớp chuỗi con:
chọn kịch bản chẩn đoán từ triệu chứng (AIS §7.3) và truy hồi phẩm xuất
(FR-DOC-03). Tài liệu gọi cả hai là "mô tả tự nhiên", nên người đọc dễ hiểu
thành hiểu ngữ nghĩa — trong khi *"bánh xe đứng im"* trượt sạch dù nghĩa y hệt
*"động cơ không quay"*.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-62a | Bậc 1 khớp từ khóa vẫn chạy trước và vẫn tất định | |
| TC-62b | Bậc 1 trúng thì KHÔNG gọi mô hình | rẻ, nhanh, tái lập được |
| TC-62c | Bậc 1 trượt thì bậc 2 hỏi mô hình | |
| TC-62d | Kết quả bậc 2 được đánh dấu là PHỎNG ĐOÁN | không trộn với bậc 1 |
| TC-62e | Mô hình bịa mã kịch bản thì bị loại | |
| TC-62f | Không có mô hình thì trả rỗng, không nổ | |

TC-62b là điều dễ mất nhất khi thêm một bậc thông minh: gọi mô hình cho mọi
câu hỏi thì mất tính tất định mà Chương 3 dựa vào, và tốn tiền cho những ca
mà một phép so chuỗi đã trả lời đúng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.confidence import GIA_DINH, SUY_RA
from eaa.diagnostics import (
    MO_HINH,
    TU_KHOA,
    DiagnosticError,
    Scenario,
    ScenarioLibrary,
)
from eaa.registry import ArtifactRegistry

REPO = Path(__file__).resolve().parent.parent
DU_AN = REPO / "projects" / "robot_balance"


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: dict) -> None:
        self.tra_ve = tra_ve
        self.calls = 0

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.calls += 1
        return "```json\n" + json.dumps(self.tra_ve, ensure_ascii=False) + "\n```"


@pytest.fixture(scope="module")
def thu_vien() -> ScenarioLibrary:
    return ScenarioLibrary.load(DU_AN / "diagnostics.yaml")


# --------------------------------------------------------------------------
# TC-62a, TC-62b — bậc 1 chạy trước và một mình
# --------------------------------------------------------------------------


def test_bac1_khop_tu_khoa_van_chay_truoc(thu_vien: ScenarioLibrary) -> None:
    llm = _LlmGia({"chon": []})
    khop = thu_vien.select_smart("động cơ không quay", llm)

    assert [m.scenario.id for m in khop] == ["DS-03"]
    assert khop[0].tier == TU_KHOA


def test_bac1_trung_thi_KHONG_goi_mo_hinh(thu_vien: ScenarioLibrary) -> None:
    """Gọi mô hình cho mọi câu là mất tính tất định và tốn tiền vô ích."""
    llm = _LlmGia({"chon": [{"id": "DS-01", "vi_sao": "bịa"}]})
    thu_vien.select_smart("động cơ không quay", llm)

    assert llm.calls == 0


def test_bac1_neu_ro_tu_nao_da_khop(thu_vien: ScenarioLibrary) -> None:
    """Kiểm lại được: nhìn là biết vì sao kịch bản này được chọn."""
    khop = thu_vien.select_smart("robot bị trôi góc khi đứng yên")
    assert khop
    assert "trôi góc" in khop[0].evidence


def test_bac1_tat_dinh(thu_vien: ScenarioLibrary) -> None:
    a = [m.scenario.id for m in thu_vien.select_smart("động cơ không quay")]
    b = [m.scenario.id for m in thu_vien.select_smart("động cơ không quay")]
    assert a == b


# --------------------------------------------------------------------------
# TC-62c, TC-62d — bậc 2 và nhãn phỏng đoán
# --------------------------------------------------------------------------


def test_cau_noi_khac_chu_thi_bac1_truot(thu_vien: ScenarioLibrary) -> None:
    """Đây là lỗ hổng mà bậc 2 sinh ra để lấp."""
    assert thu_vien.select("bánh xe đứng im dù đã cấp nguồn") == []


def test_bac2_hoi_mo_hinh_khi_bac1_truot(thu_vien: ScenarioLibrary) -> None:
    llm = _LlmGia({"chon": [{"id": "DS-03", "vi_sao": "bánh không quay tức là động cơ"}]})
    khop = thu_vien.select_smart("bánh xe đứng im dù đã cấp nguồn", llm)

    assert llm.calls == 1
    assert [m.scenario.id for m in khop] == ["DS-03"]
    assert khop[0].tier == MO_HINH


def test_ket_qua_bac2_duoc_danh_dau_la_phong_doan(thu_vien: ScenarioLibrary) -> None:
    llm = _LlmGia({"chon": [{"id": "DS-03", "vi_sao": "tương đương"}]})
    m = thu_vien.select_smart("bánh xe đứng im", llm)[0]
    van_ban = m.render()

    assert "[mô hình đoán]" in van_ban
    assert "PHỎNG ĐOÁN" in van_ban
    assert "Đọc lại mô tả kịch bản trước khi chạy" in van_ban


def test_hai_bac_co_muc_tin_cay_khac_nhau(thu_vien: ScenarioLibrary) -> None:
    """Trộn chúng vào một danh sách là làm mất điều người đọc cần để quyết."""
    bac1 = thu_vien.select_smart("động cơ không quay")[0]
    llm = _LlmGia({"chon": [{"id": "DS-03", "vi_sao": "x"}]})
    bac2 = thu_vien.select_smart("bánh xe đứng im", llm)[0]

    assert bac1.confidence_level == SUY_RA
    assert bac2.confidence_level == GIA_DINH


# --------------------------------------------------------------------------
# TC-62e, TC-62f — bịa và thiếu mô hình
# --------------------------------------------------------------------------


def test_mo_hinh_bia_ma_kich_ban_thi_bi_loai(thu_vien: ScenarioLibrary) -> None:
    """Bịa ở đây đặc biệt tệ: người sẽ đi nạp một firmware chẩn đoán không có."""
    llm = _LlmGia({"chon": [{"id": "DS-99", "vi_sao": "bịa"}, {"id": "DS-03", "vi_sao": "thật"}]})
    khop = thu_vien.select_smart("bánh xe đứng im", llm)

    assert [m.scenario.id for m in khop] == ["DS-03"]


def test_mo_hinh_khong_chon_gi_la_ket_cuc_hop_le(thu_vien: ScenarioLibrary) -> None:
    """Nó nói rằng dự án còn thiếu một kịch bản cho hiện tượng này."""
    llm = _LlmGia({"chon": []})
    assert thu_vien.select_smart("vỏ máy đổi màu", llm) == []


def test_khong_co_mo_hinh_thi_tra_rong_chu_khong_no(thu_vien: ScenarioLibrary) -> None:
    assert thu_vien.select_smart("bánh xe đứng im", None) == []


def test_thu_vien_rong_thi_khong_goi_mo_hinh() -> None:
    llm = _LlmGia({"chon": []})
    assert ScenarioLibrary([]).select_smart("bất cứ gì", llm) == []
    assert llm.calls == 0


# --------------------------------------------------------------------------
# Cùng cơ chế ở kho phẩm xuất
# --------------------------------------------------------------------------


@pytest.fixture()
def kho(tmp_path: Path) -> ArtifactRegistry:
    r = ArtifactRegistry(tmp_path / "deliverables")
    r.publish(
        family="bao_cao_kpi", kind="csv", title="Báo cáo chỉ số dự án",
        content="a,b\n1,2\n", description="Số liệu các lượt chạy",
    )
    return r


def test_kho_bac1_khop_tu_khoa(kho: ArtifactRegistry) -> None:
    ket, bac = kho.find_smart("chỉ số")
    assert [a.family for a in ket] == ["bao_cao_kpi"]
    assert bac == "tu-khoa"


def test_kho_bac1_trung_thi_khong_goi_mo_hinh(kho: ArtifactRegistry) -> None:
    llm = _LlmGia({"chon": []})
    kho.find_smart("chỉ số", llm=llm)
    assert llm.calls == 0


def test_kho_bac1_khop_bat_ky_TU_nao_nen_kha_rong(kho: ArtifactRegistry) -> None:
    """Ghi lại hành vi thật của bậc 1: khớp BẤT KỲ từ nào dài hơn 2 ký tự.

    Rộng như vậy có cái giá của nó — một câu dài dễ trúng nhầm — nhưng nó cũng
    là lý do bậc 2 hiếm khi phải chạy. Viết ra đây để lần sau ai đó siết bậc 1
    lại thì biết mình đang đánh đổi cái gì.
    """
    ket, bac = kho.find_smart("cái bảng số liệu hôm nọ")
    assert bac == "tu-khoa" and ket, "'liệu' trùng mô tả nên bậc 1 đã trúng"


def test_kho_bac2_khi_khong_tu_nao_trung(kho: ArtifactRegistry) -> None:
    llm = _LlmGia({"chon": ["bao_cao_kpi@v1"]})
    ket, bac = kho.find_smart("thứ tôi gửi thầy tuần trước", llm=llm)

    assert llm.calls == 1
    assert bac == "mo-hinh"
    assert [a.id for a in ket] == ["bao_cao_kpi@v1"]


def test_kho_mo_hinh_bia_ma_thi_bi_loai(kho: ArtifactRegistry) -> None:
    llm = _LlmGia({"chon": ["khong_he_co@v9"]})
    ket, _ = kho.find_smart("cái gì đó", llm=llm)
    assert ket == []


def test_kho_rong_thi_khong_goi_mo_hinh(tmp_path: Path) -> None:
    llm = _LlmGia({"chon": []})
    ket, bac = ArtifactRegistry(tmp_path / "d").find_smart("gì đó", llm=llm)
    assert ket == [] and bac == "tu-khoa" and llm.calls == 0


def test_mo_ta_rong_thi_khong_goi_mo_hinh(kho: ArtifactRegistry) -> None:
    llm = _LlmGia({"chon": []})
    kho.find_smart("", llm=llm)
    assert llm.calls == 0
