"""TC-01, TC-02 — bất biến merge và Human Gate không thể vượt.

TC-01 (STP-04): "Gọi `eaa gen` khi G1 chưa duyệt; **thử mọi tổ hợp lệnh để
merge không qua G3** → bị từ chối trong mọi trường hợp; không tồn tại đường
vòng."

TC-02: "Reject diff tại G3 kèm lý do → không merge; lý do xuất hiện trong
error_ledger.jsonl và trong prompt lần sinh lại."

Mệnh đề "không tồn tại đường vòng" không chứng minh được bằng cách thử vài
trường hợp — thử bao nhiêu cũng chỉ là thử. Nên bộ test này tấn công từ ba
phía:

1.  **Hành vi** — mọi cách dựng giấy phép thiếu bằng chứng đều bị từ chối, kể
    cả những cách tinh vi: duyệt gate khác, duyệt rồi sửa mã, chỉ một cổng
    trong chuỗi chưa đạt.
2.  **Cấu trúc** — `merge()` không nhận thứ gì ngoài `MergeAuthorization`, và
    dựng được vật thể đó đồng nghĩa với đã thỏa bất biến.
3.  **Quét mã nguồn** — chứng minh trong toàn bộ engine chỉ có MỘT nơi gọi
    lệnh merge của Git và không nơi nào trong luồng tự động tự phê duyệt gate.
    Đây là phần trả lời trực tiếp cho chữ "không tồn tại" của TC-01, cùng kỹ
    thuật với TC-38.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from eaa.gates import (
    APPROVED,
    REJECTED,
    GateDecision,
    GateError,
    GateNotInteractive,
    GateNotPending,
    GatePayload,
    HumanGate,
)
from eaa.ledger import ErrorLedger
from eaa.tools.base import CodeArtifact, ToolError, ToolReport
from eaa.vcs import (
    MERGE_GATE,
    GitRepo,
    MergeAuthorization,
    MergeNotAuthorized,
    authorize_merge,
)

ENGINE = Path(__file__).resolve().parent.parent / "eaa"


# --------------------------------------------------------------------------
# Trợ giúp
# --------------------------------------------------------------------------


def _bao_cao_dat() -> list[ToolReport]:
    return [
        ToolReport(gate="compile", passed=True),
        ToolReport(gate="size", passed=True, metrics={"flash_pct": 31.2}),
        ToolReport(gate="static", passed=True),
        ToolReport(gate="unittests", passed=True),
    ]


def _quyet_dinh(digest: str, *, decision: str = APPROVED, gate: str = MERGE_GATE) -> GateDecision:
    return GateDecision(
        gate_id=gate,
        decision=decision,
        actor="Vũ Trí Công",
        decided_at="2026-08-29T10:00:00+00:00",
        payload_digest="sha256:payload",
        content_digest=digest,
        module="drv_bus_sensor",
        reason="" if decision == APPROVED else "thiếu kiểm mã trạng thái",
    )


@pytest.fixture()
def gate(tmp_path: Path) -> HumanGate:
    return HumanGate(tmp_path / "gates", ledger=ErrorLedger(tmp_path / "ledger.jsonl"))


@pytest.fixture()
def repo(tmp_path: Path) -> GitRepo:
    r = GitRepo(tmp_path / "firmware")
    r.init()
    return r


def _artifact(**ghi_de) -> CodeArtifact:
    mac_dinh = dict(
        files={"src/m.c": "void m_init(void)\n{\n    static int n;\n    n = 0;\n}\n"},
        prompt_hash="sha256:aaa",
        model="mock-deterministic-1",
        constraints_version="sha256:bbb",
        chunk_ids=["ds-021"],
    )
    mac_dinh.update(ghi_de)
    return CodeArtifact(**mac_dinh)


# --------------------------------------------------------------------------
# TC-01 phần 1 — giấy phép merge không dựng được khi thiếu bằng chứng
# --------------------------------------------------------------------------


def test_du_dieu_kien_thi_dung_duoc_giay_phep() -> None:
    giay_phep = authorize_merge(
        module_id="drv_bus_sensor",
        branch="feature/drv_bus_sensor",
        reports=_bao_cao_dat(),
        decision=_quyet_dinh("sha256:diff"),
        content_digest="sha256:diff",
    )
    assert giay_phep.gates_passed == ("compile", "size", "static", "unittests")
    assert "G3 duyệt bởi Vũ Trí Công" in giay_phep.summary()


def test_khong_co_bao_cao_cong_nao_thi_khong_merge_duoc() -> None:
    with pytest.raises(MergeNotAuthorized, match="Không có báo cáo"):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=[],
            decision=_quyet_dinh("sha256:d"),
            content_digest="sha256:d",
        )


@pytest.mark.parametrize("cong_hong", ["compile", "size", "static", "unittests"])
def test_chi_can_MOT_cong_chua_dat_la_khong_merge_duoc(cong_hong: str) -> None:
    """"TOÀN BỘ ToolReport.passed" — không phải "phần lớn"."""
    bao_cao = _bao_cao_dat()
    for i, r in enumerate(bao_cao):
        if r.gate == cong_hong:
            bao_cao[i] = ToolReport(
                gate=cong_hong, passed=False, errors=[ToolError("hỏng")]
            )

    with pytest.raises(MergeNotAuthorized, match=cong_hong):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=bao_cao,
            decision=_quyet_dinh("sha256:d"),
            content_digest="sha256:d",
        )


def test_chua_co_quyet_dinh_nao_tai_G3_thi_khong_merge_duoc() -> None:
    with pytest.raises(MergeNotAuthorized, match="Chưa có quyết định"):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=_bao_cao_dat(),
            decision=None,
            content_digest="sha256:d",
        )


def test_G3_tu_choi_thi_khong_merge_duoc() -> None:
    with pytest.raises(MergeNotAuthorized, match="rejected"):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=_bao_cao_dat(),
            decision=_quyet_dinh("sha256:d", decision=REJECTED),
            content_digest="sha256:d",
        )


@pytest.mark.parametrize("gate_khac", ["G1", "G2", "G4", "G5"])
def test_duyet_mot_gate_KHAC_khong_mo_duoc_merge(gate_khac: str) -> None:
    """Đường vòng hiển nhiên nhất: dùng chữ ký của gate dễ hơn."""
    with pytest.raises(MergeNotAuthorized, match="cần quyết định tại G3"):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=_bao_cao_dat(),
            decision=_quyet_dinh("sha256:d", gate=gate_khac),
            content_digest="sha256:d",
        )


def test_duyet_ban_nay_roi_merge_ban_khac_bi_chan() -> None:
    """Khe hở mà điều kiện nguyên văn của SDD chưa bịt."""
    with pytest.raises(MergeNotAuthorized, match="không phải nội dung sắp"):
        authorize_merge(
            module_id="m",
            branch="feature/m",
            reports=_bao_cao_dat(),
            decision=_quyet_dinh("sha256:ban_da_duyet"),
            content_digest="sha256:ban_khac_hoan_toan",
        )


def test_bao_cao_tu_mau_thuan_khong_the_ton_tai() -> None:
    """Không thể chế một ToolReport vừa passed vừa có lỗi để lách."""
    with pytest.raises(ValueError, match="tự mâu thuẫn"):
        ToolReport(gate="static", passed=True, errors=[ToolError("vi phạm ràng buộc")])


# --------------------------------------------------------------------------
# TC-01 phần 2 — merge() không có lối vào nào khác
# --------------------------------------------------------------------------


def _chuan_bi_nhanh(repo: GitRepo, artifact: CodeArtifact) -> str:
    # `start_module` nay trả về DANH SÁCH TỆP ĐÃ DỌN, không trả tên nhánh:
    # nó phải nói ra việc nó vừa xóa mã còn sót của lượt hỏng trước (SL-151).
    repo.start_module("drv_bus_sensor")
    branch = repo.branch_for("drv_bus_sensor")
    from eaa.tools.compile import write_artifact

    write_artifact(artifact, repo.root)
    repo.commit_artifact(artifact, module_id="drv_bus_sensor")
    return branch


def test_merge_thanh_cong_khi_du_giay_phep(repo: GitRepo) -> None:
    branch = _chuan_bi_nhanh(repo, _artifact())
    digest = repo.diff_digest(branch)

    giay_phep = authorize_merge(
        module_id="drv_bus_sensor",
        branch=branch,
        reports=_bao_cao_dat(),
        decision=_quyet_dinh(digest),
        content_digest=digest,
    )
    commit = repo.merge(giay_phep)

    assert repo.current_branch() == "main"
    assert commit
    assert "gate-decision: G3 approved by Vũ Trí Công" in repo.commit_message()
    assert (repo.root / "src" / "m.c").is_file()


@pytest.mark.parametrize(
    "thu_truyen",
    [None, True, "approved", {"decision": "approved"}, 1, ["G3"]],
)
def test_merge_tu_choi_moi_thu_khong_phai_giay_phep(repo: GitRepo, thu_truyen) -> None:
    """Thử mọi tổ hợp — merge() không nhận gì ngoài MergeAuthorization."""
    _chuan_bi_nhanh(repo, _artifact())
    with pytest.raises(MergeNotAuthorized, match="chỉ nhận MergeAuthorization"):
        repo.merge(thu_truyen)
    assert repo.current_branch() == "feature/drv_bus_sensor"


def test_merge_khong_co_tham_so_nao_de_bo_qua_kiem_tra() -> None:
    """Chữ ký hàm là một phần của bất biến: không có cờ force/skip/yes."""
    import inspect

    tham_so = list(inspect.signature(GitRepo.merge).parameters)
    assert tham_so == ["self", "authorization"], (
        f"merge() có thêm tham số {tham_so[2:]} — mọi tham số thêm vào đây đều là "
        "một lối đi tiềm năng vòng qua bất biến"
    )


def test_sua_nhanh_sau_khi_duyet_thi_merge_bi_chan(repo: GitRepo) -> None:
    """Duyệt xong rồi lén thêm commit — giấy phép phải hết hiệu lực."""
    branch = _chuan_bi_nhanh(repo, _artifact())
    digest = repo.diff_digest(branch)
    giay_phep = authorize_merge(
        module_id="drv_bus_sensor",
        branch=branch,
        reports=_bao_cao_dat(),
        decision=_quyet_dinh(digest),
        content_digest=digest,
    )

    (repo.root / "src" / "len_them.c").write_text("void x(void){}\n", encoding="utf-8")
    repo.commit_artifact(_artifact(files={}), module_id="drv_bus_sensor")

    with pytest.raises(MergeNotAuthorized, match="đã thay đổi kể từ khi được duyệt"):
        repo.merge(giay_phep)


def test_giay_phep_bi_sua_sau_khi_dung_van_bi_kiem_lai(repo: GitRepo) -> None:
    """Giấy phép cất đi rồi dùng lại phải được kiểm lại, không tin sẵn."""
    branch = _chuan_bi_nhanh(repo, _artifact())
    digest = repo.diff_digest(branch)
    giay_phep = authorize_merge(
        module_id="drv_bus_sensor",
        branch=branch,
        reports=_bao_cao_dat(),
        decision=_quyet_dinh(digest),
        content_digest=digest,
    )

    gia_mao = MergeAuthorization.__new__(MergeAuthorization)
    object.__setattr__(gia_mao, "module_id", giay_phep.module_id)
    object.__setattr__(gia_mao, "branch", branch)
    object.__setattr__(
        gia_mao, "reports", (ToolReport(gate="compile", passed=False, errors=[ToolError("x")]),)
    )
    object.__setattr__(gia_mao, "decision", giay_phep.decision)
    object.__setattr__(gia_mao, "content_digest", digest)
    object.__setattr__(gia_mao, "issued_at", giay_phep.issued_at)

    with pytest.raises(MergeNotAuthorized, match="chưa đạt"):
        repo.merge(gia_mao)


# --------------------------------------------------------------------------
# TC-01 phần 3 — quét mã nguồn: "không tồn tại nhánh mã nào khác"
# --------------------------------------------------------------------------


def _engine_files() -> list[Path]:
    return sorted(
        p for p in ENGINE.rglob("*.py") if "__pycache__" not in p.parts
    )


def test_chi_MOT_noi_trong_engine_goi_lenh_merge_cua_git() -> None:
    """Trả lời trực tiếp cho chữ "không tồn tại" của TC-01.

    Quét bằng cây cú pháp chứ không bằng biểu thức trên từng dòng: một lời gọi
    trải trên nhiều dòng sẽ lọt lưới phép quét theo dòng, và một phép quét lọt
    lưới ở đây thì chứng minh không còn giá trị gì.
    """
    goi: list[str] = []
    for path in _engine_files():
        cay = ast.parse(path.read_text(encoding="utf-8"))
        for nut in ast.walk(cay):
            if not isinstance(nut, ast.Call) or not isinstance(nut.func, ast.Attribute):
                continue
            if nut.func.attr != "_git" or not nut.args:
                continue
            dau = nut.args[0]
            if isinstance(dau, ast.Constant) and dau.value == "merge":
                goi.append(f"{path.relative_to(ENGINE.parent)}:{nut.lineno}")

    assert len(goi) == 1, (
        "Lệnh merge của Git phải được gọi từ đúng MỘT nơi (GitRepo.merge). "
        f"Tìm thấy {len(goi)}: {goi}"
    )
    assert goi[0].startswith("eaa/vcs.py")


def test_phep_quet_ma_nguon_that_su_bat_duoc_loi_goi_merge(tmp_path: Path) -> None:
    """Meta-test: bộ quét ở trên phải bắt được cả lời gọi trải nhiều dòng.

    Một phép quét hỏng sẽ luôn xanh và không ai biết — cùng lý do với meta-test
    của TC-38.
    """
    mau = tmp_path / "gia_dinh.py"
    mau.write_text(
        "class X:\n"
        "    def duong_vong(self):\n"
        "        self._git(\n"
        '            "merge",\n'
        '            "--no-ff",\n'
        "        )\n",
        encoding="utf-8",
    )
    cay = ast.parse(mau.read_text(encoding="utf-8"))
    tim_thay = [
        nut
        for nut in ast.walk(cay)
        if isinstance(nut, ast.Call)
        and isinstance(nut.func, ast.Attribute)
        and nut.func.attr == "_git"
        and nut.args
        and isinstance(nut.args[0], ast.Constant)
        and nut.args[0].value == "merge"
    ]
    assert len(tim_thay) == 1, "bộ quét không bắt được lời gọi merge trải nhiều dòng"


def test_khong_module_nao_ngoai_vcs_goi_lenh_git_truc_tiep() -> None:
    """Mọi thao tác Git đi qua GitRepo — nếu không, bất biến chỉ bảo vệ một lối."""
    vi_pham: list[str] = []
    for path in _engine_files():
        if path.name == "vcs.py":
            continue
        for lineno, dong in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'subprocess\.\w+\(\s*\[\s*["\']git["\']', dong):
                vi_pham.append(f"{path.relative_to(ENGINE.parent)}:{lineno}")
    assert not vi_pham, f"Gọi git ngoài eaa/vcs.py: {vi_pham}"


def test_khong_noi_nao_trong_luong_tu_dong_tu_phe_duyet_gate() -> None:
    """Máy không được tự ký thay người, ở bất kỳ module nào của engine.

    Chỉ ``gates.py`` (nơi định nghĩa hành vi) và ``cli.py`` (nơi con người gõ
    lệnh) được phép nhắc tới việc phê duyệt.
    """
    duoc_phep = {"gates.py", "cli.py"}
    vi_pham: list[str] = []

    for path in _engine_files():
        if path.name in duoc_phep:
            continue
        cay = ast.parse(path.read_text(encoding="utf-8"))
        for nut in ast.walk(cay):
            if isinstance(nut, ast.Call) and isinstance(nut.func, ast.Attribute):
                if nut.func.attr in ("approve", "confirm_interactive"):
                    vi_pham.append(
                        f"{path.relative_to(ENGINE.parent)}:{nut.lineno}: "
                        f".{nut.func.attr}()"
                    )

    assert not vi_pham, (
        "Luồng tự động tự phê duyệt gate — vi phạm FR-GATE-01: " + "; ".join(vi_pham)
    )


def test_khong_co_co_dong_lenh_nao_mang_nghia_tu_duyet() -> None:
    """Không tồn tại --yes / --force / --skip-gate trong bộ lệnh."""
    from eaa.cli import build_parser

    dang_ngo = re.compile(
        r"--(yes|force-approve|auto-approve|skip-gate|no-gate|no-confirm)\b"
    )
    tro_giup = build_parser().format_help()
    parser = build_parser()
    tat_ca = [tro_giup]
    for hanh_dong in parser._subparsers._group_actions:  # type: ignore[union-attr]
        for ten, sub in hanh_dong.choices.items():  # type: ignore[attr-defined]
            tat_ca.append(sub.format_help())

    tim_thay = [m.group(0) for van_ban in tat_ca for m in dang_ngo.finditer(van_ban)]
    assert not tim_thay, f"Bộ lệnh có cờ tự duyệt: {set(tim_thay)}"


# --------------------------------------------------------------------------
# Human Gate — hành vi
# --------------------------------------------------------------------------


def _payload(gate_id: str = MERGE_GATE, **ghi_de) -> GatePayload:
    mac_dinh = dict(
        gate_id=gate_id,
        title="Review diff drv_bus_sensor",
        module="drv_bus_sensor",
        summary=("4 cổng đạt", "Flash 31.2%"),
        details="diff --git a/src/m.c b/src/m.c\n+void m_init(void) {}\n",
        checklist=("Kiểm cấu hình bus khớp hồ sơ phần cứng",),
        content_digest="sha256:noi_dung_nhanh",
    )
    mac_dinh.update(ghi_de)
    return GatePayload(**mac_dinh)


def test_yeu_cau_gate_khong_tu_quyet_dinh(gate: HumanGate) -> None:
    """request() chỉ đặt hồ sơ lên bàn, không mở đường."""
    gate.request(_payload())
    assert gate.status(MERGE_GATE) == "pending"
    assert gate.latest(MERGE_GATE) is None
    assert len(gate.pending()) == 1


def test_phe_duyet_ghi_nhat_ky_va_neo_vao_bam_noi_dung(gate: HumanGate) -> None:
    payload = _payload()
    gate.request(payload)
    quyet_dinh = gate.approve(MERGE_GATE, actor="Vũ Trí Công")

    assert quyet_dinh.approved
    assert quyet_dinh.payload_digest == payload.digest
    assert gate.status(MERGE_GATE) == APPROVED
    assert gate.is_approved_for(MERGE_GATE, payload.digest)
    assert not gate.is_approved_for(MERGE_GATE, "sha256:noi_dung_khac")


def test_phe_duyet_khi_khong_co_yeu_cau_nao_bi_tu_choi(gate: HumanGate) -> None:
    with pytest.raises(GateNotPending):
        gate.approve(MERGE_GATE, actor="ai đó")


def test_quyet_dinh_phai_co_nguoi_chiu_trach_nhiem(gate: HumanGate) -> None:
    gate.request(_payload())
    with pytest.raises(GateError, match="tên người quyết định"):
        gate.approve(MERGE_GATE, actor="   ")


def test_noi_dung_doi_giua_luc_xem_va_luc_duyet_thi_bi_chan(gate: HumanGate) -> None:
    gate.request(_payload())
    with pytest.raises(GateError, match="đã thay đổi kể từ lúc bạn xem"):
        gate.approve(MERGE_GATE, actor="Vũ Trí Công", expect_digest="sha256:ban_cu")


def test_gate_khong_hop_le_bi_tu_choi() -> None:
    with pytest.raises(GateError, match="Gate không hợp lệ"):
        GatePayload(gate_id="G9", title="x")


def test_phien_khong_co_terminal_KHONG_duoc_mac_dinh_dong_y(
    gate: HumanGate, monkeypatch
) -> None:
    """Chạy trong script hay CI mà im lặng cho qua là đường vòng TC-01 đi tìm."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(GateNotInteractive, match="chế độ tự đồng ý"):
        gate.confirm_interactive(_payload())


