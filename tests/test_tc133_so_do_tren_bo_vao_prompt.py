"""TC-133 — số đo trên bo phải chảy ngược vào prompt (N-913).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-173.

Trước SL-173, bài học từ bo thật chỉ tới được mô hình qua **lý do từ chối kỹ sư
gõ tay** ở G3 — mất một lần gõ là mất hẳn. Ba chỗ giữ số đo (`measurements.jsonl`,
`flash_log.jsonl`, `hardware_profile.yaml`) đều không có đường nào chạm tới bộ
ghép prompt.

Hệ quả đo được: mốc gia tốc `-535` phải một người đo bằng DS-02 rồi tự tay chép
vào hồ sơ phần cứng; tốc độ bootloader `57600` phải một người phát hiện rồi tự
nhớ. Lượt sinh mã kế tiếp không biết gì về cả hai.

Ba luật bài này canh
---------------------

1. **Append-only + supersede** — duyệt là GHI THÊM, không sửa bản cũ. Số đo cũ
   là dữ liệu của chương đánh giá: hôm ấy bo đọc ra thế.
2. **Chỉ số đo ĐÃ DUYỆT mới vào prompt.** Agent đề xuất, người chốt.
3. **Số đo thắng tài liệu khi hai bên lệch**, và lớp prompt nói thẳng câu ấy —
   ở đúng chỗ hai bên gặp nhau, không phải ở một lời dặn chung cuối prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa import EXIT_OK
from eaa.cli import MEASURED_FILE, main
from eaa.measured import DA_DUYET, DE_XUAT, MeasuredError, MeasuredStore, lop_so_do
from tests.test_cli_e2e import dung_moi_truong


@pytest.fixture()
def so(tmp_path: Path) -> MeasuredStore:
    return MeasuredStore(tmp_path / "board_facts.jsonl")


# ── sổ: append-only + supersede ──────────────────────────────────────────────


def test_de_xuat_khong_phai_da_duyet(so: MeasuredStore) -> None:
    so.propose("ACCEL_OFFSET", "-535", unit="LSB", source="DS-02")
    assert so.active() == []
    assert [f.name for f in so.pending()] == ["ACCEL_OFFSET"]


def test_duyet_la_GHI_THEM_chu_khong_sua_ban_cu(so: MeasuredStore) -> None:
    """Số đo cũ là dữ liệu của chương đánh giá — không ai được viết lại."""
    so.propose("BOOTLOADER_BAUD", "57600", source="đo trên bo")
    so.approve("BOOTLOADER_BAUD", actor="Vũ Trí Công")

    tat_ca = so.all()
    assert len(tat_ca) == 2, "duyệt phải là bản ghi thứ hai, không phải sửa bản đầu"
    assert tat_ca[0].status == DE_XUAT
    assert tat_ca[1].status == DA_DUYET
    assert tat_ca[0].measured_at == tat_ca[1].measured_at


def test_ban_duyet_sau_thang_ban_duyet_truoc(so: MeasuredStore) -> None:
    """Đo lại cho số khác thì bản sau thắng — theo THỨ TỰ GHI, không theo mốc."""
    so.propose("GYRO_DRIFT", "1.2", unit="°/s")
    so.approve("GYRO_DRIFT", actor="A")
    so.propose("GYRO_DRIFT", "0.8", unit="°/s")
    so.approve("GYRO_DRIFT", actor="B")

    hieu_luc = so.active()
    assert len(hieu_luc) == 1
    assert hieu_luc[0].value == "0.8"
    assert hieu_luc[0].approved_by == "B"
    # Và bản cũ vẫn còn nguyên trong sổ.
    assert [f.value for f in so.all()] == ["1.2", "1.2", "0.8", "0.8"]


def test_duyet_hai_lan_bi_tu_choi(so: MeasuredStore) -> None:
    so.propose("X", "1")
    so.approve("X", actor="A")
    with pytest.raises(MeasuredError, match="đã được duyệt"):
        so.approve("X", actor="B")


def test_duyet_so_chua_co_trong_so_bi_tu_choi(so: MeasuredStore) -> None:
    with pytest.raises(MeasuredError, match="Chưa có số đo"):
        so.approve("KHONG_CO", actor="A")


def test_duyet_KHONG_TEN_NGUOI_bi_tu_choi(so: MeasuredStore) -> None:
    """Một quyết định không gắn tên là một quyết định không ai chịu trách nhiệm."""
    so.propose("X", "1")
    with pytest.raises(MeasuredError, match="tên người duyệt"):
        so.approve("X", actor="   ")


def test_so_do_thieu_ten_hoac_gia_tri_bi_tu_choi(so: MeasuredStore) -> None:
    with pytest.raises(MeasuredError):
        so.propose("  ", "5")
    with pytest.raises(MeasuredError):
        so.propose("X", "  ")


def test_so_rong_thi_khong_no(so: MeasuredStore) -> None:
    assert so.all() == [] and so.active() == [] and so.pending() == []


# ── lớp K8 ───────────────────────────────────────────────────────────────────


def test_lop_rong_khi_chua_co_so_do_nao() -> None:
    """Một lớp nói 'chưa có gì' chỉ tốn token mà không đổi việc mô hình làm."""
    assert lop_so_do([]) == ""


def test_lop_noi_thang_SO_DO_THANG_TAI_LIEU(so: MeasuredStore) -> None:
    so.propose("ACCEL_OFFSET", "-535", unit="LSB", source="DS-02")
    so.approve("ACCEL_OFFSET", actor="A")
    van = lop_so_do(so.active())

    assert "SỐ ĐO THẮNG" in van
    assert "ĐÃ KIỂM" in van


def test_lop_mang_XUAT_XU_du_de_di_kiem_lai(so: MeasuredStore) -> None:
    """Một con số không có xuất xứ thì lần sau không ai đo lại được nó."""
    so.propose("ACCEL_OFFSET", "-535", unit="LSB", source="DS-02", note="dải ±4g")
    so.approve("ACCEL_OFFSET", actor="A")
    van = lop_so_do(so.active())

    assert "-535" in van and "LSB" in van
    assert "DS-02" in van
    assert "dải ±4g" in van


# ── ngân sách ────────────────────────────────────────────────────────────────


def test_them_lop_KHONG_pha_tran_tong() -> None:
    """Dời, không nới: tổng phần các lớp vẫn đúng 8.000."""
    from eaa.llm.base import LAYER_BUDGETS, TOTAL_BUDGET

    assert sum(LAYER_BUDGETS.values()) == TOTAL_BUDGET == 8_000
    assert LAYER_BUDGETS["board_facts"] > 0


def test_lay_ngan_sach_tu_lop_repair_chu_khong_tu_lop_khac() -> None:
    """`repair` là SÀN chứ không phải trần (SL-147) — số danh nghĩa là sổ sách.

    Lấy của lớp khác thì mới thật sự bóp lớp ấy; lấy của `repair` thì không,
    và bài này giữ cho lần sửa sau không lặng lẽ đổi chỗ lấy.
    """
    from eaa.llm.base import LAYER_BUDGETS

    assert LAYER_BUDGETS["repair"] == 1_500
    assert LAYER_BUDGETS["datasheet_chunks"] == 1_500
    assert LAYER_BUDGETS["project_rules"] == 1_200
    assert LAYER_BUDGETS["hardware_facts"] == 400


# ── nối vào bộ ghép prompt, qua CLI thật ─────────────────────────────────────


@pytest.fixture()
def du_an(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> Path:
    project = dung_moi_truong(tmp_path, monkeypatch)
    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    capsys.readouterr()
    return project


def _lop_board_facts(project: Path) -> str:
    from eaa.cli import build_context
    from eaa.composer import Task

    ctx = build_context(project)
    muc = ctx.store.load().backlog[0]
    task = Task(
        module_id=muc.id,
        goal="Sinh module",
        uses=list(muc.uses),
        depends_on=list(muc.depends_on),
        acceptance=[],
    )
    lop = next(
        (l for l in ctx.composer.build(task).layers if l.name == "board_facts"), None
    )
    return lop.content if lop else ""


def test_so_do_CHO_DUYET_khong_vao_prompt(du_an: Path, capsys) -> None:
    """Số máy tự đo rồi tự tin là đúng sẽ đi thẳng vào mã của mọi module sau."""
    main(["measured", "add", "ACCEL_OFFSET", "-535", "--unit", "LSB", "--source", "DS-02"])
    capsys.readouterr()
    assert "ACCEL_OFFSET" not in _lop_board_facts(du_an)


def test_so_do_DA_DUYET_vao_prompt(du_an: Path, capsys) -> None:
    main(["measured", "add", "ACCEL_OFFSET", "-535", "--unit", "LSB", "--source", "DS-02"])
    assert main(["measured", "approve", "ACCEL_OFFSET", "--actor", "Kỹ sư"]) == EXIT_OK
    capsys.readouterr()

    van = _lop_board_facts(du_an)
    assert "ACCEL_OFFSET" in van and "-535" in van
    assert "SỐ ĐO THẮNG" in van


def test_lop_dung_TRUOC_lop_trich_doan_tai_lieu(du_an: Path, capsys) -> None:
    """Đặt sau thì mô hình đã đọc xong tài liệu và đã tin tài liệu."""
    from eaa.cli import build_context
    from eaa.composer import Task

    main(["measured", "add", "X", "1"])
    main(["measured", "approve", "X", "--actor", "Kỹ sư"])
    capsys.readouterr()

    ctx = build_context(du_an)
    muc = ctx.store.load().backlog[0]
    ten = [
        l.name
        for l in ctx.composer.build(
            Task(module_id=muc.id, goal="g", uses=list(muc.uses), acceptance=[])
        ).layers
    ]
    assert ten.index("board_facts") < ten.index("datasheet_chunks")


def test_chua_noi_so_thi_moi_thu_chay_y_nhu_truoc(du_an: Path, capsys) -> None:
    """Nối sổ là việc của CLI, không phải điều kiện để composer chạy được."""
    from eaa.composer import PromptComposer, Task
    from eaa.cli import build_context

    ctx = build_context(du_an)
    tay = PromptComposer(ctx.kb, ctx.graph, ctx.ledger)
    assert tay.measured is None
    muc = ctx.store.load().backlog[0]
    p = tay.build(Task(module_id=muc.id, goal="g", uses=list(muc.uses), acceptance=[]))
    assert p.token_report().get("board_facts", 0) == 0


def test_so_hong_khong_lam_hong_luot_sinh(du_an: Path, capsys) -> None:
    """Một lớp phụ trợ không được quyền làm hỏng lượt sinh vì lý do của nó."""
    (du_an / MEASURED_FILE).write_text("{ đây không phải JSON\n", encoding="utf-8")
    assert _lop_board_facts(du_an) == ""


def test_list_noi_ro_cai_nao_VAO_prompt_cai_nao_khong(du_an: Path, capsys) -> None:
    main(["measured", "add", "A", "1"])
    main(["measured", "add", "B", "2"])
    main(["measured", "approve", "A", "--actor", "Kỹ sư"])
    capsys.readouterr()

    main(["measured", "list"])
    ra = capsys.readouterr().out
    assert "và chúng VÀO prompt" in ra
    assert "KHÔNG vào prompt" in ra


# ── ranh giới quyền ──────────────────────────────────────────────────────────


def test_agent_de_xuat_duoc_nhung_KHONG_duyet_duoc() -> None:
    """Lệnh DUYỆT không nằm trong danh mục Agent — cùng luật SL-164."""
    from eaa.agent import TOOLBOX

    argv = {" ".join(t.argv) for t in TOOLBOX}
    assert "measured list" in argv
    assert "measured add" in argv
    assert "measured approve" not in argv


def test_muc_de_xuat_khai_dung_la_CO_GHI() -> None:
    """Khai là chỉ đọc thì người đọc danh mục sẽ tưởng nó vô hại."""
    from eaa.agent import TOOLBOX

    assert next(t for t in TOOLBOX if t.argv == ("measured", "add")).writes is True
    assert next(t for t in TOOLBOX if t.argv == ("measured", "list")).writes is False
