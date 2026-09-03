"""Tầng LLM — ngân sách ngữ cảnh, bóc tách phản hồi, che khóa, MockLLM.

Ba yêu cầu được canh ở đây:

* **FR-CTX-01 / TC-16** — vượt ngân sách là LỖI LẮP RÁP: chặn trước khi gọi
  API, và báo đích danh lớp nào vượt. Báo "prompt quá dài" mà không nói lớp
  nào thì người sửa chỉ còn cách cắt bừa.
* **NFR-06 / TC-14** — khóa API không bao giờ xuất hiện ở bất kỳ đầu ra nào,
  kể cả trong băm prompt.
* **EAA-SDD-03 §6** — phản hồi sai định dạng tính là một lần fail của vòng tự
  sửa, không phải một lỗi hạ tầng.
"""

from __future__ import annotations

import pytest

from eaa.llm.base import (
    LAYER_BUDGETS,
    TOTAL_BUDGET,
    BudgetExceeded,
    LLMClient,
    LLMError,
    Prompt,
    PromptLayer,
    estimate_tokens,
    mask_secrets,
    parse_file_blocks,
)
from eaa.llm.mock import SCENARIOS, MockLLM


def _prompt(**ghi_de) -> Prompt:
    mac_dinh = dict(
        system_instruction="Bạn là kỹ sư firmware. CẤM cấp phát động.",
        layers=[
            PromptLayer("role_constraints", "CẤM delay(). RAM < 2KB.", budget=800, required=True),
            PromptLayer("task", "Viết module đọc cảm biến.", budget=500),
        ],
        module="drv_bus_sensor",
        constraints_version="sha256:ab12",
        chunk_ids=("ds-021",),
    )
    mac_dinh.update(ghi_de)
    return Prompt(**mac_dinh)


# --------------------------------------------------------------------------
# Ngân sách — Hình 1 của AIS
# --------------------------------------------------------------------------


def test_ngan_sach_tung_lop_cong_dung_bang_tran_tong() -> None:
    """Hình 1 AIS chia 8.000 token thành bảy lớp; tổng phải khớp."""
    assert sum(LAYER_BUDGETS.values()) == TOTAL_BUDGET == 8_000


def test_prompt_trong_ngan_sach_thi_di_qua() -> None:
    _prompt().check_budget()


def test_tc16_vuot_tran_tong_bi_chan_truoc_khi_goi_api() -> None:
    prompt = _prompt(
        layers=[PromptLayer("datasheet_chunks", "thanh ghi " * 6000, budget=1500)]
    )
    with pytest.raises(BudgetExceeded) as loi:
        prompt.check_budget()

    assert loi.value.total > TOTAL_BUDGET
    assert loi.value.budget == TOTAL_BUDGET
    assert "datasheet_chunks" in str(loi.value)


def test_tc16_bao_dich_danh_lop_nao_vuot_phan_cua_no() -> None:
    """Trong trần tổng nhưng một lớp phình — GHI LẠI, không chặn (SL-161).

    Bản trước đòi chặn. Đo được trong hai ngày làm việc với phần cứng: mười hai
    lần bị chặn với tổng dao động 3.100–4.300 trên 8.000 — không lần nào là
    thiếu chỗ thật, mỗi lần một vòng đi lại.

    Phần của mỗi lớp là cách chia công bằng KHI CÓ TRANH CHẤP; tổng còn trống
    nghĩa là chưa có tranh chấp. Việc chỉ đích danh thủ phạm vẫn còn nguyên ở
    chỗ nó có nghĩa — xem `test_tc16_vuot_tran_tong_bi_chan_truoc_khi_goi_api`.
    """
    prompt = _prompt(
        layers=[
            PromptLayer("error_rules", "quy tắc " * 400, budget=300),
            PromptLayer("task", "ngắn", budget=500),
        ]
    )
    prompt.check_budget()  # không ném

    assert sum(prompt.token_report().values()) <= TOTAL_BUDGET
    assert prompt.over_share, "vượt phần mà không ghi lại là phình trong im lặng"
    gop = "\n".join(prompt.over_share)
    assert "error_rules" in gop and "task" not in gop


def test_thong_diep_vuot_ngan_sach_noi_ro_khong_goi_api() -> None:
    prompt = _prompt(layers=[PromptLayer("datasheet_chunks", "x " * 9000, budget=1500)])
    with pytest.raises(BudgetExceeded, match="Không gọi API"):
        prompt.check_budget()