# --------------------------------------------------------------------------
# TC-02 — reject có hệ quả đúng
# --------------------------------------------------------------------------


def test_tc02_tu_choi_bat_buoc_kem_ly_do(gate: HumanGate) -> None:
    gate.request(_payload())
    with pytest.raises(GateError, match="bắt buộc kèm lý do"):
        gate.reject(MERGE_GATE, actor="Vũ Trí Công", reason="   ")


def test_tc02_ly_do_tu_choi_di_vao_error_ledger(gate: HumanGate, tmp_path: Path) -> None:
    gate.request(_payload())
    gate.reject(
        MERGE_GATE,
        actor="Vũ Trí Công",
        reason="thiếu kiểm mã trạng thái sau mỗi thao tác bus",
    )

    so = ErrorLedger(tmp_path / "ledger.jsonl")
    muc = so.entries()
    assert len(muc) == 1
    assert muc[0].category == "gate_rejection"
    assert "thiếu kiểm mã trạng thái" in muc[0].description
    assert muc[0].module == "drv_bus_sensor"


def test_tc02_ly_do_tu_choi_vao_prompt_lan_sinh_lai(gate: HumanGate, tmp_path: Path) -> None:
    """Nửa sau của TC-02: lý do phải xuất hiện trong prompt lần sau."""
    gate.request(_payload())
    gate.reject(MERGE_GATE, actor="Vũ Trí Công", reason="thiếu kiểm mã trạng thái")

    so = ErrorLedger(tmp_path / "ledger.jsonl")
    quy_tac = so.rules_for("drv_bus_sensor")
    assert quy_tac and "thiếu kiểm mã trạng thái" in quy_tac[0]


