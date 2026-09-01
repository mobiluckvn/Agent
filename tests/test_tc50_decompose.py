"""TC-50 — Agent đề xuất phân rã module (N-040..N-043).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-50a | Bốn thứ đề xuất cùng lúc | module, tài nguyên, phụ thuộc, chu kỳ — vì chúng ràng buộc nhau |
| TC-50b | Thứ tự làm suy từ phụ thuộc | sắp topo; vòng phụ thuộc bị bắt ngay |
| TC-50c | Ước lượng tải CPU chặn phân rã bất khả thi | vượt trần thì không nhận tự động |
| TC-50d | Không bịa tài nguyên | module chiếm ngoại vi không có trong hồ sơ → cảnh báo |
| TC-50e | Agent không tự thêm vào backlog | đề xuất là *proposed fact*; người nhận mới vào |

Cảnh báo trong nhóm này được chọn rất dè: bản đầu của bộ kiểm chu kỳ báo động
mọi module tầng logic chạy chậm hơn ``control_loop_ms``, và nó báo sai ngay lần
chạy thật đầu tiên — một việc gửi telemetry mỗi 100 ms là hoàn toàn đúng. Một
cơ chế báo động sai thì người ta học cách phớt lờ, và làm hỏng luôn những lần
báo đúng.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.decompose import (
    PLAN_FILE,
    TRAN_TAI_CPU,
    DecomposeError,
    DecompositionPlan,
    LlmDecomposer,
    ModuleProposal,
)

REPO = Path(__file__).resolve().parent.parent


def _m(ma: str, **kw) -> ModuleProposal:
    kw.setdefault("purpose", f"trách nhiệm của {ma}")
    return ModuleProposal(id=ma, **kw)


def _ban(*modules: ModuleProposal, **kw) -> DecompositionPlan:
    return DecompositionPlan(modules=modules or (_m("mod_a"),), goal="mục tiêu thử", **kw)


class _HoSoGia:
    peripherals = [{"id": "timer1"}, {"id": "usart0"}, {"id": "adc1"}]
    components = [{"id": "led_bao"}]


class _RangBuocGia:
    """Ràng buộc giả — phải mang ĐỦ ba trường như vật thật.

    Bản trước thiếu `style`, và nó lọt vì bối cảnh phân rã hồi ấy cũng bỏ qua
    `style`. Khi bối cảnh chuyển sang dùng CHUNG bảng K1 với đường sinh mã
    (SL-131), cái giả thiếu trường lập tức lộ ra.

    Bài học: một vật giả mô phỏng thiếu thì nó không kiểm được đường mã đi qua
    phần còn thiếu ấy — và nó xanh, nên không ai biết.
    """

    limits = {"control_loop_ms": 10}
    forbidden = ["delay()"]
    style = {"arithmetic": "integer"}


# --------------------------------------------------------------------------
# TC-50a — bốn thứ đề xuất cùng lúc
# --------------------------------------------------------------------------


def test_module_mang_du_bon_thu() -> None:
    m = _m("drv_temp", uses=("adc1",), depends_on=(), provides=("drv_temp_read",),
           period_ms=100, est_exec_ms=2.0, layer="driver")
    assert m.uses and m.provides and m.scheduled
    assert m.load == pytest.approx(0.02)


def test_module_khong_chay_dinh_ky_thi_khong_ton_CPU() -> None:
    assert _m("lib_loc", period_ms=0, est_exec_ms=5.0).load == 0.0


def test_ma_module_phai_go_lai_duoc() -> None:
    """Mã này thành tên tệp và tên hàm."""
    for xau in ("", "Có Dấu", "a b", "1abc", "X" * 50):
        with pytest.raises(DecomposeError, match="Mã module"):
            _m(xau)


def test_module_khong_neu_trach_nhiem_bi_tu_choi() -> None:
    with pytest.raises(DecomposeError, match="trách nhiệm"):
        ModuleProposal(id="abc", purpose="  ")


def test_ma_trung_nhau_bi_tu_choi() -> None:
    with pytest.raises(DecomposeError, match="trùng nhau"):
        _ban(_m("mod_a"), _m("mod_a"))


def test_phu_thuoc_vao_module_khong_co_bi_tu_choi() -> None:
    with pytest.raises(DecomposeError, match="không có trong bản"):
        _ban(_m("mod_a", depends_on=("khong_co",)))


# --------------------------------------------------------------------------
# TC-50b — thứ tự làm suy từ phụ thuộc
# --------------------------------------------------------------------------


def test_sap_topo_dung_thu_tu() -> None:
    ban = _ban(
        _m("dieu_phoi", depends_on=("logic",)),
        _m("logic", depends_on=("drv",)),
        _m("drv"),
    )
    assert ban.order() == ["drv", "logic", "dieu_phoi"]


def test_nhom_lam_song_song_duoc() -> None:
    """Người cần biết cái nào chặn cái nào để ưu tiên đúng."""
    ban = _ban(
        _m("drv_a"), _m("drv_b"),
        _m("logic", depends_on=("drv_a", "drv_b")),
    )
    assert ban.parallel_groups() == [["drv_a", "drv_b"], ["logic"]]


def test_vong_phu_thuoc_bi_bat_ngay() -> None:
    """Phát hiện lúc lập kế hoạch rẻ hơn nhiều so với lúc viết nửa số module."""
    ban = _ban(_m("mod_a", depends_on=("mod_b",)), _m("mod_b", depends_on=("mod_a",)))
    with pytest.raises(DecomposeError, match="thành vòng"):
        ban.order()


def test_thong_bao_vong_goi_y_cach_cat() -> None:
    ban = _ban(_m("mod_a", depends_on=("mod_b",)), _m("mod_b", depends_on=("mod_a",)))
    with pytest.raises(DecomposeError, match="tách một interface"):
        ban.order()


def test_thu_tu_on_dinh_giua_hai_lan_chay() -> None:
    ban = _ban(_m("mod_z"), _m("mod_a"), _m("mod_m"))
    assert ban.order() == ban.order() == ["mod_a", "mod_m", "mod_z"]


# --------------------------------------------------------------------------
# TC-50c — ước lượng tải CPU
# --------------------------------------------------------------------------


def test_tinh_tong_tai() -> None:
    ban = _ban(
        _m("mod_a", period_ms=10, est_exec_ms=2.0),
        _m("mod_b", period_ms=100, est_exec_ms=10.0),
    )
    assert ban.total_load == pytest.approx(0.3)
    assert not ban.overloaded


def test_vuot_tran_thi_bao_ro_va_goi_y_cach_xu_ly() -> None:
    ban = _ban(_m("mod_a", period_ms=10, est_exec_ms=8.0))
    assert ban.overloaded

    van_ban = ban.render()
    assert "VƯỢT TRẦN" in van_ban
    assert "giãn chu kỳ, gộp module" in van_ban


def test_luon_noi_ro_day_la_uoc_luong() -> None:
    """Nhầm ước lượng với số đo là cách tự tin sai chỗ."""
    assert "ƯỚC LƯỢNG, không phải số đo" in _ban(_m("mod_a", period_ms=10, est_exec_ms=1)).render()


def test_viec_khong_chay_xong_trong_chu_ky_cua_no() -> None:
    from eaa.decompose import _kiem_chu_ky

    canh_bao = _kiem_chu_ky([_m("mod_a", period_ms=5, est_exec_ms=8.0)], None)
    assert any("LỚN HƠN chu kỳ" in c for c in canh_bao)


def test_khong_co_viec_nao_lam_vong_dieu_khien() -> None:
    from eaa.decompose import _kiem_chu_ky

    canh_bao = _kiem_chu_ky([_m("mod_a", period_ms=100, est_exec_ms=1)], _RangBuocGia())
    assert any("không có ai thực hiện" in c for c in canh_bao)


def test_chu_ky_khong_phai_boi_so_cua_viec_nhanh_nhat() -> None:
    from eaa.decompose import _kiem_chu_ky

    canh_bao = _kiem_chu_ky(
        [_m("mod_a", period_ms=10, est_exec_ms=1), _m("mod_b", period_ms=25, est_exec_ms=1)],
        _RangBuocGia(),
    )
    assert any("bội số" in c for c in canh_bao)


def test_KHONG_bao_dong_gia_voi_viec_cham_hop_le() -> None:
    """Lỗi thật của bản đầu: telemetry mỗi 100 ms bị báo sai là vi phạm.

    Trần ``control_loop_ms`` là trần của VÒNG ĐIỀU KHIỂN, không phải của mọi
    việc. Một cơ chế báo động sai thì người ta học cách phớt lờ.
    """
    from eaa.decompose import _kiem_chu_ky

    canh_bao = _kiem_chu_ky(
        [
            _m("vong_dieu_khien", period_ms=10, est_exec_ms=3, layer="logic"),
            _m("telemetry", period_ms=100, est_exec_ms=2, layer="logic"),
            _m("nhay_led", period_ms=500, est_exec_ms=0.5, layer="logic"),
        ],
        _RangBuocGia(),
    )
    assert canh_bao == [], f"báo động giả: {canh_bao}"


# --------------------------------------------------------------------------
# TC-50d — không bịa tài nguyên
# --------------------------------------------------------------------------


def test_chiem_ngoai_vi_khong_co_thi_canh_bao() -> None:
    """Mô hình rất hay bịa một ngoại vi nghe hợp lý."""
    from eaa.decompose import _kiem_tai_nguyen

    canh_bao = _kiem_tai_nguyen([_m("mod_a", uses=("can_bus",))], _HoSoGia())
    assert any("KHÔNG CÓ trong hồ sơ" in c for c in canh_bao)


def test_chiem_ngoai_vi_co_that_thi_khong_canh_bao() -> None:
    from eaa.decompose import _kiem_tai_nguyen

    assert _kiem_tai_nguyen([_m("mod_a", uses=("timer1", "led_bao"))], _HoSoGia()) == []


def test_khong_co_ho_so_thi_khong_doan_bua() -> None:
    from eaa.decompose import _kiem_tai_nguyen

    assert _kiem_tai_nguyen([_m("mod_a", uses=("bat_ky",))], None) == []


# --------------------------------------------------------------------------
# TC-50e — Agent không tự thêm vào backlog
# --------------------------------------------------------------------------


def test_ban_in_ra_noi_ro_agent_khong_tu_them() -> None:
    van_ban = _ban(_m("mod_a")).render()
    assert "Agent KHÔNG tự thêm vào backlog" in van_ban
    assert "eaa plan accept" in van_ban


def test_luu_va_doc_lai_nguyen_ven(tmp_path: Path) -> None:
    goc = _ban(
        _m("drv", uses=("adc1",), provides=("drv_read",), period_ms=100, est_exec_ms=2),
        _m("logic", depends_on=("drv",), period_ms=10, est_exec_ms=1),
        warnings=("một cảnh báo",),
    )
    duong_dan = goc.save(tmp_path / "plan.json")
    lai = DecompositionPlan.load(duong_dan)

    assert [m.id for m in lai.modules] == [m.id for m in goc.modules]
    assert lai.modules[0].uses == ("adc1",)
    assert lai.warnings == ("một cảnh báo",)


def test_ho_so_hong_thi_bao_ro(tmp_path: Path) -> None:
    duong_dan = tmp_path / "plan.json"
    duong_dan.write_text("khong-phai-json", encoding="utf-8")
    with pytest.raises(DecomposeError, match="hỏng"):
        DecompositionPlan.load(duong_dan)


def test_khong_co_ban_thi_tra_None(tmp_path: Path) -> None:
    assert DecompositionPlan.load(tmp_path / "khong-co.json") is None


# --------------------------------------------------------------------------
# Đề xuất bằng mô hình
# --------------------------------------------------------------------------


class _LlmGia:
    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def _json_ban(*modules: dict) -> str:
    return "```json\n" + json.dumps({"modules": list(modules)}) + "\n```"


def test_de_xuat_boc_duoc_va_kiem_luon() -> None:
    llm = _LlmGia(
        _json_ban(
            {"id": "drv_temp", "purpose": "đọc nhiệt", "layer": "driver",
             "uses": ["adc1"], "period_ms": 100, "est_exec_ms": 2},
            {"id": "logic", "purpose": "xử lý", "layer": "logic",
             "depends_on": ["drv_temp"], "period_ms": 10, "est_exec_ms": 1},
        )
    )
    ban = LlmDecomposer(llm=llm).propose(
        "đo nhiệt độ", hardware=_HoSoGia(), constraints=_RangBuocGia()
    )

    assert [m.id for m in ban.modules] == ["drv_temp", "logic"]
    assert ban.order() == ["drv_temp", "logic"]
    assert ban.proposed_by == "mo-hinh-gia-1"
    assert ban.warnings == ()


def test_de_xuat_bia_ngoai_vi_thi_kem_canh_bao() -> None:
    llm = _LlmGia(
        _json_ban(
            {"id": "drv_can", "purpose": "bus CAN", "uses": ["can_bus"],
             "period_ms": 10, "est_exec_ms": 1},
        )
    )
    ban = LlmDecomposer(llm=llm).propose("x", hardware=_HoSoGia(), constraints=_RangBuocGia())
    assert any("KHÔNG CÓ trong hồ sơ" in c for c in ban.warnings)


def test_khong_co_muc_tieu_thi_khong_phan_ra() -> None:
    """Agent không tự nghĩ ra bài toán."""
    with pytest.raises(DecomposeError, match="Agent không tự nghĩ ra"):
        LlmDecomposer(llm=_LlmGia("")).propose("   ")


def test_prompt_cam_bia_ngoai_vi_va_cam_dat_chu_ky_bua() -> None:
    llm = _LlmGia(_json_ban({"id": "mod_a", "purpose": "x", "period_ms": 10, "est_exec_ms": 1}))
    LlmDecomposer(llm=llm).propose("x", hardware=_HoSoGia(), constraints=_RangBuocGia())

    van_ban = llm.prompts[0].full_text()
    assert "không bịa ngoại vi" in van_ban
    assert "không đặt bừa" in van_ban
    assert "adc1" in van_ban, "phải nêu tài nguyên CÓ THẬT để mô hình bám vào"


def test_ban_rong_bi_tu_choi() -> None:
    with pytest.raises(DecomposeError, match="không có module nào"):
        LlmDecomposer(llm=_LlmGia("```json\n{\"modules\": []}\n```")).propose("x")


# --------------------------------------------------------------------------
# Nối vào CLI
# --------------------------------------------------------------------------


def test_lenh_plan_co_propose_va_accept() -> None:
    import argparse

    from eaa.cli import build_parser

    for hanh_dong in build_parser()._actions:
        if isinstance(hanh_dong, argparse._SubParsersAction):
            plan = hanh_dong.choices["plan"]
            break
    con = next(
        a for a in plan._actions if isinstance(a, argparse._SubParsersAction)
    ).choices
    assert {"propose", "accept", "add", "list", "order"} <= set(con)


def test_nhan_ban_qua_tai_phai_noi_ro_y_dinh() -> None:
    import argparse

    from eaa.cli import build_parser

    for hanh_dong in build_parser()._actions:
        if isinstance(hanh_dong, argparse._SubParsersAction):
            plan = hanh_dong.choices["plan"]
            break
    accept = next(
        a for a in plan._actions if isinstance(a, argparse._SubParsersAction)
    ).choices["accept"]
    co = {c for a in accept._actions for c in a.option_strings}
    assert "--du-biet-qua-tai" in co
