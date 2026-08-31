"""TC-61 — vòng hội thoại: Agent tự gọi lệnh, nhưng không vượt được gate.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-61a | Agent tự chạy được lệnh trong danh mục và trả lời từ kết quả thật | |
| TC-61b | **Gate không nằm trong danh mục** — chặn bằng cấu tạo, không bằng lời dặn | |
| TC-61c | Lệnh chạm thiết bị / cài đặt / phong hạng đều ngoài danh mục | |
| TC-61d | Từ chối kèm LÝ DO và kèm lệnh cụ thể để người tự chạy | |
| TC-61e | Có trần số bước; chạm trần thì dừng và nói ra | |
| TC-61f | Mỗi lượt vẫn là một lời gọi STATELESS; ngữ cảnh do engine dựng lại | |
| TC-61g | Toàn bộ lượt hỏi ghi ra chat_log.jsonl | |

TC-61b là lý do cả tệp test này tồn tại. Một tầng hội thoại là đúng loại thứ
có thể phá bất biến trung tâm của sản phẩm một cách êm ái: mô hình "hiểu" rằng
người dùng muốn duyệt, rồi tự gọi ``gate approve``. Phép kiểm ở đây không hỏi
"mô hình có ngoan không" — nó hỏi **có tồn tại đường nào để gọi lệnh ấy
không**, và câu trả lời phải là không, bất kể mô hình trả về gì.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.agent import (
    MAX_STEPS,
    NGOAI_DANH_MUC,
    TOOLBOX,
    AgentError,
    AgentLoop,
    Tool,
    tool_for,
)

REPO = Path(__file__).resolve().parent.parent


class _LlmKichBan:
    """Mô hình giả: trả lần lượt các hành động đã dựng sẵn."""

    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, *hanh_dong: dict) -> None:
        self.hanh_dong = list(hanh_dong)
        self.prompts: list = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt) -> str:
        self.prompts.append(prompt)
        i = min(len(self.prompts) - 1, len(self.hanh_dong) - 1)
        return "```json\n" + json.dumps(self.hanh_dong[i], ensure_ascii=False) + "\n```"


def _vong(tmp_path: Path, llm, **kw) -> AgentLoop:
    da_chay: list[list[str]] = []

    def _runner(argv):
        da_chay.append(list(argv))
        return 0, f"(đầu ra giả của: {' '.join(argv)})"

    vong = AgentLoop(llm=llm, project=tmp_path, runner=kw.pop("runner", _runner), **kw)
    vong.da_chay = da_chay  # type: ignore[attr-defined]
    return vong


# --------------------------------------------------------------------------
# TC-61a — chạy lệnh rồi trả lời từ kết quả thật
# --------------------------------------------------------------------------


def test_agent_chay_lenh_roi_tra_loi(tmp_path: Path) -> None:
    llm = _LlmKichBan(
        {"suy_nghi": "cần xem ngân sách", "hanh_dong": "chay_lenh", "lenh": ["budget", "show"]},
        {"hanh_dong": "tra_loi", "noi_dung": "Ngân sách còn rộng."},
    )
    vong = _vong(tmp_path, llm)
    ket = vong.ask("ngân sách thế nào?")

    assert ket.commands_run == ["budget show"]
    assert ket.answer == "Ngân sách còn rộng."
    assert not ket.hit_limit


def test_ket_qua_lenh_duoc_dua_lai_cho_mo_hinh(tmp_path: Path) -> None:
    """Nếu không đưa lại thì mô hình chỉ đang đoán, và luật 1 của prompt vô nghĩa."""
    llm = _LlmKichBan(
        {"hanh_dong": "chay_lenh", "lenh": ["status"]},
        {"hanh_dong": "tra_loi", "noi_dung": "xong"},
    )
    _vong(tmp_path, llm).ask("dự án sao rồi?")

    lop_lan_hai = {l.name: l.content for l in llm.prompts[1].layers}
    assert "observations" in lop_lan_hai
    assert "đầu ra giả của: status" in lop_lan_hai["observations"]


def test_hoi_lai_khi_thieu_du_kien(tmp_path: Path) -> None:
    llm = _LlmKichBan({"hanh_dong": "hoi_lai", "noi_dung": "Bạn muốn xem module nào?"})
    ket = _vong(tmp_path, llm).ask("xem giúp mình")

    assert ket.clarifying == "Bạn muốn xem module nào?"
    assert not ket.commands_run


# --------------------------------------------------------------------------
# TC-61b, TC-61c — hàng rào là DANH MỤC, không phải lời dặn
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["gate", "approve", "G1"],
        ["gate", "approve", "G3"],
        ["gate", "reject", "G3"],
        ["flash"],
        ["flash", "--image", "x.hex"],
        # 'doctor --fix' KHÔNG còn ở đây — xem test_doctor_fix_duoc_phep_vi_sao
        # ngay dưới. Thay chỗ nó là lệnh duyệt, vì đó mới là chỗ có quyền.
        ["doctor", "approve", "avr-gcc"],
        ["tune", "drv_x"],
        ["rollback", "drv_x"],
        ["endurance"],
        ["build"],
        ["gen", "drv_x"],
        ["init", "--force"],
        ["telemetry"],
        ["ports"],
        ["scope-image", "a.png"],
        ["datasheet", "add", "a.pdf"],
        ["docs", "regen"],
    ],
)
def test_lenh_nguy_hiem_khong_co_trong_danh_muc(argv: list[str]) -> None:
    """Phép kiểm không hỏi 'mô hình có ngoan không' mà hỏi 'có đường nào không'."""
    assert tool_for(argv) is None, f"{' '.join(argv)} KHÔNG được nằm trong danh mục"


def test_doctor_fix_duoc_phep_vi_sao() -> None:
    """`doctor --fix` rời khỏi danh sách cấm — và lý do phải nói cho ra lẽ.

    Nó từng bị cấm vì nó cài phần mềm. Giờ nó KHÔNG cài được gì mà thiếu một
    quyết định của người neo vào đúng dãy đối số sắp chạy (SL-110). Quyền nằm
    ở `doctor approve`, và lệnh ấy vẫn ngoài danh mục.

    Cùng hình dạng với cặp `tool approve` (người) / `tool run` (Agent): Agent
    mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ.
    """
    assert tool_for(["doctor"]) is not None, "quét là chỉ đọc"
    assert tool_for(["doctor", "--fix"]) is not None
    assert tool_for(["doctor", "approve", "avr-gcc"]) is None, \
        "duyệt là quyền, và quyền thì không vào danh mục"


def test_gate_show_van_duoc_phep() -> None:
    """Trình hồ sơ là việc của Agent; QUYẾT ĐỊNH mới là việc của người."""
    assert tool_for(["gate", "show", "G3"]) is not None
    assert tool_for(["gate", "approve", "G3"]) is None


def test_mo_hinh_doi_goi_gate_thi_vong_lap_TU_CHOI(tmp_path: Path) -> None:
    """Kể cả khi mô hình cố tình gọi, vòng lặp không thực thi."""
    llm = _LlmKichBan(
        {"hanh_dong": "chay_lenh", "lenh": ["gate", "approve", "G1"]},
        {"hanh_dong": "tra_loi", "noi_dung": "thôi vậy"},
    )
    vong = _vong(tmp_path, llm)
    ket = vong.ask("duyệt G1 hộ mình")

    assert vong.da_chay == [], "không lệnh nào được thực thi"
    assert ket.commands_run == []
    assert any(s.refused for s in ket.steps)


def test_ly_do_tu_choi_noi_duoc_vi_sao(tmp_path: Path) -> None:
    llm = _LlmKichBan(
        {"hanh_dong": "chay_lenh", "lenh": ["flash"]},
        {"hanh_dong": "tra_loi", "noi_dung": "ok"},
    )
    ket = _vong(tmp_path, llm).ask("nạp firmware đi")
    tu_choi = next(s.refused for s in ket.steps if s.refused)

    assert "thiết bị thật" in tu_choi
    assert "xác nhận" in tu_choi


def test_lenh_bia_ra_cung_bi_tu_choi(tmp_path: Path) -> None:
    llm = _LlmKichBan(
        {"hanh_dong": "chay_lenh", "lenh": ["xoa-het-du-lieu"]},
        {"hanh_dong": "tra_loi", "noi_dung": "ok"},
    )
    vong = _vong(tmp_path, llm)
    ket = vong.ask("dọn dẹp giúp mình")

    assert vong.da_chay == []
    assert "không có trong danh mục" in next(s.refused for s in ket.steps if s.refused)


def test_moi_lenh_ngoai_danh_muc_deu_co_ly_do_viet_san() -> None:
    """Một lời từ chối trống rỗng bắt người đi tra tài liệu."""
    for verb, ly_do in NGOAI_DANH_MUC.items():
        assert ly_do.strip(), f"{verb} chưa có lý do từ chối"
        assert len(ly_do) > 40, f"lý do của {verb} quá ngắn để nói được gì"


def test_danh_muc_cong_bo_dung_thu_no_co() -> None:
    """Bảng gửi cho mô hình không được mâu thuẫn với chính danh mục."""
    from eaa.agent import _mo_ta_danh_muc

    van_ban = _mo_ta_danh_muc()
    co_mat = {t.argv[0] for t in TOOLBOX}
    phan_khong_co = van_ban.split("Đặc biệt KHÔNG có:")[1]

    for verb in co_mat:
        assert f" {verb}," not in phan_khong_co, (
            f"{verb} vừa có trong danh mục vừa bị công bố là không có"
        )


# --------------------------------------------------------------------------
# TC-61d — từ chối kèm lệnh cụ thể cho người
# --------------------------------------------------------------------------


def test_de_nghi_nguoi_chay_mot_lenh(tmp_path: Path) -> None:
    llm = _LlmKichBan(
        {
            "hanh_dong": "de_nghi_nguoi_chay",
            "lenh": ["gate", "approve", "G1"],
            "noi_dung": "Duyệt gate là việc của bạn.",
        }
    )
    ket = _vong(tmp_path, llm).ask("duyệt G1 đi")

    assert ket.suggested == ["gate approve G1"]
    assert "eaa gate approve G1" in ket.render()


def test_de_nghi_nhieu_lenh_mot_luc(tmp_path: Path) -> None:
    """Người hỏi thường cần một chuỗi vài bước, không phải một lệnh."""
    llm = _LlmKichBan(
        {
            "hanh_dong": "de_nghi_nguoi_chay",
            "lenh": [["gate", "approve", "G1"], ["gate", "approve", "G2"]],
            "noi_dung": "Hai gate này bạn tự duyệt.",
        }
    )
    ket = _vong(tmp_path, llm).ask("mở đường cho mình sinh mã")

    assert ket.suggested == ["gate approve G1", "gate approve G2"]


# --------------------------------------------------------------------------
# TC-61e — trần số bước
# --------------------------------------------------------------------------


def test_cham_tran_thi_dung_va_noi_ra(tmp_path: Path) -> None:
    """Một vòng lặp không có trần là vòng lặp quay tới lúc hết tiền."""
    llm = _LlmKichBan({"hanh_dong": "chay_lenh", "lenh": ["status"]})
    vong = _vong(tmp_path, llm, max_steps=3)
    ket = vong.ask("kể mọi thứ cho tôi")

    assert ket.hit_limit
    assert len(vong.da_chay) == 3
    assert "chạm trần 3 bước" in ket.render() or "chạm trần" in ket.render()


def test_tran_mac_dinh_la_mot_con_so_co_that() -> None:
    assert 1 <= MAX_STEPS <= 20


def test_hanh_dong_khong_hop_le_khong_lam_dut_vong(tmp_path: Path) -> None:
    llm = _LlmKichBan(
        {"hanh_dong": "nhay_mua"},
        {"hanh_dong": "tra_loi", "noi_dung": "xin lỗi"},
    )
    ket = _vong(tmp_path, llm).ask("thử xem")
    assert ket.answer == "xin lỗi"


# --------------------------------------------------------------------------
# TC-61f — vẫn stateless; ngữ cảnh do engine dựng lại
# --------------------------------------------------------------------------


def test_moi_luot_la_mot_loi_goi_doc_lap(tmp_path: Path) -> None:
    """Không có trạng thái nào nằm ở phía nhà cung cấp mô hình."""
    llm = _LlmKichBan({"hanh_dong": "tra_loi", "noi_dung": "rồi"})
    vong = _vong(tmp_path, llm)
    vong.ask("câu một")
    vong.ask("câu hai")

    # Hai prompt độc lập, mỗi cái tự mang đủ ngữ cảnh của nó.
    assert len(llm.prompts) == 2
    for p in llm.prompts:
        assert p.system_instruction, "mỗi lượt phải tự mang vai trò và luật"
        assert any(l.name == "toolbox" for l in p.layers)


def test_ban_ghi_phien_do_engine_dung_lai(tmp_path: Path) -> None:
    llm = _LlmKichBan({"hanh_dong": "tra_loi", "noi_dung": "đã xem xong"})
    vong = _vong(tmp_path, llm)
    vong.ask("ngân sách thế nào?")
    vong.ask("còn tài liệu thì sao?")

    lop = {l.name: l.content for l in llm.prompts[1].layers}
    assert "history" in lop
    assert "ngân sách thế nào?" in lop["history"]


def test_ngan_sach_ngu_canh_duoc_kiem_truoc_khi_goi(tmp_path: Path) -> None:
    """Cùng luật với vòng sinh mã: đếm token TRƯỚC, không phải sau."""

    class _LlmDemThat(_LlmKichBan):
        def complete(self, prompt):
            prompt.check_budget(self.count_tokens)
            return super().complete(prompt)

    llm = _LlmDemThat({"hanh_dong": "tra_loi", "noi_dung": "ok"})
    ket = _vong(tmp_path, llm).ask("hỏi ngắn")
    assert ket.answer == "ok"


# --------------------------------------------------------------------------
# TC-61g — ghi vết
# --------------------------------------------------------------------------


def test_moi_luot_duoc_ghi_ra_nhat_ky(tmp_path: Path) -> None:
    from eaa.agent import CHAT_LOG

    llm = _LlmKichBan(
        {"hanh_dong": "chay_lenh", "lenh": ["budget", "show"]},
        {"hanh_dong": "tra_loi", "noi_dung": "xong"},
    )
    _vong(tmp_path, llm).ask("ngân sách?")

    dong = (tmp_path / CHAT_LOG).read_text(encoding="utf-8").strip().splitlines()
    assert len(dong) == 1
    ban_ghi = json.loads(dong[0])
    assert ban_ghi["question"] == "ngân sách?"
    assert ban_ghi["commands_run"] == ["budget show"]
    assert ban_ghi["steps"][0]["argv"] == ["budget", "show"]


def test_cau_hoi_rong_bi_tu_choi(tmp_path: Path) -> None:
    with pytest.raises(AgentError, match="rỗng"):
        _vong(tmp_path, _LlmKichBan({"hanh_dong": "tra_loi"})).ask("   ")


# --------------------------------------------------------------------------
# Danh mục là DỮ LIỆU — đọc được, kiểm được
# --------------------------------------------------------------------------


def test_moi_cong_cu_deu_noi_duoc_no_dung_de_lam_gi() -> None:
    for t in TOOLBOX:
        assert t.purpose.strip(), f"{t.name} chưa nói dùng để làm gì"
        assert not t.name.startswith("-")


def test_khop_lenh_uu_tien_ban_dai_nhat() -> None:
    """'plan add' phải khớp Tool('plan','add'), không khớp nhầm Tool('plan','list')."""
    assert tool_for(["plan", "add", "x"]).argv == ("plan", "add")
    assert tool_for(["plan", "list"]).argv == ("plan", "list")


def test_khong_cong_cu_nao_ghi_ma_khong_duoc_danh_dau() -> None:
    """Cột 'writes' để nói cho người biết, nên nó phải đúng."""
    ghi = {t.name for t in TOOLBOX if t.writes}
    assert "plan add" in ghi
    assert "interface" in ghi
    assert "status" not in ghi


# ═══════════ TC-61f — gợi ý lệnh ngoài eaa không bị gắn tiền tố ═══════════


def test_lenh_cua_eaa_duoc_gan_tien_to():
    from eaa.agent import _dong_lenh

    assert _dong_lenh("gate approve G1") == "eaa gate approve G1"
    assert _dong_lenh("flash --module drv_i2c") == "eaa flash --module drv_i2c"


def test_lenh_he_dieu_hanh_KHONG_bi_gan_tien_to():
    """'eaa brew install ...' là một lệnh không tồn tại.

    Người dùng gõ theo, nhận lỗi, và mất lòng tin vào cả câu trả lời đúng nằm
    ngay phía trên nó.
    """
    from eaa.agent import _dong_lenh

    assert _dong_lenh("brew install avr-gcc") == "brew install avr-gcc"
    assert _dong_lenh("sudo apt-get install -y gcc-avr") == "sudo apt-get install -y gcc-avr"
    assert _dong_lenh("export EAA_LLM_KEY=...") == "export EAA_LLM_KEY=..."


def test_lenh_da_co_tien_to_khong_bi_gan_hai_lan():
    from eaa.agent import _dong_lenh

    assert _dong_lenh("eaa gate approve G1") == "eaa gate approve G1"


def test_lenh_rong_khong_lam_sap():
    from eaa.agent import _dong_lenh

    assert _dong_lenh("   ") == ""


def test_ket_qua_in_ra_dung_ca_hai_loai():
    from eaa.agent import ChatResult

    kq = ChatResult(question="q", answer="xong",
                    suggested=["brew install cppcheck", "doctor --fix"])
    ra = kq.render()
    assert "    brew install cppcheck" in ra
    assert "    eaa doctor --fix" in ra


# ═══ TC-61g — lệnh Agent chạy phải mang theo dự án đang làm việc ═══


def test_lenh_agent_chay_gan_san_du_an(tmp_path):
    """Kho nhiều dự án thì lệnh con không tự chọn được — Agent nhận mã 4.

    Lỗi này chỉ hiện ra khi có hơn một dự án, nên nó đi lọt qua mọi bài test
    dùng đúng một dự án. Đo được ở lần chạy live đầu tiên.
    """
    from eaa.agent import AgentLoop

    da_chay = []

    def bat(argv):
        da_chay.append(list(argv))
        return 0, "ok"

    import eaa.agent as m

    goc = m._chay_cli
    m._chay_cli = bat
    try:
        vong = AgentLoop(project=tmp_path / "du_an_a", llm=None)
        vong.runner(["status"])
        vong.runner(["plan", "list"])
    finally:
        m._chay_cli = goc

    assert da_chay[0] == ["--project", str(tmp_path / "du_an_a"), "status"]
    assert da_chay[1] == ["--project", str(tmp_path / "du_an_a"), "plan", "list"]


def test_runner_tiem_vao_thi_khong_bi_ghi_de(tmp_path):
    """Bài test thay runner để kiểm vòng lặp mà không chạm hệ thống tệp."""
    from eaa.agent import AgentLoop

    rieng = lambda argv: (0, "gia")
    assert AgentLoop(project=tmp_path, llm=None, runner=rieng).runner is rieng
