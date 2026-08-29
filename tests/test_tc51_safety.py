"""TC-51 — phân tích hỏng hóc và chế độ an toàn (N-016, N-017).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-51a | Mỗi hỏng hóc phải có CÁCH PHÁT HIỆN | thiếu thì nêu đích danh; mức cao/nguy hiểm thì nhấn mạnh |
| TC-51b | Phủ hết tài nguyên trong hồ sơ | tài nguyên không kiểu hỏng nào nhắc tới → nêu tên |
| TC-51c | Chế độ an toàn nói rõ VÀO và RA | thiếu một trong hai thì từ chối ngay lúc dựng |
| TC-51d | Có cơ cấu chấp hành thì phải có chế độ an toàn | thiếu là chỗ hở, nêu rõ hậu quả |
| TC-51e | Agent đề xuất, người chốt tại G1 | không có đường nào để bản này tự có hiệu lực |

Câu hỏi trung tâm của nhóm này không phải "cái gì có thể hỏng" — danh sách ấy
dài vô hạn — mà là **hỏng thì có ai biết không**. Hệ nhúng không có ai ngồi
nhìn: một cảm biến trả rác sẽ được xử lý như số thật cho tới khi có gì đó cháy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from eaa.safety import (
    MUC_NGHIEM_TRONG,
    SAFETY_FILE,
    FailureMode,
    LlmSafetyAnalyst,
    SafeState,
    SafetyAnalysis,
    SafetyError,
)

REPO = Path(__file__).resolve().parent.parent


def _kh(ma: str, **kw) -> FailureMode:
    kw.setdefault("resource", "cam_bien")
    kw.setdefault("failure", "trả giá trị rác")
    return FailureMode(id=ma, **kw)


def _an_toan(**kw) -> SafeState:
    kw.setdefault("description", "Dừng khẩn cấp, cắt truyền động")
    kw.setdefault("entry", ("phát hiện lỗi nguy hiểm",))
    kw.setdefault("exit", ("chỉ thoát bằng khởi động lại nguồn",))
    return SafeState(**kw)


class _HoSoGia:
    peripherals = [{"id": "twi"}, {"id": "usart0"}]
    components = [
        {"id": "imu", "kind": "sensor"},
        {"id": "dong_co_trai", "kind": "actuator"},
    ]


class _HoSoKhongChapHanh:
    peripherals = [{"id": "usart0"}]
    components = [{"id": "imu", "kind": "sensor"}]


# --------------------------------------------------------------------------
# TC-51a — mỗi hỏng hóc phải có cách phát hiện
# --------------------------------------------------------------------------


def test_thieu_cach_phat_hien_thi_neu_dich_danh() -> None:
    """Hỏng không phát hiện được là hỏng sẽ lộ ra trên bàn thí nghiệm."""
    ban = SafetyAnalysis(modes=(_kh("imu_rac"), _kh("imu_treo", detection="quá hạn 50 ms"),))
    thieu = ban.gaps()

    assert any("imu_rac" in t for t in thieu)
    assert not any("imu_treo" in t for t in thieu)


def test_muc_nghiem_trong_ma_khong_phat_hien_duoc_thi_nhan_manh() -> None:
    ban = SafetyAnalysis(modes=(_kh("chap_mosfet", severity="nguy_hiem"),))
    thieu = ban.gaps()

    assert any("CAO/NGUY HIỂM" in t for t in thieu)
    assert any("bắt buộc phải có cách phát hiện" in t for t in thieu)


def test_ban_in_ra_noi_thang_khi_khong_phat_hien_duoc() -> None:
    van_ban = _kh("imu_rac").render()
    assert "KHÔNG CÓ CÁCH NÀO" in van_ban
    assert "bàn thí nghiệm" in van_ban


def test_du_cach_phat_hien_thi_khong_bao_thieu() -> None:
    ban = SafetyAnalysis(
        modes=(_kh("a_hong", detection="kiểm tổng khung"),),
        safe_state=_an_toan(),
    )
    assert ban.gaps() == []


def test_muc_nghiem_trong_khong_hop_le_bi_tu_choi() -> None:
    with pytest.raises(SafetyError, match="mức nghiêm trọng"):
        _kh("a_hong", severity="rat_nang")


def test_kieu_hong_thieu_noi_dung_bi_tu_choi() -> None:
    with pytest.raises(SafetyError, match="hỏng ở đâu"):
        FailureMode(id="a_hong", resource="  ", failure="x")
    with pytest.raises(SafetyError, match="hỏng cái gì"):
        FailureMode(id="a_hong", resource="x", failure="  ")


# --------------------------------------------------------------------------
# TC-51b — phủ hết tài nguyên
# --------------------------------------------------------------------------


def test_tai_nguyen_chua_phu_duoc_neu_ten() -> None:
    """Bỏ sót một cơ cấu chấp hành là bỏ sót đúng cái sẽ hỏng."""
    ban = SafetyAnalysis(modes=(_kh("imu_rac", resource="imu", detection="giới hạn dải"),))
    chua = ban.uncovered(_HoSoGia())

    assert set(chua) == {"twi", "usart0", "dong_co_trai"}


def test_phu_het_thi_khong_con_ho() -> None:
    ban = SafetyAnalysis(
        modes=tuple(
            _kh(f"hong_{i}", resource=r, detection="có cách")
            for i, r in enumerate(("twi", "usart0", "imu", "dong_co_trai"))
        ),
        safe_state=_an_toan(),
    )
    assert ban.uncovered(_HoSoGia()) == []
    assert ban.gaps(_HoSoGia()) == []


def test_khong_phan_biet_hoa_thuong_khi_doi_chieu() -> None:
    ban = SafetyAnalysis(modes=(_kh("a_hong", resource="TWI", detection="x"),))
    assert "twi" not in ban.uncovered(_HoSoGia())


def test_khong_co_ho_so_thi_khong_doan_bua() -> None:
    assert SafetyAnalysis(modes=(_kh("a_hong"),)).uncovered(None) == []


# --------------------------------------------------------------------------
# TC-51c — chế độ an toàn nói rõ vào và ra
# --------------------------------------------------------------------------


def test_thieu_dieu_kien_vao_bi_tu_choi() -> None:
    with pytest.raises(SafetyError, match="không bao giờ được vào"):
        _an_toan(entry=())


def test_thieu_dieu_kien_ra_bi_tu_choi() -> None:
    """Vào mà không ra được là một cục gạch."""
    with pytest.raises(SafetyError, match="cục gạch"):
        _an_toan(exit=())


def test_chu_y_khong_cho_ra_thi_phai_viet_ra() -> None:
    """'Chỉ thoát bằng reset' là một câu trả lời hợp lệ — im lặng thì không."""
    an_toan = _an_toan(exit=("chỉ thoát bằng khởi động lại nguồn",))
    assert "khởi động lại nguồn" in an_toan.render()


def test_thieu_mo_ta_bi_tu_choi() -> None:
    with pytest.raises(SafetyError, match="trạng thái gì"):
        _an_toan(description="   ")


def test_ban_in_ra_du_ba_phan() -> None:
    van_ban = _an_toan(actions=("cắt nguồn động cơ",)).render()
    assert "vào khi:" in van_ban and "ra khi:" in van_ban
    assert "việc phải làm khi vào:" in van_ban


# --------------------------------------------------------------------------
# TC-51d — có cơ cấu chấp hành thì phải có chế độ an toàn
# --------------------------------------------------------------------------


def test_co_co_cau_chap_hanh_ma_thieu_che_do_an_toan() -> None:
    ban = SafetyAnalysis(
        modes=tuple(
            _kh(f"hong_{i}", resource=r, detection="có cách")
            for i, r in enumerate(("twi", "usart0", "imu", "dong_co_trai"))
        )
    )
    thieu = ban.gaps(_HoSoGia())
    assert any("lỗi phần mềm thành hỏng cơ khí" in t for t in thieu)


def test_khong_co_co_cau_chap_hanh_thi_khong_doi() -> None:
    ban = SafetyAnalysis(
        modes=tuple(
            _kh(f"hong_{i}", resource=r, detection="có cách")
            for i, r in enumerate(("usart0", "imu"))
        )
    )
    assert ban.gaps(_HoSoKhongChapHanh()) == []


def test_nhan_biet_chap_hanh_qua_KHAI_BAO_khong_qua_ten() -> None:
    """Engine không được biết tên một họ linh kiện nào."""
    from eaa.safety import _co_co_cau_chap_hanh

    class _Co:
        components = [{"id": "x", "actuator": True}]

    class _Khong:
        components = [{"id": "dong_co_khong_khai_bao"}]

    assert _co_co_cau_chap_hanh(_Co())
    assert not _co_co_cau_chap_hanh(_Khong())


# --------------------------------------------------------------------------
# TC-51e — lưu trữ và chốt
# --------------------------------------------------------------------------


def test_luu_va_doc_lai_nguyen_ven(tmp_path: Path) -> None:
    goc = SafetyAnalysis(
        modes=(_kh("imu_rac", detection="giới hạn dải", severity="nguy_hiem"),),
        safe_state=_an_toan(actions=("cắt nguồn",)),
        proposed_by="mo-hinh-gia-1",
    )
    duong_dan = goc.save(tmp_path / SAFETY_FILE)
    lai = SafetyAnalysis.load(duong_dan)

    assert lai.modes[0].detection == "giới hạn dải"
    assert lai.modes[0].severity == "nguy_hiem"
    assert lai.safe_state.actions == ("cắt nguồn",)
    assert lai.proposed_by == "mo-hinh-gia-1"


def test_tep_luu_noi_ro_cau_hoi_trung_tam(tmp_path: Path) -> None:
    duong_dan = SafetyAnalysis(modes=(_kh("a_hong", detection="x"),)).save(
        tmp_path / SAFETY_FILE
    )
    van_ban = duong_dan.read_text(encoding="utf-8")

    assert "HỎNG THÌ CÓ AI BIẾT KHÔNG" in van_ban
    assert "BẢN ĐỀ XUẤT" in van_ban


def test_ban_in_ra_chi_dung_cong_chot() -> None:
    van_ban = SafetyAnalysis(modes=(_kh("a_hong", detection="x"),)).render()
    assert "Agent KHÔNG tự chốt" in van_ban
    assert "eaa gate approve G1" in van_ban


def test_khong_co_tep_thi_tra_None(tmp_path: Path) -> None:
    assert SafetyAnalysis.load(tmp_path / "khong-co.yaml") is None


def test_tep_hong_thi_bao_ro(tmp_path: Path) -> None:
    duong_dan = tmp_path / SAFETY_FILE
    duong_dan.write_text("a: [1,\n", encoding="utf-8")
    with pytest.raises(SafetyError, match="YAML không hợp lệ"):
        SafetyAnalysis.load(duong_dan)


def test_sap_xep_theo_muc_nghiem_trong() -> None:
    """Người đọc phải gặp thứ nguy hiểm trước, không phải theo thứ tự bảng chữ cái."""
    ban = SafetyAnalysis(
        modes=(
            _kh("aaa_nhe", severity="thap", detection="x"),
            _kh("zzz_nang", severity="nguy_hiem", detection="y"),
        )
    )
    van_ban = ban.render()
    assert van_ban.index("zzz_nang") < van_ban.index("aaa_nhe")


# --------------------------------------------------------------------------
# Dựng bằng mô hình
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


def test_dung_duoc_tu_mo_hinh() -> None:
    llm = _LlmGia(
        "```json\n"
        + json.dumps(
            {
                "failure_modes": [
                    {"id": "imu_rac", "resource": "imu", "failure": "trả rác",
                     "detection": "giới hạn dải", "severity": "nguy_hiem"}
                ],
                "safe_state": {
                    "description": "dừng khẩn cấp",
                    "entry": ["lỗi nguy hiểm"],
                    "exit": ["reset nguồn"],
                },
            }
        )
        + "\n```"
    )
    ban = LlmSafetyAnalyst(llm=llm).analyse(hardware=_HoSoGia(), goal="robot")

    assert ban.modes[0].id == "imu_rac"
    assert ban.safe_state.description == "dừng khẩn cấp"
    assert ban.proposed_by == "mo-hinh-gia-1"


def test_ho_so_trong_thi_khong_phan_tich() -> None:
    """Phân tích bám vào thứ CÓ THẬT trên bo, không vào trí tưởng tượng."""

    class _Trong:
        peripherals: list = []
        components: list = []

    with pytest.raises(SafetyError, match="trí tưởng tượng"):
        LlmSafetyAnalyst(llm=_LlmGia("")).analyse(hardware=_Trong())


def test_prompt_doi_cach_phat_hien_cu_the() -> None:
    llm = _LlmGia(
        '```json\n{"failure_modes": [{"id": "a_hong", "resource": "imu", '
        '"failure": "x", "detection": "y"}]}\n```'
    )
    LlmSafetyAnalyst(llm=llm).analyse(hardware=_HoSoGia())

    van_ban = llm.prompts[0].full_text()
    assert "FIRMWARE NHẬN RA BẰNG CÁCH NÀO" in van_ban
    assert "không nêu cách phát hiện chung chung" in van_ban.lower()
    assert "imu" in van_ban and "dong_co_trai" in van_ban


def test_lenh_safety_co_propose_va_show() -> None:
    import argparse

    from eaa.cli import build_parser

    for hanh_dong in build_parser()._actions:
        if isinstance(hanh_dong, argparse._SubParsersAction):
            safety = hanh_dong.choices["safety"]
            break
    con = next(
        a for a in safety._actions if isinstance(a, argparse._SubParsersAction)
    ).choices
    assert {"propose", "show"} <= set(con)


def test_du_an_mau_da_co_phan_tich_an_toan() -> None:
    """Dự án mẫu phải mang theo bản phân tích, vì nó có cơ cấu chấp hành."""
    duong_dan = REPO / "projects" / "robot_balance" / SAFETY_FILE
    if not duong_dan.is_file():
        pytest.skip("dự án mẫu chưa dựng phân tích an toàn")

    ban = SafetyAnalysis.load(duong_dan)
    assert ban.modes, "phải có kiểu hỏng"
    assert ban.safe_state is not None, "có cơ cấu chấp hành thì phải có chế độ an toàn"
    assert not ban.undetectable, "mọi kiểu hỏng phải có cách phát hiện"
