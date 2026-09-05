"""TC-146 — canh phép đo ngược lịch sử dự án (V3, SL-179).

Xem `docs/CHAN_LY_NEN_V3.md` (chốt TRƯỚC khi chạy) và `docs/V3_KET_QUA.md`.

Bài kiểm này canh cái gì
-------------------------

Không canh "bộ dò tốt". Nó canh **tính toàn vẹn của phép đo**, tức ba thứ mà
nếu trôi đi thì con số 3/13 mất nghĩa mà không ai biết:

1. dữ liệu nguồn còn nguyên (13 lần từ chối, mã ứng viên còn tra được);
2. **tính sạch của phép thử hồi cứu** — bộ dò ra đời SAU dữ liệu;
3. chân lý nền không bị sửa sau khi thấy kết quả.

Điểm (3) là điểm không có bài kiểm nào khác trong kho này canh, và nó là điểm
duy nhất làm V3 khác một lời khai.
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

GOC = pathlib.Path(__file__).resolve().parents[1]
DU_AN = GOC / "projects/robot_balance"
QUYET_DINH = DU_AN / "gates/decisions.jsonl"
LUOT_GOI = DU_AN / "llm_calls.jsonl"
CHAN_LY = GOC / "docs/CHAN_LY_NEN_V3.md"
KET_QUA = GOC / "docs/V3_KET_QUA.md"

#: Commit đã chốt chân lý nền. Nội dung tệp ấy không được đổi sau commit này.
COMMIT_CHOT = "f8313d9"

pytestmark = pytest.mark.skipif(
    not QUYET_DINH.exists(), reason="chưa có bằng chứng Chương 3 trong kho"
)


def _doc(p: pathlib.Path) -> list[dict]:
    return [json.loads(d) for d in p.read_text().splitlines() if d.strip()]


# ── 1 · dữ liệu nguồn còn nguyên ─────────────────────────────────────────────


def test_van_con_dung_13_lan_tu_choi_G3() -> None:
    """Số 13 đi vào mọi con số của V3. Nó trôi thì cả bảng trôi theo."""
    tc = [x for x in _doc(QUYET_DINH)
          if x["decision"] == "rejected" and x["gate_id"] == "G3"]
    assert len(tc) == 13, f"số lần từ chối G3 đổi từ 13 thành {len(tc)}"


def test_moi_lan_tu_choi_deu_co_LY_DO_NGUYEN_VAN() -> None:
    """Lý do nguyên văn LÀ chân lý nền. Một lý do rỗng là một ô không chấm được."""
    for x in _doc(QUYET_DINH):
        if x["decision"] == "rejected":
            assert len(x.get("reason", "")) > 80, (
                f"lần từ chối {x['module']} lúc {x['decided_at']} mất lý do nguyên văn"
            )


def test_ma_ung_vien_van_tra_duoc_cho_ca_13_lan() -> None:
    """Mã bị từ chối không nằm trong kho firmware — chỉ còn trong nhật ký gọi."""
    goi = [x for x in _doc(LUOT_GOI)
           if x.get("response") and "```file:" in x["response"] and x.get("module")]
    tc = sorted((x for x in _doc(QUYET_DINH)
                 if x["decision"] == "rejected" and x["gate_id"] == "G3"),
                key=lambda x: x["decided_at"])
    thieu = [
        x["module"] for x in tc
        if not any(g["module"] == x["module"] and g["called_at"] < x["decided_at"]
                   for g in goi)
    ]
    assert not thieu, f"không còn tra được mã ứng viên cho: {thieu}"


# ── 2 · tính SẠCH của phép thử hồi cứu ───────────────────────────────────────


def test_bon_bo_do_ra_doi_SAU_toan_bo_du_lieu() -> None:
    """Tài sản đắt nhất của V3, và nó không lặp lại được.

    Dữ liệu 01–03/09 không thể bị bốn bộ dò làm nhiễu, vì lúc ấy chưa bộ dò nào
    tồn tại. Nếu ai đó lùi ngày ra đời của một bộ dò xuống trước dữ liệu thì
    phép thử hết sạch, và con số 3/13 không còn nói được điều nó đang nói.
    """
    tre_nhat = max(x["decided_at"] for x in _doc(QUYET_DINH))
    for mo_dun in ("eaa/contract.py", "eaa/sensitivity.py",
                   "eaa/instrument.py", "eaa/tools/regcheck.py"):
        r = subprocess.run(
            ["git", "-C", str(GOC), "log", "--diff-filter=A", "--format=%aI",
             "--", mo_dun],
            capture_output=True, text=True, timeout=60,
        )
        dong = [d for d in r.stdout.split() if d]
        if not dong:
            continue
        assert dong[-1] > tre_nhat, (
            f"{mo_dun} có mặt TRƯỚC quyết định gate cuối ({tre_nhat}) — "
            "phép thử hồi cứu không còn sạch"
        )


# ── 3 · chân lý nền không bị sửa sau khi thấy kết quả ────────────────────────


def test_CHAN_LY_NEN_khong_doi_sau_khi_da_chot() -> None:
    """Điểm quan trọng nhất của cả tệp này.

    V3 là phép tự chấm. Nếu chân lý nền được chỉnh sau khi thấy bộ dò tìm ra
    gì, con số đi ra chỉ nói rằng người viết biết chọn ví dụ. Bài này so nội
    dung hiện tại với bản đã commit tại `COMMIT_CHOT`.
    """
    r = subprocess.run(
        ["git", "-C", str(GOC), "show", f"{COMMIT_CHOT}:docs/CHAN_LY_NEN_V3.md"],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        pytest.skip("chưa tra được commit chốt trong kho này")
    assert r.stdout == CHAN_LY.read_text(), (
        "docs/CHAN_LY_NEN_V3.md đã đổi so với bản chốt trước khi chạy bộ dò. "
        "Sửa chân lý nền sau khi thấy kết quả làm cả phép đo V3 mất giá trị — "
        "nếu thật sự cần sửa, hãy ghi một mục sai lệch mới thay vì sửa im lặng."
    )


def test_ban_ket_qua_co_du_ba_con_so_khong_duoc_gop() -> None:
    """BẮT ĐƯỢC · BỎ SÓT · KHÔNG CHẠY ĐƯỢC phải đứng riêng trong báo cáo.

    Gộp *bỏ sót* với *ngoài tầm* là cách dễ nhất để bảng nói dối, và nó nói dối
    theo cả hai hướng.
    """
    van = KET_QUA.read_text()
    for chu in ("BẮT ĐƯỢC", "BỎ SÓT", "KÊU NHƯNG TRẬT LÝ DO", "IM ĐÚNG"):
        assert chu in van, f"bản kết quả thiếu hạng {chu!r}"


def test_ban_ket_qua_van_cong_bo_phan_du_doan_SAI() -> None:
    """Phần dự đoán sai là phần dễ bị lặng lẽ bỏ đi nhất khi viết lại báo cáo."""
    van = KET_QUA.read_text()
    assert "dự đoán của tôi SAI" in van or "dự đoán SAI" in van
    assert "54 phút" in van, "mất con số về độ sớm — kết quả đáng giá nhất của V3"


# ── 4 · chỗ lệch đã sửa trong contract.py không được quay lại ────────────────


def test_mot_cau_lenh_KHONG_duoc_doc_thanh_khai_bao_ham() -> None:
    """Chỗ lệch V3 làm lộ: hai danh sách từ khoá cho cùng một mục đích.

    Danh sách trong `khai_bao_ham` từng thiếu `else`, nên
    `else if(x == 200) f(a, b);` bị đọc thành khai báo — rồi ở bản sau thành
    một "hàm bị mất" bịa ra từ đầu tới cuối.
    """
    from eaa.contract import khai_bao_ham, pha_vo_hop_dong

    than = """
    void app_step(void) {
        if (seq_time == 100) buzzer_beep_async(now_ms, 50);
        else if (seq_time == 200) buzzer_beep_async(now_ms, 50);
        do { tick(); } while (0);
        switch (st) { case 1: handle(x); break; }
    }
    """
    assert "buzzer_beep_async" not in khai_bao_ham(than)
    assert "handle" not in khai_bao_ham(than)
    # Và chiều hại nhất: bản sau bỏ câu lệnh ấy đi KHÔNG được thành "MẤT".
    assert pha_vo_hop_dong(than, "void app_step(void) { tick(); }") == []
