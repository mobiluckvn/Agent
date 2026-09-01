"""TC-111 — hồ sơ đang chờ ở gate không được bị ghi đè.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-142.

Tìm ra khi sinh hai driver liên tiếp cho robot cân bằng::

    eaa gen drv_buzzer   → qua 4 cổng, chờ G3
    eaa gen drv_button   → qua 4 cổng, chờ G3

Rồi nhìn trạng thái::

    backlog:  logic_pid=in_review  drv_button=in_review  drv_buzzer=in_review
    gates/pending_G3.json → module: drv_button

**Ba module đang chờ review, một hồ sơ.** Hai hồ sơ kia đã bị ghi đè.

Cơ chế: một tệp cho mỗi CỔNG, không phải cho mỗi MODULE::

    def _pending_path(self, gate_id):
        return self.gates_dir / f"pending_{gate_id}.json"

`request()` ghi thẳng vào đó. Module thứ hai xoá hồ sơ của module thứ nhất.

Vì sao đây là mất mát thật, không phải phiền toái
--------------------------------------------------

Hồ sơ G3 mang **bản diff và băm nội dung** mà quyết định của người neo vào. Mất
nó thì hai module kia không còn đường nào ra khỏi `in_review`: `gate approve`
báo không có gì đang chờ, và mã đã sinh nằm trên nhánh không ai merge được.

Và nếu người bấm duyệt lúc ấy, họ duyệt `drv_button` trong khi màn hình vừa
báo ba module qua cổng — dễ tin rằng mình vừa duyệt cả ba.

Chọn CHẶN chứ không xếp hàng, và đó là lựa chọn có ý thức
-----------------------------------------------------------

Cách giàu hơn là mỗi module một hồ sơ riêng, để review theo lô. Cách này chặn
`gen` khi cổng còn hồ sơ của module khác. Chọn nó vì nó không đánh mất gì và
nói rõ lối đi tiếp; xếp hàng nhiều hồ sơ là một cơ chế lớn hơn, và nó chỉ có
giá trị khi thực sự có người review theo lô.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.gates import GatePayload, GateError, HumanGate


def _bo_gate(tmp_path: Path) -> HumanGate:
    return HumanGate(tmp_path / "gates", None, None)


def _ho_so(module: str) -> GatePayload:
    return GatePayload(
        gate_id="G3",
        title=f"Review diff module {module}",
        module=module,
        details=f"diff của {module}",
        content_digest=f"sha256:{module}",
    )


def test_module_thu_hai_KHONG_ghi_de_module_thu_nhat(tmp_path: Path) -> None:
    cong = _bo_gate(tmp_path)
    cong.request(_ho_so("drv_buzzer"))

    with pytest.raises(GateError) as loi:
        cong.request(_ho_so("drv_button"))

    thong_diep = str(loi.value)
    assert "drv_buzzer" in thong_diep, "không nói module nào đang giữ chỗ"
    assert "approve" in thong_diep and "reject" in thong_diep, "không nói lối đi tiếp"

    # Và hồ sơ cũ còn nguyên — đây mới là điều phải giữ.
    dang_cho = cong.pending("G3")
    assert len(dang_cho) == 1
    assert dang_cho[0].payload.module == "drv_buzzer"
    assert dang_cho[0].payload.content_digest == "sha256:drv_buzzer"


def test_CUNG_module_thi_ghi_de_duoc(tmp_path: Path) -> None:
    """Sinh lại chính module ấy là chuyện thường — bản diff mới thay bản cũ.

    Đây là đường đi sau mỗi lần từ chối G3, nên chặn nó là chặn cả vòng sửa.
    """
    cong = _bo_gate(tmp_path)
    cong.request(_ho_so("logic_pid"))
    moi = GatePayload(
        gate_id="G3",
        title="Review diff module logic_pid",
        module="logic_pid",
        details="diff MỚI",
        content_digest="sha256:moi",
    )
    cong.request(moi)

    dang_cho = cong.pending("G3")
    assert len(dang_cho) == 1
    assert dang_cho[0].payload.content_digest == "sha256:moi"


def test_cong_KHAC_thi_khong_lien_quan(tmp_path: Path) -> None:
    """G1 đang chờ không được chặn một yêu cầu G3."""
    cong = _bo_gate(tmp_path)
    cong.request(GatePayload(gate_id="G1", title="ràng buộc", content_digest="x"))
    cong.request(_ho_so("drv_buzzer"))
    assert len(cong.pending()) == 2


def test_ho_so_KHONG_gan_module_van_ghi_de_duoc(tmp_path: Path) -> None:
    """G1/G2/G5 không gắn module; giữ nguyên hành vi cũ cho chúng."""
    cong = _bo_gate(tmp_path)
    cong.request(GatePayload(gate_id="G1", title="lần 1", content_digest="a"))
    cong.request(GatePayload(gate_id="G1", title="lần 2", content_digest="b"))
    assert cong.pending("G1")[0].payload.content_digest == "b"


def test_duyet_xong_thi_module_sau_di_tiep_duoc(tmp_path: Path) -> None:
    """Chặn phải là CỔNG, không phải ngõ cụt: qua được sau khi người quyết."""
    cong = _bo_gate(tmp_path)
    cong.request(_ho_so("drv_buzzer"))
    cong.approve("G3", actor="Vũ Trí Công")

    cong.request(_ho_so("drv_button"))
    assert cong.pending("G3")[0].payload.module == "drv_button"