def test_tc02_tu_choi_roi_thi_khong_merge_duoc(repo: GitRepo, gate: HumanGate) -> None:
    branch = _chuan_bi_nhanh(repo, _artifact())
    digest = repo.diff_digest(branch)

    gate.request(_payload(details=digest))
    gate.reject(MERGE_GATE, actor="Vũ Trí Công", reason="chưa đạt")

    with pytest.raises(MergeNotAuthorized):
        authorize_merge(
            module_id="drv_bus_sensor",
            branch=branch,
            reports=_bao_cao_dat(),
            decision=gate.latest(MERGE_GATE),
            content_digest=digest,
        )
    assert repo.current_branch() == branch


# --------------------------------------------------------------------------
# Nhật ký quyết định — bằng chứng cho tiêu chí nghiệm thu STP-04 §5
# --------------------------------------------------------------------------


def test_nhat_ky_quyet_dinh_la_append_only(gate: HumanGate) -> None:
    for lan in range(2):
        gate.request(_payload(details=f"bản {lan}"))
        gate.reject(MERGE_GATE, actor="Vũ Trí Công", reason=f"lý do {lan}")
    gate.request(_payload(details="bản cuối"))
    gate.approve(MERGE_GATE, actor="Vũ Trí Công")

    lich_su = gate.decisions(MERGE_GATE)
    assert [d.decision for d in lich_su] == [REJECTED, REJECTED, APPROVED]
    assert [d.reason for d in lich_su[:2]] == ["lý do 0", "lý do 1"]


