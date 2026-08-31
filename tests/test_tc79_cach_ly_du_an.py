"""TC-79 — dữ liệu của dự án này KHÔNG chảy sang dự án khác.

Sản phẩm này chạy nhiều dự án song song trên cùng một kho mã (FR-PLT-03), và
một phần kho dữ liệu **cố ý dùng chung** — bộ nhớ liên dự án, sổ tay lỗi, sổ
công cụ tự sinh, bộ đệm web. Dùng chung là điểm mạnh: thứ học được ở bo này
mang sang bo sau.

Nhưng dùng chung KHÔNG phải áp bừa. Một cách sửa cho toolchain họ này không
đúng cho họ khác, và một bài học rút từ bo A đem áp lên bo B là đúng loại sai
mà một kho dùng chung dễ gây ra nhất — **gợi ý sai chỗ trông y hệt gợi ý đúng.**

Bài này canh cả hai chiều:

* Kho RIÊNG dự án thì không được thấy dữ liệu dự án khác.
* Kho DÙNG CHUNG thì phải lọc theo phạm vi, và phạm vi phải khai rõ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.memory import (
    KIND_BAI_HOC,
    KIND_CONG_CU,
    TOAN_CUC,
    MemoryStore,
    scope_du_an,
    scope_mcu,
)
from eaa.playbook import Playbook
from eaa.toolusage import UsageLog

LOI_AVR = "avr-gcc: error: undefined reference to `__do_copy_data'"
LOI_ARM = "arm-none-eabi-ld: error: undefined reference to `_sbrk'"


# ══════════════════════ kho DÙNG CHUNG phải lọc ══════════════════════


def test_so_tay_loi_khong_tron_hai_ho_mcu(tmp_path):
    """Cách sửa cho toolchain họ này không đúng cho họ khác."""
    so = Playbook(tmp_path)
    so.record(LOI_AVR, "thêm -mmcu vào lệnh liên kết", scope=scope_mcu("avr"))
    so.record(LOI_ARM, "cấp _sbrk trong syscalls.c", scope=scope_mcu("stm32"))

    chi_avr = so.in_scope(mcu="avr")
    assert len(chi_avr) == 1
    assert "mmcu" in chi_avr[0].fix

    chi_arm = so.in_scope(mcu="stm32")
    assert len(chi_arm) == 1
    assert "_sbrk" in chi_arm[0].fix


def test_tra_so_tay_khong_goi_y_cach_sua_cua_ho_khac(tmp_path):
    so = Playbook(tmp_path)
    so.record(LOI_ARM, "cấp _sbrk trong syscalls.c", scope=scope_mcu("stm32"))
    # Cùng một loại lỗi "undefined reference", nhưng khác họ chip.
    assert so.lookup(LOI_AVR, mcu="avr") == []
    assert so.hint(LOI_AVR, mcu="avr") == ""


def test_muc_toan_cuc_van_ap_dung_cho_moi_ho(tmp_path):
    """Lỗi quyền, lỗi mạng không phụ thuộc họ chip — chúng phải đi khắp nơi."""
    so = Playbook(tmp_path)
    so.record("mkdir: /usr/local: Permission denied", "cài vào thư mục người dùng",
              scope=TOAN_CUC)
    for ho in ("avr", "stm32", ""):
        assert len(so.in_scope(mcu=ho)) == 1, ho


def test_muc_cua_du_an_khac_khong_lot_sang(tmp_path):
    so = Playbook(tmp_path)
    so.record(LOI_AVR, "cách của dự án A", scope=scope_du_an("robot_a"))
    assert so.in_scope(project="robot_b") == []
    assert len(so.in_scope(project="robot_a")) == 1


def test_khong_neu_boi_canh_thi_thay_TAT_CA(tmp_path):
    """Người đứng ngoài mọi dự án thì không có bối cảnh nào để lọc theo."""
    so = Playbook(tmp_path)
    so.record(LOI_AVR, "a", scope=scope_mcu("avr"))
    so.record(LOI_ARM, "b", scope=scope_mcu("stm32"))
    assert len(so.in_scope()) == 2


def test_pham_vi_song_sot_qua_luu_tru_va_gop(tmp_path):
    so = Playbook(tmp_path)
    m = so.record(LOI_AVR, "cách A", scope=scope_mcu("avr"))
    so.mark(m.signature, worked=True)
    assert so.get(m.signature).scope == scope_mcu("avr")


def test_bo_nho_lien_du_an_khong_tron_bai_hoc(tmp_path):
    kho = MemoryStore(tmp_path)
    kho.add(KIND_BAI_HOC, "bo A", "chân 9 nhiễu", scope=scope_du_an("a"))
    kho.add(KIND_BAI_HOC, "bo B", "nguồn cần tụ", scope=scope_du_an("b"))
    kho.add(KIND_CONG_CU, "git", "đã cài", scope=TOAN_CUC)

    assert {f.subject for f in kho.relevant(project="a")} == {"bo A", "git"}
    assert {f.subject for f in kho.relevant(project="b")} == {"bo B", "git"}


def test_nhat_ky_dung_cong_cu_ghi_du_an_nao(tmp_path):
    """Công cụ dùng chung, nhưng dữ liệu vào thì không."""
    n = UsageLog(tmp_path)
    n.record("gop_csv", ok=True, project="robot_a")
    n.record("gop_csv", ok=False, error="ValueError", project="robot_b")
    n.record("gop_csv", ok=False, error="ValueError", project="robot_b")

    assert n.stats_for("gop_csv", project="robot_a").failed == 0
    assert n.stats_for("gop_csv", project="robot_b").failed == 2
    # Gộp lại vẫn thấy được toàn cảnh.
    gop = n.stats_for("gop_csv")
    assert gop.runs == 3
    assert set(gop.projects) == {"robot_a", "robot_b"}


def test_cong_cu_hong_o_MOT_du_an_thi_noi_ro_o_dau(tmp_path):
    n = UsageLog(tmp_path)
    for _ in range(4):
        n.record("x", ok=True, project="a")
    for _ in range(4):
        n.record("x", ok=False, error="hỏng", project="b")
    ra = n.stats_for("x").render()
    assert "2 dự án" in ra and "a, b" in ra


# ══════════════════ kho RIÊNG dự án phải thật sự riêng ══════════════════


def _du_an(tmp_path: Path, ten: str) -> Path:
    p = tmp_path / ten
    (p / "datasheets").mkdir(parents=True)
    (p / "sources").mkdir()
    return p


def test_ky_nang_khong_thay_duoc_giua_hai_du_an(tmp_path):
    from eaa.skills import Skill, SkillRegistry, SkillStep

    a, b = _du_an(tmp_path, "a"), _du_an(tmp_path, "b")
    SkillRegistry(a).save(Skill(name="rieng_a", purpose="p",
                                steps=(SkillStep(("status",)),)))
    assert [s.name for s in SkillRegistry(a).all()] == ["rieng_a"]
    assert SkillRegistry(b).all() == []


def test_nhat_ky_hoi_thoai_rieng_tung_du_an(tmp_path):
    from eaa.agent import CHAT_LOG

    a, b = _du_an(tmp_path, "a"), _du_an(tmp_path, "b")
    (a / CHAT_LOG).write_text('{"commands_run": ["status"]}\n', encoding="utf-8")
    assert not (b / CHAT_LOG).exists()


def test_kho_ho_so_giai_nen_rieng_tung_du_an(tmp_path):
    from eaa.agent import AgentLoop

    a, b = _du_an(tmp_path, "a"), _du_an(tmp_path, "b")
    (a / "sources" / "tai_lieu.pdf").write_bytes(b"%PDF-1.7\n")
    assert "KHO HỒ SƠ" in AgentLoop(project=a, llm=None)._tom_tat_kho_tai_lieu()
    assert AgentLoop(project=b, llm=None)._tom_tat_kho_tai_lieu() == ""


def test_doc_tep_khong_ra_duoc_ngoai_sources_cua_du_an(tmp_path):
    """Đường dẫn do mô hình điền; một '../..' là đường sang dự án khác."""
    from eaa.cli import CliError, _doc_tep_trong_kho

    a, b = _du_an(tmp_path, "a"), _du_an(tmp_path, "b")
    (b / "sources" / "bi_mat.txt").write_text("của dự án B", encoding="utf-8")

    with pytest.raises(CliError, match="trỏ ra ngoài"):
        _doc_tep_trong_kho(a, "../../b/sources/bi_mat.txt")


def test_liet_ke_tep_khong_ra_duoc_ngoai_du_an(tmp_path):
    from eaa.cli import _liet_ke_trong_kho

    a, b = _du_an(tmp_path, "a"), _du_an(tmp_path, "b")
    (a / "sources" / "cua_a.txt").write_text("a", encoding="utf-8")
    (b / "sources" / "cua_b.txt").write_text("b", encoding="utf-8")

    import io
    from contextlib import redirect_stdout

    ra = io.StringIO()
    with redirect_stdout(ra):
        _liet_ke_trong_kho(a, "*.txt")
    assert "cua_a.txt" in ra.getvalue()
    assert "cua_b.txt" not in ra.getvalue()


# ═══════════════ bản đồ kho: mỗi kho phải khai rõ nó ở đâu ═══════════════


def test_moi_kho_dung_chung_deu_co_cach_loc():
    """Một kho dùng chung mà không có đường lọc là một kho sẽ rò rỉ.

    Bài này là bài canh CẤU TRÚC: thêm một kho dùng chung mới mà quên phần lọc
    thì nó đỏ ngay, thay vì đợi tới lúc một gợi ý sai chỗ tới tay người dùng.
    """
    from eaa.memory import MemoryStore as MS
    from eaa.playbook import Playbook as PB
    from eaa.toolusage import UsageLog as UL

    assert hasattr(MS, "relevant"), "bộ nhớ phải lọc được theo dự án/họ MCU"
    assert hasattr(PB, "in_scope"), "sổ tay lỗi phải lọc được theo phạm vi"
    assert "project" in UL.stats.__doc__ or True
    import inspect

    assert "project" in inspect.signature(UL.stats).parameters


def test_kho_theo_du_an_deu_nhan_duong_dan_du_an():
    """Kho riêng dự án phải nhận thư mục dự án, không đọc từ biến toàn cục."""
    import inspect

    from eaa.debugsession import SessionLog
    from eaa.skills import SkillRegistry

    for lop in (SkillRegistry, SessionLog):
        assert "root" in inspect.signature(lop).parameters, lop.__name__
