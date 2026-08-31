"""TC-86 — người duyệt lệnh cài; Agent là kẻ chạy nó.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-110.

Tìm ra khi người dùng đọc câu trả lời của tôi cho `eaa doctor --fix` và nói:
*"Agent phải hỏi bạn về bộ công cụ đó và tự cài chứ."*

Đúng, và trước bản sửa này thì **không có đường nào để làm thế**. Xác nhận cài
chỉ tồn tại dưới dạng một câu hỏi trên terminal, trong cùng tiến trình. Phiên
không có terminal thì doctor dừng và **không nói ra lối đi tiếp** — hết đường.

Human Gate thì không thế: `confirm_interactive` gặp phiên không terminal sẽ
nêu đích danh `eaa gate approve <G>`. Người quyết định ngoài luồng, quyết định
ấy được ghi lại, và máy đọc nó ra ở lượt sau. Cổng cài thiếu đúng cánh cửa đó.

Bất biến không đổi: **không có lệnh cài nào chạy mà không có một người duyệt
đúng lệnh ấy.** Cái đổi là ai gõ phím lúc cài — sau khi người đã duyệt, Agent
chạy. Cùng hình dạng với `tool approve` (người) → `tool run` (Agent) của SL-77:
*Agent mở rộng CÁI NÓ LÀM, không mở rộng QUYỀN NÓ CÓ.*
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.doctor import (
    Doctor,
    EnvLock,
    InstallApprovals,
    InstallNotConfirmed,
    ToolManifest,
)

MANIFEST = """\
tools:
  - name: cong-cu-gia
    check: [cong-cu-gia, "--version"]
    blocking: true
    gate: compile
    install:
      macos: [brew, install, cong-cu-gia]
      linux: [apt-get, install, "-y", cong-cu-gia]
      windows: [choco, install, cong-cu-gia]
"""


@pytest.fixture()
def doctor(tmp_path: Path) -> Doctor:
    tep = tmp_path / "tools.yaml"
    tep.write_text(MANIFEST, encoding="utf-8")
    return Doctor(
        manifest=ToolManifest.load(tep),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
        approvals=InstallApprovals(tmp_path / "install_approvals.jsonl"),
    )


def _lenh_cua(doctor: Doctor) -> tuple[str, ...]:
    return doctor.install_command(doctor.manifest.get("cong-cu-gia"))


def _khong_chay(doctor: Doctor) -> list:
    """Thay chỗ chạy lệnh thật bằng một chỗ ghi lại — bài kiểm không cài gì cả."""
    da_chay: list = []
    doctor._run_install = lambda spec, lenh: (  # type: ignore[assignment]
        da_chay.append(tuple(lenh)) or [f"{spec.name}: đã cài"]
    )
    return da_chay


# ═══════════ cánh cửa còn thiếu: dừng thì phải NÊU LỐI ĐI TIẾP ═══════════


def test_khong_co_nguoi_thi_NEU_DICH_DANH_lenh_duyet(doctor: Doctor) -> None:
    """Dừng mà không nói đi đâu tiếp thì đó là ngõ cụt, không phải một cổng.

    Human Gate nêu đích danh `eaa gate approve <G>`. Cổng cài phải nêu được
    câu tương đương, nếu không thì một phiên làm việc qua người trung gian
    **không bao giờ** cài được công cụ, dù người có đồng ý bao nhiêu lần.
    """
    doctor.confirm = lambda ten, lenh: None
    da_chay = _khong_chay(doctor)

    with pytest.raises(InstallNotConfirmed) as loi:
        doctor.fix(doctor.scan())

    assert "eaa doctor approve cong-cu-gia" in str(loi.value)
    assert da_chay == [], "chưa duyệt thì không được chạy gì"


def test_hoi_MOT_LAN_cho_ca_bo_chu_khong_hoi_tung_cai(tmp_path: Path) -> None:
    """Năm công cụ thiếu thì nêu cả năm rồi dừng một lần.

    Dừng ngay ở cái đầu tiên bắt người duyệt xong lại chạy lại để biết cái thứ
    hai — mỗi lượt một tin, và người không bao giờ thấy được toàn cảnh việc họ
    đang đồng ý.
    """
    tep = tmp_path / "tools.yaml"
    tep.write_text(
        MANIFEST
        + """\
  - name: cong-cu-gia-2
    check: [cong-cu-gia-2, "--version"]
    blocking: true
    gate: static
    install:
      macos: [brew, install, cong-cu-gia-2]
      linux: [apt-get, install, "-y", cong-cu-gia-2]
      windows: [choco, install, cong-cu-gia-2]
