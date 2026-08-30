"""TC-56 — giao diện sinh trước thân, và giới hạn của test trên máy chủ.

Nghiệp vụ N-041 và N-053.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-56a | Mỗi hàm trả lời ba câu chữ ký không nói được | ngắt / chặn / tái nhập |
| TC-56b | An-toàn-ngắt VÀ chặn là mâu thuẫn, chặn ngay lúc dựng | N-041 |
| TC-56c | Engine không viết C — khuôn tiêu đề nằm ở pack | cùng ranh giới TC-38 |
| TC-56d | Tệp tiêu đề đề xuất nói rõ nó là lời hứa, chưa là mã đã kiểm | đi vào lớp K3 |
| TC-56e | KHÔNG ghi đè tệp tiêu đề đã có | bản cũ có thể của module đã merge |
| TC-56f | Cổng test đơn vị nêu ĐÍCH DANH phần không kiểm được | N-053 |
| TC-56g | Phần không kiểm được là cảnh báo, không phải lỗi | không sửa được bằng thêm test |

TC-56d là mắt xích dễ tuột nhất. Lớp K3 của composer lấy dòng chú thích đầu
tiên của tệp ``.h`` làm tóm tắt, và câu ấy đi thẳng vào prompt của module phụ
thuộc. Nếu một giao diện mới chỉ là đề xuất mà trông y hệt giao diện của một
module đã merge, thì mô hình sẽ viết mã dựa vào một hợp đồng chưa ai kiểm mà
không biết mình đang làm thế.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from eaa.interfaces import (
    BANNER_DE_XUAT,
    FunctionContract,
    InterfaceError,
    InterfaceGenerator,
    InterfaceSpec,
    LlmInterfaceDesigner,
)
from eaa.platform import load_manifest
from eaa.tools.unittests import UnitTestGate, host_gaps

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"


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


def _json(du_lieu) -> _LlmGia:
    return _LlmGia("```json\n" + json.dumps(du_lieu, ensure_ascii=False) + "\n```")


def _ham(**kw) -> FunctionContract:
    kw.setdefault("signature", "void drv_bus_init(void)")
    kw.setdefault("purpose", "Dựng bus về trạng thái sẵn sàng")
    return FunctionContract(**kw)


# --------------------------------------------------------------------------
# TC-56a, TC-56b — hợp đồng gọi
# --------------------------------------------------------------------------


def test_hop_dong_tra_loi_du_ba_cau() -> None:
    van_ban = _ham(isr_safe=True, blocking=False, reentrant=True).contract_text()

    assert "gọi trong ngắt: ĐƯỢC" in van_ban
    assert "không chặn" in van_ban
    assert "tái nhập được" in van_ban


def test_mac_dinh_la_KHONG_chu_khong_phai_chac_la_duoc() -> None:
    """Một mặc định êm ái sẽ được nhận vì nó tiện, và sai lệch lộ ra dưới tải."""
    van_ban = _ham().contract_text()

    assert "gọi trong ngắt: KHÔNG" in van_ban
    assert "KHÔNG tái nhập" in van_ban


def test_vua_an_toan_ngat_vua_chan_la_mau_thuan() -> None:
    with pytest.raises(InterfaceError, match="mâu thuẫn"):
        _ham(isr_safe=True, blocking=True)


def test_chu_ky_khong_phai_khai_bao_ham_thi_tu_choi() -> None:
    with pytest.raises(InterfaceError, match="khai báo hàm"):
        FunctionContract(signature="int mot_bien")


def test_chu_ky_kem_dau_cham_phay_bi_tu_choi() -> None:
    """Engine không ghép cú pháp C — dấu kết câu do khuôn của pack đặt."""
    with pytest.raises(InterfaceError, match="chấm phẩy"):
        FunctionContract(signature="void f(void);")


def test_hai_ham_trung_ten_bi_bat_som() -> None:
    with pytest.raises(InterfaceError, match="hai lần"):
        InterfaceSpec(
            module_id="drv_bus",
            functions=(_ham(signature="void f(void)"), _ham(signature="int f(int a)")),
        )


def test_giao_dien_trong_la_mot_cho_ho() -> None:
    ban = InterfaceSpec(module_id="drv_bus")
    assert any("sinh song song mất hết ý nghĩa" in t for t in ban.gaps())


def test_ham_khong_noi_lam_gi_la_mot_cho_ho() -> None:
    ban = InterfaceSpec(module_id="drv_bus", functions=(_ham(purpose=""),))
    assert any("chưa nói hàm này làm gì" in t for t in ban.gaps())


def test_ten_ham_rut_duoc_tu_chu_ky() -> None:
    assert _ham(signature="int8_t drv_bus_read(uint8_t reg, uint8_t *out)").name == "drv_bus_read"


def test_macro_chong_nap_trung_suy_tu_ma_module() -> None:
    assert InterfaceSpec(module_id="drv_bus_2").guard == "DRV_BUS_2_H"


# --------------------------------------------------------------------------
# TC-56c, TC-56d, TC-56e — sinh tệp tiêu đề từ khuôn của pack
# --------------------------------------------------------------------------


@pytest.fixture()
def spec() -> InterfaceSpec:
    return InterfaceSpec(
        module_id="drv_bus",
        purpose="Điều khiển bus nối cảm biến",
        functions=(
            _ham(),
            _ham(
                signature="int8_t drv_bus_read(uint8_t reg, uint8_t *out)",
                purpose="Đọc một thanh ghi",
                blocking=True,
            ),
        ),
        includes=("stddef.h",),
    )


def test_sinh_tep_tieu_de_tu_khuon_cua_pack(spec: InterfaceSpec) -> None:
    van_ban = InterfaceGenerator(load_manifest(PACK_DEMO)).render(spec)

    assert "#ifndef DRV_BUS_H" in van_ban
    assert "void drv_bus_init(void);" in van_ban
    assert "int8_t drv_bus_read(uint8_t reg, uint8_t *out);" in van_ban
    assert "gọi trong ngắt: KHÔNG" in van_ban
    assert "CHẶN" in van_ban


def test_pack_khong_khai_khuon_thi_noi_thang_chu_khong_tu_ghep_C(
    spec: InterfaceSpec, tmp_path: Path
) -> None:
    import yaml

    goc = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    goc.pop("interfaces")
    thu_muc = tmp_path / "pack-khong-khuon"
    thu_muc.mkdir()
    (thu_muc / "pack.yaml").write_text(
        yaml.safe_dump(goc, allow_unicode=True), encoding="utf-8"
    )

    with pytest.raises(InterfaceError, match="engine không tự ghép cú pháp C"):
        InterfaceGenerator(load_manifest(thu_muc)).render(spec)


def test_engine_khong_chua_cu_phap_C_cua_tep_tieu_de() -> None:
    """Macro chống nạp trùng và cách viết chú thích là chuyện của nền tảng."""
    ma = (REPO / "eaa" / "interfaces.py").read_text(encoding="utf-8")
    for cu_phap in ("#ifndef", "#define", "#endif", "/* {"):
        assert cu_phap not in ma, f"{cu_phap!r} bị ghim trong engine"


def test_tep_de_xuat_noi_ro_no_la_loi_hua_chua_la_ma_da_kiem(
    spec: InterfaceSpec, tmp_path: Path
) -> None:
    """Dòng này đi thẳng vào lớp K3 của prompt module phụ thuộc."""
    duong_dan = InterfaceGenerator(load_manifest(PACK_DEMO)).write(spec, tmp_path)
    van_ban = duong_dan.read_text(encoding="utf-8")

    assert BANNER_DE_XUAT in van_ban
    assert "CHƯA sinh" in van_ban


def test_banner_di_vao_prompt_cua_module_phu_thuoc(spec: InterfaceSpec, tmp_path: Path) -> None:
    """Không phải kiểm chuỗi trong tệp, mà kiểm nó tới được nơi có tác dụng."""
    from eaa.composer import PromptComposer

    firmware = tmp_path / "firmware"
    InterfaceGenerator(load_manifest(PACK_DEMO)).write(spec, firmware)

    tom_tat = PromptComposer._tom_tat_header(
        (firmware / "drv_bus.h").read_text(encoding="utf-8")
    )
    assert "Điều khiển bus" in tom_tat or BANNER_DE_XUAT[:20] in tom_tat


def test_khong_ghi_de_tep_tieu_de_da_co(spec: InterfaceSpec, tmp_path: Path) -> None:
    """Bản cũ có thể của module đã merge, và module khác đang dựa vào nó."""
    gen = InterfaceGenerator(load_manifest(PACK_DEMO))
    gen.write(spec, tmp_path)

    with pytest.raises(InterfaceError, match="KHÔNG ghi đè"):
        gen.write(spec, tmp_path)


def test_dung_giao_dien_tu_mo_hinh() -> None:
    llm = _json(
        {
            "purpose": "Điều khiển bus",
            "includes": ["stdint.h"],
            "functions": [
                {
                    "signature": "void drv_bus_init(void);",
                    "purpose": "khởi tạo",
                    "isr_safe": False,
                    "blocking": False,
                    "reentrant": True,
                }
            ],
        }
    )
    spec = LlmInterfaceDesigner(llm=llm).design(module_id="drv_bus", uses=("bus_a",))

    assert spec.functions[0].name == "drv_bus_init"
    assert not spec.functions[0].signature.endswith(";"), "dấu chấm phẩy phải bị gỡ"
    assert spec.proposed_by == "mo-hinh-gia-1"


def test_mo_hinh_tra_ve_hop_dong_mau_thuan_thi_khong_lot() -> None:
    llm = _json(
        {
            "functions": [
                {"signature": "void f(void)", "isr_safe": True, "blocking": True}
            ]
        }
    )
    with pytest.raises(InterfaceError, match="mâu thuẫn"):
        LlmInterfaceDesigner(llm=llm).design(module_id="drv_bus")


# --------------------------------------------------------------------------
# TC-56f, TC-56g — phần không kiểm được trên máy chủ (N-053)
# --------------------------------------------------------------------------


class _DoThiGia:
    def registers_for(self, module_id: str) -> list[str]:
        return ["REG_A1", "REG_A2"]

    def resources_of(self, module_id: str) -> list[str]:
        return ["bus_a"]


class _RangBuocGia:
    limits = {"control_loop_ms": 10, "max_module_lines": 300}


def test_neu_dich_danh_thanh_ghi_khong_kiem_duoc_tren_may_chu() -> None:
    thieu = host_gaps(module_id="drv_bus", graph=_DoThiGia(), constraints=_RangBuocGia())

    assert any("REG_A1" in t for t in thieu), "phải gọi đúng tên, không nói chung chung"
    assert any("bus_a" in t for t in thieu)
    assert any("control_loop_ms" in t for t in thieu)


def test_moi_loai_thieu_sot_chi_ra_cho_no_duoc_dong() -> None:
    """Ba loại khác nhau được đóng ở ba chỗ khác nhau — nói ra thì mới đi tiếp được."""
    thieu = host_gaps(module_id="drv_bus", graph=_DoThiGia(), constraints=_RangBuocGia())
    gop = "\n".join(thieu)

    assert "nghiệm thu trên thiết bị" in gop
    assert "eaa diagnose" in gop
    assert "cổng mô phỏng" in gop


def test_rang_buoc_khong_phai_thoi_gian_thi_khong_bi_keo_vao() -> None:
    class _ChiCoDongMa:
        limits = {"max_module_lines": 300}

    thieu = host_gaps(module_id="m", graph=None, constraints=_ChiCoDongMa())
    assert not any("max_module_lines" in t for t in thieu)


def test_module_khong_cham_phan_cung_thi_khong_bia_ra_thieu_sot() -> None:
    class _DoThiTrong:
        def registers_for(self, module_id: str) -> list[str]:
            return []

        def resources_of(self, module_id: str) -> list[str]:
            return []

    assert host_gaps(module_id="lib_toan", graph=_DoThiTrong(), constraints=None) == []


def test_cong_test_don_vi_neu_thieu_sot_ngay_ca_khi_moi_test_deu_xanh(
    tmp_path: Path,
) -> None:
    """Nhất là khi mọi test đều xanh — đó đúng lúc người dễ tưởng đã phủ hết."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    bao_cao = UnitTestGate(
        tests_dir=tests,
        work_dir=tmp_path,
        module="drv_bus",
        graph=_DoThiGia(),
        constraints=_RangBuocGia(),
    ).run()

    assert bao_cao.passed
    assert bao_cao.metrics["host_gaps"] == 3
    assert any("KHÔNG kiểm được trên máy chủ" in str(w) for w in bao_cao.warnings)