def test_bao_cao_token_tinh_ca_system_instruction() -> None:
    """System instruction mang lớp ràng buộc — bỏ nó ra ngoài là đếm thiếu."""
    prompt = _prompt()
    bao_cao = prompt.token_report()
    assert "system_instruction" in bao_cao
    assert prompt.total_tokens() == sum(bao_cao.values())


def test_ngan_sach_kiem_bang_bo_dem_cua_chinh_mo_hinh() -> None:
    """AIS §2: count_tokens của mô hình sẽ gọi, không phải ước lượng chung."""
    dem_goi = []

    def dem_that(text: str) -> int:
        dem_goi.append(text)
        return 1

    _prompt().check_budget(dem_that)
    assert dem_goi, "check_budget phải dùng bộ đếm được truyền vào"


def test_uoc_luong_token_nghieng_ve_phia_chan_nham() -> None:
    """Sai số phải nghiêng về chặn nhầm, không phải cho qua nhầm."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("một hai ba") >= 3
    ngan, dai = estimate_tokens("a b"), estimate_tokens("a b c d e f")
    assert dai > ngan


# --------------------------------------------------------------------------
# Truy vết
# --------------------------------------------------------------------------


def test_bam_prompt_on_dinh_va_doi_khi_noi_dung_doi() -> None:
    a, b = _prompt(), _prompt()
    assert a.hash == b.hash

    khac = _prompt(layers=[PromptLayer("task", "Nhiệm vụ khác", budget=500)])
    assert khac.hash != a.hash


def test_tc14_khoa_api_bi_che_trong_bam_va_trong_log(monkeypatch) -> None:
    monkeypatch.setenv("EAA_LLM_KEY", "khoa-that-cua-toi-123456")

    assert "khoa-that-cua-toi-123456" not in mask_secrets("key=khoa-that-cua-toi-123456")
    assert mask_secrets("api_key: AIzaSyABCDEFGHIJKLMNOPQRSTUVWX123") == "***"
    assert "sk-" not in mask_secrets("token sk-abcdefghijklmnopqrstuvwx")

    # Băm được tính trên nội dung ĐÃ che: prompt lỡ mang khóa băm ra đúng bằng
    # prompt đã thay khóa bằng dấu sao — nên băm không phải kênh suy ngược ra khóa.
    lo_mang_khoa = _prompt(system_instruction="Xác thực bằng khoa-that-cua-toi-123456")
    da_che = _prompt(system_instruction="Xác thực bằng ***")
    assert lo_mang_khoa.hash == da_che.hash


def test_prompt_giu_du_truong_truy_vet_NFR07() -> None:
    prompt = _prompt()
    assert prompt.module and prompt.constraints_version and prompt.chunk_ids
    assert prompt.hash.startswith("sha256:")


def test_tra_cuu_lop_theo_ten() -> None:
    prompt = _prompt()
    assert prompt.layer("task") is not None
    assert prompt.layer("khong-co") is None


def test_render_bo_qua_lop_rong() -> None:
    prompt = _prompt(
        layers=[
            PromptLayer("a", "có nội dung"),
            PromptLayer("b", "   "),
            PromptLayer("c", "cũng có"),
        ]
    )
    assert prompt.render() == "có nội dung\n\ncũng có"


# --------------------------------------------------------------------------
# Bóc tách phản hồi
# --------------------------------------------------------------------------


def test_boc_tach_khoi_file() -> None:
    tep = parse_file_blocks(SCENARIOS["pass"])
    assert set(tep) == {"src/module.c", "src/module.h"}
    assert "module_init" in tep["src/module.c"]


def test_phan_hoi_sai_dinh_dang_tinh_la_mot_lan_fail() -> None:
    with pytest.raises(LLMError, match="fail của vòng tự sửa"):
        parse_file_blocks(SCENARIOS["malformed"])


def test_hai_khoi_cho_cung_mot_tep_bi_tu_choi() -> None:
    """Không xác định được bản nào là bản cuối thì không được đoán."""
    with pytest.raises(LLMError, match="hai khối"):
        parse_file_blocks("```file:a.c\nmột\n```\n```file:a.c\nhai\n```")


def test_boc_tach_chap_nhan_nhan_ngon_ngu_truoc_file() -> None:
    tep = parse_file_blocks("```c file:src/a.c\nint main(void){return 0;}\n```")
    assert "src/a.c" in tep


# --------------------------------------------------------------------------
# MockLLM
# --------------------------------------------------------------------------


def test_mock_tuan_thu_giao_dien_LLMClient() -> None:
    assert isinstance(MockLLM(), LLMClient)


def test_mock_sinh_ma_va_mang_du_truy_vet() -> None:
    llm = MockLLM()
    artifact = llm.generate(_prompt())

    assert set(artifact.files) == {"src/module.c", "src/module.h"}
    assert artifact.model == "mock-deterministic-1"
    assert artifact.constraints_version == "sha256:ab12"
    assert artifact.chunk_ids == ["ds-021"]
    assert artifact.tokens_in > 0 and artifact.tokens_out > 0


def test_mock_chen_chunk_id_that_vao_trich_dan() -> None:
    """Mã mẫu mang đúng chunk đã nạp — để cổng kiểm trích dẫn có cái để bắt."""
    artifact = MockLLM().generate(_prompt(chunk_ids=("ds-021",)))
    assert "// ref: ds-021" in artifact.files["src/module.c"]


def test_mock_tat_dinh() -> None:
    a = MockLLM().generate(_prompt())
    b = MockLLM().generate(_prompt())
    assert a.files == b.files and a.prompt_hash == b.prompt_hash


def test_mock_tu_kiem_ngan_sach_truoc_khi_goi() -> None:
    """Adapter phải tự chặn, không trông chờ Orchestrator nhớ hộ."""
    llm = MockLLM()
    with pytest.raises(BudgetExceeded):
        llm.generate(_prompt(layers=[PromptLayer("task", "x " * 9000, budget=500)]))
    assert llm.call_count == 0, "không được ghi nhận lần gọi nào khi đã bị chặn"


def test_mock_ghi_lai_prompt_de_test_soi_duoc() -> None:
    llm = MockLLM()
    llm.generate(_prompt())
    assert "CẤM delay()" in llm.last_prompt
    assert "CẤM cấp phát động" in llm.last_prompt, "system instruction phải nằm trong bản ghi"
    assert llm.call_count == 1


def test_mock_day_phan_hoi_dung_de_dung_kich_ban_vong_tu_sua() -> None:
    """Hỏng hai lần rồi sửa được ở lần ba."""
    llm = MockLLM(responses=[SCENARIOS["fail"], SCENARIOS["fail"], SCENARIOS["pass"]])
    assert "undeclared_helper" in llm.generate(_prompt()).raw_response
    assert "undeclared_helper" in llm.generate(_prompt()).raw_response
    assert "module_step" in llm.generate(_prompt()).raw_response
    # Hết dãy thì giữ nguyên phần tử cuối.
    assert "module_step" in llm.generate(_prompt()).raw_response


def test_mock_anh_xa_theo_module() -> None:
    llm = MockLLM(responses={"drv_bus_sensor": SCENARIOS["violation"]})
    assert "malloc" in llm.generate(_prompt()).raw_response
    with pytest.raises(LLMError, match="không có phản hồi định sẵn"):
        llm.generate(_prompt(module="module_la"))


def test_mock_ham_sinh_phan_hoi_theo_lan_goi() -> None:
    llm = MockLLM(responses=lambda prompt, lan: f"```file:a{lan}.c\nint x;\n```")
    assert "a0.c" in llm.generate(_prompt()).files
    assert "a1.c" in llm.generate(_prompt()).files


def test_kich_ban_khong_ton_tai_bao_loi_kem_danh_sach() -> None:
    with pytest.raises(LLMError, match="đang có"):
        MockLLM(scenario="khong-co").generate(_prompt())


@pytest.mark.parametrize("kich_ban", ["fail", "violation", "no_citation"])
def test_cac_kich_ban_hong_deu_boc_tach_duoc(kich_ban: str) -> None:
    """Mã hỏng vẫn phải là mã: nó phải tới được cổng kiểm chứng để bị chặn ở đó."""
    artifact = MockLLM(scenario=kich_ban).generate(_prompt())
    assert artifact.files


def test_kich_ban_vi_pham_dung_cham_du_ba_rang_buoc_cam() -> None:
    ma = SCENARIOS["violation"]
    assert "delay(" in ma and "malloc" in ma and "descend(" in ma


def test_kich_ban_thieu_trich_dan_khong_co_ref() -> None:
    """Kịch bản cho TC-17: cấu hình thanh ghi mà không trích dẫn nguồn."""
    assert "// ref:" not in SCENARIOS["no_citation"]