""",
        encoding="utf-8",
    )
    d = Doctor(
        manifest=ToolManifest.load(tep),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
        approvals=InstallApprovals(tmp_path / "install_approvals.jsonl"),
        confirm=lambda ten, lenh: None,
    )

    with pytest.raises(InstallNotConfirmed) as loi:
        d.fix(d.scan())

    noi_dung = str(loi.value)
    assert "cong-cu-gia" in noi_dung and "cong-cu-gia-2" in noi_dung
    assert any("cong-cu-gia-2" in d for d in loi.value.nhat_ky)


# ═══════════ người duyệt rồi thì AGENT CHẠY ═══════════


def test_da_duyet_thi_Agent_tu_chay_khong_can_terminal(doctor: Doctor) -> None:
    """Đây là điều người dùng đòi, và là chỗ bản sửa này thay đổi hành vi."""
    lenh = _lenh_cua(doctor)
    doctor.approvals.approve("cong-cu-gia", lenh, by="Vũ Trí Công")

    doctor.confirm = lambda ten, l: None  # vẫn không có ai ở terminal
    da_chay = _khong_chay(doctor)

    nhat_ky = doctor.fix(doctor.scan())

    assert da_chay == [lenh], "người đã duyệt đúng lệnh này rồi — phải chạy"
    assert any("Vũ Trí Công" in d for d in nhat_ky), "phải nói AI duyệt"


def test_duyet_khong_ghi_ten_nguoi_thi_TU_CHOI(doctor: Doctor) -> None:
    """Một quyết định không có người chịu trách nhiệm không phải quyết định."""
    with pytest.raises(Exception, match="ai duyệt"):
        doctor.approvals.approve("cong-cu-gia", _lenh_cua(doctor), by="  ")


# ═══════════ duyệt MỘT LỆNH CỤ THỂ, không duyệt chung chung ═══════════


def test_duyet_lenh_nay_KHONG_cho_phep_chay_lenh_khac(doctor: Doctor) -> None:
    """Bất biến quan trọng nhất của cả bản sửa.

    Không có nó thì "duyệt cài X rồi cài Y" là một đường vòng hợp lệ về mặt kỹ
    thuật: chỉ cần manifest đổi giữa lúc duyệt và lúc chạy. Manifest là dữ
    liệu, và dữ liệu thì đổi được — kể cả bởi một đề xuất công cụ mới.

    Cùng tính chất mà GatePayload.content_digest giữ cho Human Gate.
    """
    doctor.approvals.approve("cong-cu-gia", ("brew", "install", "thu-khac"), by="ai đó")
    doctor.confirm = lambda ten, l: None
    da_chay = _khong_chay(doctor)

    with pytest.raises(InstallNotConfirmed):
        doctor.fix(doctor.scan())
    assert da_chay == [], "duyệt lệnh khác thì không mở đường cho lệnh này"


def test_duyet_cong_cu_khac_KHONG_lay_sang_duoc(doctor: Doctor) -> None:
    doctor.approvals.approve("cong-cu-khac", _lenh_cua(doctor), by="ai đó")
    doctor.confirm = lambda ten, l: None
    da_chay = _khong_chay(doctor)

    with pytest.raises(InstallNotConfirmed):
        doctor.fix(doctor.scan())
    assert da_chay == []


# ═══════════ sổ duyệt: nối tiếp, đọc lại được ═══════════


def test_so_duyet_ghi_NOI_TIEP_va_doc_lai_duoc(doctor: Doctor) -> None:
    """Append-only + đọc lại — cùng luật với mọi kho tri thức khác (TC-26)."""
    doctor.approvals.approve("a", ("x",), by="người 1")
    doctor.approvals.approve("b", ("y",), by="người 2")

    dong = doctor.approvals.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(dong) == 2
    assert json.loads(dong[0])["tool"] == "a"
    assert [k.tool for k in doctor.approvals.all()] == ["a", "b"]
    assert doctor.approvals.find("a", ("x",)) is not None
    assert doctor.approvals.find("a", ("y",)) is None


def test_so_duyet_hong_khong_lam_sap_lenh(doctor: Doctor) -> None:
    """Sổ hỏng phải đọc thành "chưa duyệt", không thành một vụ sập.

    Và tuyệt đối không được đọc thành "đã duyệt" — hướng hỏng an toàn chỉ có
    một chiều.
    """
    doctor.approvals.path.write_text("{ không phải json\n", encoding="utf-8")
    assert doctor.approvals.all() == []
    assert doctor.approvals.find("cong-cu-gia", _lenh_cua(doctor)) is None


# ═══════════ ranh giới quyền của Agent ═══════════


def test_doctor_approve_KHONG_nam_trong_danh_muc_Agent(doctor: Doctor) -> None:
    """Agent chạy được lệnh cài đã duyệt; nó KHÔNG tự duyệt được.

    Đây là chỗ phân biệt "mở rộng cái nó làm" với "mở rộng quyền nó có".
    """
    from eaa.agent import NGOAI_DANH_MUC, TOOLBOX

    trong_danh_muc = {" ".join(t.argv) for t in TOOLBOX}
    assert "doctor approve" not in trong_danh_muc
    assert "doctor approve" in NGOAI_DANH_MUC

    # …còn quét và chạy lệnh ĐÃ DUYỆT thì phải có, nếu không thì lời hứa
    # "Agent tự cài sau khi bạn duyệt" không có đường nào thực hiện.
    assert "doctor" in trong_danh_muc
    assert "doctor --fix" in trong_danh_muc


def test_muc_khong_khai_takes_thi_KHONG_nhan_them_doi_so() -> None:
    """Lỗ hổng suýt lọt khi thêm `doctor` vào danh mục — bài canh cũ bắt được.

    `tool_for` khớp theo TIỀN TỐ. Nên thêm một mục `doctor` để Agent quét được
    máy sẽ mở luôn `doctor approve`, `doctor --accept-drift` — tức là mở đúng
    cái quyền mà mục ấy sinh ra để không đụng tới.

    Hàng rào của sản phẩm này là danh mục, nên danh mục phải nói ĐÚNG cái nó
    cho phép. Một mục đọc như *"được gọi `doctor`"* mà thực tế là *"được gọi
    bất cứ gì bắt đầu bằng `doctor`"* thì bảng quyền hạn không còn đọc được —
    và một bảng quyền hạn không đọc được thì không ai kiểm được nó.
    """
    from eaa.agent import TOOLBOX, tool_for

    assert tool_for(["doctor"]) is not None
    for them in (["approve", "x"], ["--accept-drift"], ["--propose"]):
        assert tool_for(["doctor", *them]) is None, f"tiền tố mở: doctor {them}"

    # Luật chung, không phải vá riêng cho 'doctor': mọi mục không khai 'takes'
    # đều phải khớp đúng độ dài.
    for t in TOOLBOX:
        if not t.takes:
            assert tool_for([*t.argv, "--gi-do"]) is None, \
                f"mục {t.name!r} không khai takes mà vẫn nuốt đối số thừa"


def test_ly_do_tu_choi_lenh_hai_tu_phai_TOI_DUOC_nguoi_doc() -> None:
    """`NGOAI_DANH_MUC` có khóa hai từ, mà chỗ tra cứu chỉ lấy từ đầu tiên.

    Nên mọi lời giải thích cho lệnh hai từ — 'tool approve', 'doctor approve',
    'skill approve' — đều nằm chết trong tệp: viết ra, đi vào prompt, nhưng
    không bao giờ tới được người hỏi. Họ nhận câu chung chung "không có trong
    danh mục", đúng chỗ mà một câu cụ thể là hữu ích nhất.
    """
    from eaa.agent import NGOAI_DANH_MUC, AgentLoop

    ly_do = AgentLoop._vi_sao_khong(None, ["doctor", "approve", "cong-cu-gia"])
    assert ly_do == NGOAI_DANH_MUC["doctor approve"]

    # Lệnh một từ vẫn phải giữ nguyên đường cũ.
    assert AgentLoop._vi_sao_khong(None, ["flash"]) == NGOAI_DANH_MUC["flash"]