def test_thieu_sot_la_canh_bao_chu_khong_phai_loi(tmp_path: Path) -> None:
    """Không sửa được bằng cách viết thêm test trên máy chủ, nên chặn ở đây là vô ích."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    bao_cao = UnitTestGate(
        tests_dir=tests,
        work_dir=tmp_path,
        module="drv_bus",
        graph=_DoThiGia(),
        constraints=_RangBuocGia(),
    ).run()

    assert bao_cao.passed
    assert not bao_cao.errors


def test_khong_truyen_ngu_canh_thi_cong_chay_y_nhu_truoc(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=tmp_path).run()
    assert bao_cao.passed and bao_cao.metrics["host_gaps"] == 0


# --------------------------------------------------------------------------
# Hai pack thật cũng phải khai khuôn
# --------------------------------------------------------------------------


def test_ca_hai_pack_deu_sinh_duoc_tep_tieu_de(spec: InterfaceSpec) -> None:
    for ten in ("avr", "stm32"):
        manifest = load_manifest(REPO / "packs" / ten)
        assert manifest.interfaces is not None, f"pack {ten} chưa khai khuôn 'interfaces'"
        van_ban = InterfaceGenerator(manifest).render(spec)
        assert "DRV_BUS_H" in van_ban
        assert BANNER_DE_XUAT in van_ban