def test_nhat_ky_quyet_dinh_hong_thi_bao_loi_kem_so_dong(gate: HumanGate) -> None:
    gate.request(_payload())
    gate.approve(MERGE_GATE, actor="Vũ Trí Công")
    with open(gate.decisions_path, "a", encoding="utf-8") as f:
        f.write("{không phải json\n")

    with pytest.raises(GateError, match=":2:"):
        gate.decisions()


# --------------------------------------------------------------------------
# Commit truy vết được — NFR-07
# --------------------------------------------------------------------------


def test_commit_mang_du_dau_vet_NFR07(repo: GitRepo) -> None:
    _chuan_bi_nhanh(repo, _artifact())
    thong_diep = repo.commit_message()

    for khoa in ("prompt-hash", "model", "constraints-version", "chunk-ids"):
        assert khoa in thong_diep, f"commit thiếu dấu vết {khoa}"
    assert "sha256:aaa" in thong_diep
    assert "ds-021" in thong_diep


def test_artifact_thieu_dau_vet_thi_khong_commit_duoc(repo: GitRepo) -> None:
    from eaa.tools.compile import write_artifact
    from eaa.vcs import GitError

    repo.start_module("m")
    artifact = _artifact(prompt_hash="", model="")
    write_artifact(artifact, repo.root)

    with pytest.raises(GitError, match="NFR-07"):
        repo.commit_artifact(artifact, module_id="m")


def test_nhanh_moi_module_theo_quy_uoc_AIS_8_4(repo: GitRepo) -> None:
    assert repo.branch_for("drv_bus_sensor") == "feature/drv_bus_sensor"
    repo.start_module("drv_bus_sensor")
    assert repo.current_branch() == "feature/drv_bus_sensor"
