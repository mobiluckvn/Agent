"""TC-52 — kiểm sau khi nạp: đọc ngược bộ nhớ, hoặc nói rõ là không kiểm được.

Nghiệp vụ N-075. Đây là mắt xích cuối cùng của chuỗi "thứ trên chip có đúng là
thứ đã duyệt không", và trước bản này nó đang bị bỏ trống: mã thoát 0 của công
cụ nạp được ngầm đọc thành "nạp đúng".

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-52a | Nạp xong thì đọc ngược và so | pack có ``flash_verify`` → bản ghi mang trạng thái ``khop`` |
| TC-52b | Đọc ngược lệch thì lần nạp KHÔNG đạt | dù công cụ nạp trả 0 |
| TC-52c | Pack không đọc ngược được thì nói thẳng | không mượn mã thoát bước nạp làm bằng chứng |
| TC-52d | Bản ghi cũ không được suy thành "đã kiểm" | mặc định là chưa kiểm, không phải khớp |
| TC-52e | Phong hạng nêu rõ khoảng chưa kiểm | commit khớp mà chưa đọc ngược vẫn phải nói ra |

Điểm đáng chú ý nhất là TC-52c. Cám dỗ tự nhiên khi cài đặt là để trống trường
này và coi như đạt — và làm vậy thì mọi số đo về sau gắn vào một giả định chưa
ai kiểm, mà không ai biết là mình đang giả định.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from eaa.acceptance import check_device_commit
from eaa.flash import (
    VERIFY_KHONG_KIEM_DUOC,
    VERIFY_KHOP,
    VERIFY_LECH,
    FlashLog,
    FlashRecord,
    Flasher,
    VerifyResult,
)
from eaa.platform import CAPABILITIES, load_manifest
from eaa.tools.runner import ToolRunner

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"


class _KhoGia:
    def head(self) -> str:
        return "a" * 40

    def has_changes(self) -> bool:
        return False


@pytest.fixture()
def runner(tmp_path: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


@pytest.fixture()
def anh(tmp_path: Path) -> Path:
    p = tmp_path / "build" / "firmware.hex"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(":00000001FF\n", encoding="utf-8")
    return p


def _flasher(runner: ToolRunner, tmp_path: Path, **kw) -> Flasher:
    kw.setdefault("repo", _KhoGia())
    kw.setdefault("confirm", lambda _: True)
    kw.setdefault("log", FlashLog(tmp_path / "flash_log.jsonl"))
    return Flasher(runner=runner, source_dir=tmp_path, **kw)


def _pack_khong_doc_nguoc(tmp_path: Path) -> Path:
    """Bản sao pack demo đã gỡ năng lực ``flash_verify``.

    Dựng bằng cách sửa manifest chứ không bằng cách vá đối tượng: thứ cần kiểm
    là engine phản ứng ra sao với một pack KHAI BÁO thiếu năng lực, và đó là
    đúng cảnh của một mạch nạp không đọc ngược được.
    """
    goc = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    goc["capabilities"].pop("flash_verify")
    thu_muc = tmp_path / "pack-khong-doc-nguoc"
    thu_muc.mkdir()
    (thu_muc / "pack.yaml").write_text(
        yaml.safe_dump(goc, allow_unicode=True), encoding="utf-8"
    )
    return thu_muc


# --------------------------------------------------------------------------
# TC-52a — nạp xong thì đọc ngược
# --------------------------------------------------------------------------


def test_nap_xong_thi_doc_nguoc_va_ghi_bang_chung(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    ban_ghi = _flasher(runner, tmp_path).run(anh, port="/dev/demo", actor="ky-su")

    assert ban_ghi.passed
    assert ban_ghi.verify_status == VERIFY_KHOP
    assert ban_ghi.verified
    assert "ĐÃ KIỂM" in VerifyResult(ban_ghi.verify_status, ban_ghi.verify_detail).render()


def test_bang_chung_doc_nguoc_song_sot_qua_nhat_ky(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """Trường mới phải đi qua được vòng ghi–đọc JSONL, không chỉ sống trong RAM."""
    nhat_ky = FlashLog(tmp_path / "flash_log.jsonl")
    _flasher(runner, tmp_path, log=nhat_ky).run(anh, port="/dev/demo", actor="ky-su")

    doc_lai = nhat_ky.all()[-1]
    assert doc_lai.verify_status == VERIFY_KHOP
    assert "đã kiểm" in doc_lai.render()


# --------------------------------------------------------------------------
# TC-52b — đọc ngược lệch thì lần nạp KHÔNG đạt
# --------------------------------------------------------------------------


def test_doc_nguoc_lech_thi_lan_nap_khong_dat(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """Công cụ nạp trả 0, nhưng nội dung trên chip khác. Đó là một lần nạp hỏng.

    Dựng cảnh bằng cách để sẵn một "nội dung trên chip" khác ảnh rồi thay bước
    ghi bằng một bước báo đạt mà không chạm vào chip — mô phỏng đúng khối flash
    nhận lệnh ghi, trả về OK, nhưng giữ lại dữ liệu cũ.
    """
    Path(str(anh) + ".on-device").write_text(":00000001AA\n", encoding="utf-8")

    class _RunnerKhongGhiDuoc(ToolRunner):
        def run(self, capability, params=None, **kw):  # type: ignore[override]
            if capability == "flash":
                # Bước ghi "thành công" nhưng không chạm được vào chip.
                from eaa.tools.base import ToolReport

                return ToolReport(gate="flash", passed=True)
            return super().run(capability, params, **kw)

    r = _RunnerKhongGhiDuoc(
        manifest=runner.manifest, work_dir=runner.work_dir, base_params=runner.base_params
    )
    ban_ghi = _flasher(r, tmp_path).run(anh, port="/dev/demo", actor="ky-su")

    assert ban_ghi.verify_status == VERIFY_LECH
    assert not ban_ghi.passed, "đọc ngược lệch mà vẫn báo đạt là đúng lỗ hổng N-075"
    assert "KHÔNG trùng" in ban_ghi.verify_detail


def test_nap_truot_thi_khong_doc_nguoc(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    """Nạp đã trượt thì cái "lệch" đọc được chỉ là hệ quả, không phải dữ kiện mới."""

    class _RunnerNapTruot(ToolRunner):
        def run(self, capability, params=None, **kw):  # type: ignore[override]
            if capability == "flash":
                from eaa.tools.base import ToolError, ToolReport

                return ToolReport(
                    gate="flash", passed=False, errors=[ToolError("mat ket noi")]
                )
            raise AssertionError("không được đọc ngược khi bước nạp đã trượt")

    r = _RunnerNapTruot(
        manifest=runner.manifest, work_dir=runner.work_dir, base_params=runner.base_params
    )
    ban_ghi = _flasher(r, tmp_path).run(anh, port="/dev/demo", actor="ky-su")

    assert not ban_ghi.passed
    assert ban_ghi.verify_status == VERIFY_KHONG_KIEM_DUOC


# --------------------------------------------------------------------------
# TC-52c — không đọc ngược được thì nói thẳng
# --------------------------------------------------------------------------


def test_pack_khong_khai_nang_luc_thi_noi_la_khong_kiem_duoc(
    tmp_path: Path, anh: Path
) -> None:
    r = ToolRunner(
        manifest=load_manifest(_pack_khong_doc_nguoc(tmp_path)),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    ban_ghi = _flasher(r, tmp_path).run(anh, port="/dev/demo", actor="ky-su")

    assert ban_ghi.passed, "không đọc ngược được KHÔNG phải là nạp hỏng"
    assert ban_ghi.verify_status == VERIFY_KHONG_KIEM_DUOC
    assert not ban_ghi.verified
    assert "flash_verify" in ban_ghi.verify_detail

    van_ban = VerifyResult(ban_ghi.verify_status, ban_ghi.verify_detail).render()
    assert "KHÔNG KIỂM ĐƯỢC" in van_ban
    assert "'nạp đúng'" in van_ban, "phải nói thẳng ra điều dễ bị ngầm hiểu"


def test_thieu_cong_cu_doc_nguoc_khong_bi_doc_thanh_khop(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    class _RunnerThieuCongCu(ToolRunner):
        def available(self, capability: str) -> bool:  # type: ignore[override]
            return capability != "flash_verify"

    r = _RunnerThieuCongCu(
        manifest=runner.manifest, work_dir=runner.work_dir, base_params=runner.base_params
    )
    ket = _flasher(r, tmp_path).verify(anh)

    assert ket.status == VERIFY_KHONG_KIEM_DUOC
    assert not ket.checked and not ket.ok
    assert "doctor" in ket.detail


def test_loi_lap_lenh_cua_pack_khong_lam_mat_ban_ghi_nap(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """Đọc ngược hỏng vì lý do gì cũng không được ném ra ngoài.

    Thứ đã nằm trên chip thì vẫn nằm đó; ném ngoại lệ ở đây chỉ làm mất phần
    ghi chép về nó.
    """

    class _RunnerNo(ToolRunner):
        def run(self, capability, params=None, **kw):  # type: ignore[override]
            if capability == "flash_verify":
                raise RuntimeError("mẫu lệnh của pack thiếu tham số")
            return super().run(capability, params, **kw)

    r = _RunnerNo(
        manifest=runner.manifest, work_dir=runner.work_dir, base_params=runner.base_params
    )
    nhat_ky = FlashLog(tmp_path / "flash_log.jsonl")
    ban_ghi = _flasher(r, tmp_path, log=nhat_ky).run(anh, port="/dev/demo", actor="ky-su")

    assert ban_ghi.verify_status == VERIFY_KHONG_KIEM_DUOC
    assert "thiếu tham số" in ban_ghi.verify_detail
    assert len(nhat_ky.all()) == 1


# --------------------------------------------------------------------------
# TC-52d — bản ghi cũ không được suy thành "đã kiểm"
# --------------------------------------------------------------------------


def test_ban_ghi_cu_khong_co_truong_nay_thi_la_chua_kiem() -> None:
    cu = FlashRecord.from_dict(
        {
            "image": "fw.hex",
            "image_digest": "sha256:x",
            "commit": "a" * 40,
            "port": "/dev/demo",
            "actor": "ky-su",
            "flashed_at": "2026-01-01T00:00:00+00:00",
            "passed": True,
        }
    )
    assert cu.verify_status == VERIFY_KHONG_KIEM_DUOC
    assert not cu.verified


# --------------------------------------------------------------------------
# TC-52e — phong hạng nêu rõ khoảng chưa kiểm
# --------------------------------------------------------------------------


def _nhat_ky_mot_lan_nap(tmp_path: Path, verify_status: str) -> FlashLog:
    log = FlashLog(tmp_path / "flash_log.jsonl")
    log.append(
        FlashRecord(
            image="fw.hex",
            image_digest="sha256:x",
            commit="a" * 40,
            port="/dev/demo",
            actor="ky-su",
            flashed_at="2026-01-01T00:00:00+00:00",
            passed=True,
            verify_status=verify_status,
            verify_detail="" if verify_status == VERIFY_KHOP else "pack không khai",
        )
    )
    return log


def test_commit_khop_va_da_doc_nguoc_thi_khong_con_gi_phai_ngo(tmp_path: Path) -> None:
    kiem = check_device_commit("a" * 40, _nhat_ky_mot_lan_nap(tmp_path, VERIFY_KHOP))
    assert kiem.verified and kiem.readback_verified
    assert not kiem.message


def test_commit_khop_ma_chua_doc_nguoc_thi_van_phai_noi_ra(tmp_path: Path) -> None:
    kiem = check_device_commit(
        "a" * 40, _nhat_ky_mot_lan_nap(tmp_path, VERIFY_KHONG_KIEM_DUOC)
    )
    assert kiem.verified, "vẫn đi tiếp được — đây là thiếu biết, không phải mâu thuẫn"
    assert not kiem.readback_verified
    assert "KHÔNG được đọc ngược" in kiem.message


# --------------------------------------------------------------------------
# Ranh giới engine/pack
# --------------------------------------------------------------------------


def test_nang_luc_moi_nam_trong_interface_chu_khong_khai_len(tmp_path: Path) -> None:
    """Pack chỉ được khai năng lực có trong interface — kể cả năng lực mới này."""
    assert "flash_verify" in CAPABILITIES
    for ten in ("avr", "stm32"):
        manifest = load_manifest(REPO / "packs" / ten)
        assert manifest.has("flash_verify"), f"pack {ten} phải đọc ngược được"


def test_doc_nguoc_khong_doi_xac_nhan_rieng() -> None:
    """Chỉ đọc, không đổi gì trên thiết bị — và nó chạy trong một lần nạp đã xác nhận.

    Bắt xác nhận lần hai ở đây sẽ khiến người quen tay bấm 'có' hai lần, làm
    nhạt đi chính lần xác nhận có ý nghĩa (FR-DIA-02).
    """
    manifest = load_manifest(REPO / "packs" / "avr")
    assert manifest.invocation("flash").requires_confirmation
    assert not manifest.invocation("flash_verify").requires_confirmation
