"""TC-42 — nhận diện cổng và nạp firmware xuống thiết bị thật.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-42a | Liệt kê cổng, nhận diện bo | khớp VID/PID do DỰ ÁN khai; không đọc được VID/PID thì nói thẳng là không đọc được |
| TC-42b | Bốn phép kiểm trước khi nạp | thiếu ảnh, kho bẩn, ảnh cũ hơn nguồn — mỗi thứ đều chặn |
| TC-42c | Nạp LUÔN cần người xác nhận | không TTY = không nạp; từ chối = không nạp; FR-DIA-02 |
| TC-42d | Nhật ký nạp append-only | commit nào, ảnh nào, cổng nào, ai, lúc nào — kể cả lần trượt |
| TC-42e | Engine không đoán cổng | không nhận ra hoặc nhận ra nhiều thì dừng, không chọn bừa |

Vì sao nhóm này gắt hơn các nhóm trước: tới đây hậu quả là VẬT LÝ. Một cổng
kiểm chứng sai chỉ tốn một lượt chạy lại; một lần nạp nhầm thiết bị là hỏng
thật. Nên mọi phép kiểm ở đây đều là "không", không phải "cảnh báo" — và không
cờ dòng lệnh nào bỏ qua được chúng.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest

from eaa.flash import (
    FlashError,
    FlashLog,
    FlashNotConfirmed,
    FlashRecord,
    Flasher,
)
from eaa.platform import load_manifest
from eaa.serialport import (
    SerialPort,
    UsbId,
    match_declared,
    render_ports,
)
from eaa.tools.runner import ToolRunner

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"


# --------------------------------------------------------------------------
# TC-42a — nhận diện cổng
# --------------------------------------------------------------------------


def _cong(device: str, vid: str = "", pid: str = "", **kw) -> SerialPort:
    return SerialPort(
        device=device, vid=vid, pid=pid, source="pyserial" if vid else "glob", **kw
    )


def test_khop_vid_pid_do_du_an_khai() -> None:
    cong = [_cong("/dev/ttyUSB0", "1a86", "7523"), _cong("/dev/ttyUSB1", "0403", "6001")]
    khai = [UsbId(vid="1a86", pid="7523", note="Bo tương thích")]

    ket_qua = match_declared(cong, khai)
    assert ket_qua[0].matched == "Bo tương thích"
    assert not ket_qua[1].matched


def test_vid_khong_kem_pid_nghia_la_moi_bo_cua_hang() -> None:
    cong = [_cong("/dev/ttyACM0", "2341", "0043"), _cong("/dev/ttyACM1", "2341", "0001")]
    ket_qua = match_declared(cong, [UsbId(vid="2341", note="Bo của hãng này")])
    assert all(c.matched for c in ket_qua)


def test_vid_chuan_hoa_dang_viet() -> None:
    """``0x2341``, ``2341``, ``2341`` là cùng một thứ."""
    cong = [_cong("/dev/ttyACM0", "2341", "0043")]
    for cach_viet in ("0x2341", "2341", "2341"):
        assert match_declared(cong, [UsbId(vid=cach_viet, pid="0043")])[0].matched


def test_khong_doc_duoc_vid_pid_thi_noi_thang() -> None:
    """Một dòng "không nhận diện được" trung thực đáng hơn một dòng "không khớp" sai."""
    cong = [_cong("/dev/cu.usbmodem1101")]
    ket_qua = match_declared(cong, [UsbId(vid="2341", pid="0043")])

    assert not ket_qua[0].identifiable
    assert "không đọc được" in ket_qua[0].render()


def test_khop_theo_ten_cong_duoc_ghi_ro_la_chua_chac() -> None:
    cong = [_cong("/dev/cu.usbmodem1101")]
    ket_qua = match_declared(cong, [], port_hint="usbmodem")

    assert "chưa xác nhận" in ket_qua[0].matched


def test_bao_cao_khong_thay_cong_nao_thi_goi_y_viec_can_lam() -> None:
    van_ban = render_ports([])
    assert "đã cắm" in van_ban


def test_doc_khai_bao_bo_tu_ho_so_phan_cung() -> None:
    from eaa.kb import HardwareProfile
    from eaa.serialport import declared_usb_ids

    hp = HardwareProfile.load(REPO / "projects" / "robot_balance" / "hardware_profile.yaml")
    khai, goi_y = declared_usb_ids(hp)

    assert khai, "dự án mẫu phải khai bo của mình"
    assert goi_y
    assert all(u.vid for u in khai)


def test_engine_khong_biet_bo_nao_la_bo_nao() -> None:
    """Cặp VID/PID nằm ở tầng dự án. Engine chỉ so, không biết.

    Đây là cùng một ranh giới mà TC-38 canh, kiểm ở một điểm cụ thể: không một
    mã số nhà sản xuất nào được nằm cứng trong engine.
    """
    ma_nguon = (REPO / "eaa" / "serialport.py").read_text(encoding="utf-8")
    for ma_hang in ("2341", "1a86", "0403", "10c4"):
        assert ma_hang not in ma_nguon, f"mã hãng {ma_hang} bị ghim trong engine"


# --------------------------------------------------------------------------
# Nền cho phần nạp
# --------------------------------------------------------------------------


class _KhoGia:
    """Kho mã tối thiểu — chỉ hai câu hỏi mà Flasher cần hỏi."""

    def __init__(self, commit: str = "a" * 40, ban: bool = False) -> None:
        self._commit = commit
        self.ban = ban

    def head(self) -> str:
        return self._commit

    def has_changes(self) -> bool:
        return self.ban


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


# --------------------------------------------------------------------------
# TC-42b — bốn phép kiểm trước khi nạp
# --------------------------------------------------------------------------


def test_thieu_anh_thi_khong_nap(runner: ToolRunner, tmp_path: Path) -> None:
    kiem = _flasher(runner, tmp_path).preflight(tmp_path / "khong-co.hex")
    assert not kiem.ok
    assert "eaa build" in kiem.render()


def test_kho_ma_ban_thi_khong_nap(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    """Nạp lúc kho bẩn thì bản ghi "đã nạp commit X" là câu sai."""
    f = _flasher(runner, tmp_path, repo=_KhoGia(ban=True))
    kiem = f.preflight(anh)

    assert not kiem.ok
    assert "chưa commit" in kiem.render()


def test_anh_cu_hon_ma_nguon_thi_khong_nap(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """Sửa mã rồi nạp mà quên ráp lại là cách hỏng âm thầm nhất."""
    import os
    import time

    nguon = tmp_path / "src" / "m.c"
    nguon.parent.mkdir(parents=True, exist_ok=True)
    nguon.write_text("void m(void) {}\n", encoding="utf-8")
    moi_hon = anh.stat().st_mtime + 10
    os.utime(nguon, (moi_hon, moi_hon))

    kiem = _flasher(runner, tmp_path).preflight(anh)
    assert not kiem.ok
    assert "cũ hơn mã nguồn" in kiem.render()
    assert "m.c" in kiem.render()


def test_san_pham_dich_khong_tinh_la_ma_nguon_moi_hon(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """``build/main.c`` sinh ra trong lúc ráp — nó không phải nguồn.

    Không loại trừ thì ảnh sẽ luôn "cũ hơn chính nó", và phép kiểm luôn báo
    động là phép kiểm sẽ bị tắt.
    """
    import os

    sinh_ra = tmp_path / "build" / "main.c"
    sinh_ra.write_text("int main(void){return 0;}\n", encoding="utf-8")
    moi_hon = anh.stat().st_mtime + 10
    os.utime(sinh_ra, (moi_hon, moi_hon))

    assert _flasher(runner, tmp_path).preflight(anh).ok


def test_kiem_dat_thi_bao_commit(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    kiem = _flasher(runner, tmp_path).preflight(anh)
    assert kiem.ok
    assert kiem.commit == "a" * 40


# --------------------------------------------------------------------------
# TC-42c — luôn cần người xác nhận
# --------------------------------------------------------------------------


def test_tu_choi_xac_nhan_thi_khong_nap(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    f = _flasher(runner, tmp_path, confirm=lambda _: False)
    with pytest.raises(FlashNotConfirmed):
        f.run(anh, port="/dev/ttyUSB0", actor="ky-su")


def test_phien_khong_co_terminal_khong_phai_la_dong_y(
    runner: ToolRunner, tmp_path: Path, anh: Path, monkeypatch
) -> None:
    """Cùng nguyên tắc với Human Gate, và ở đây hậu quả là vật lý."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    f = Flasher(runner=runner, repo=_KhoGia(), source_dir=tmp_path)  # confirm=None

    with pytest.raises(FlashNotConfirmed, match="không có terminal"):
        f.run(anh, port="/dev/ttyUSB0", actor="ky-su")


def test_thieu_ten_nguoi_thi_khong_nap(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    with pytest.raises(FlashNotConfirmed, match="chịu trách nhiệm"):
        _flasher(runner, tmp_path).run(anh, port="/dev/ttyUSB0", actor="  ")


def test_thieu_cong_thi_khong_nap(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    with pytest.raises(FlashError, match="Chưa chỉ cổng"):
        _flasher(runner, tmp_path).run(anh, port="", actor="ky-su")


def test_tom_tat_dua_nguoi_xac_nhan_du_thong_tin(
    runner: ToolRunner, tmp_path: Path, anh: Path
) -> None:
    """Người bấm đồng ý phải thấy: ảnh nào, băm gì, commit nào, cổng nào."""
    da_thay: list[str] = []
    f = _flasher(runner, tmp_path, confirm=lambda t: (da_thay.append(t), True)[1])
    f.run(anh, port="/dev/ttyUSB0", actor="ky-su")

    (tom_tat,) = da_thay
    assert "sha256:" in tom_tat
    assert "a" * 40 in tom_tat
    assert "/dev/ttyUSB0" in tom_tat
    assert "ky-su" in tom_tat


def test_nang_luc_flash_cua_pack_bat_buoc_khai_can_xac_nhan() -> None:
    """Engine từ chối nạp một pack lách điều này (FR-DIA-02)."""
    for goc in (PACK_DEMO, REPO / "packs" / "avr"):
        pack = load_manifest(goc)
        assert pack.invocation("flash").requires_confirmation


# --------------------------------------------------------------------------
# TC-42d — nhật ký nạp
# --------------------------------------------------------------------------


def test_nap_xong_ghi_nhat_ky(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    nhat_ky = FlashLog(tmp_path / "flash_log.jsonl")
    f = _flasher(runner, tmp_path, log=nhat_ky)

    ban_ghi = f.run(anh, port="/dev/ttyUSB0", actor="ky-su", programmer="bootloader")

    assert ban_ghi.passed
    (da_ghi,) = nhat_ky.all()
    assert da_ghi.commit == "a" * 40
    assert da_ghi.port == "/dev/ttyUSB0"
    assert da_ghi.actor == "ky-su"
    assert da_ghi.image_digest.startswith("sha256:")
    assert da_ghi.flashed_at


def test_lan_nap_truot_cung_duoc_ghi(runner: ToolRunner, tmp_path: Path, anh: Path) -> None:
    """"Đã thử nạp và trượt" là dữ kiện chẩn đoán y như "đã nạp xong"."""
    import yaml

    goc = tmp_path / "packs" / "hong"
    goc.mkdir(parents=True)
    du_lieu = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["pack"] = "hong"
    du_lieu["capabilities"]["flash"]["command"] = [
        "{python}", "-c", "import sys; sys.exit(1)", "{binary}", "{port}"
    ]
    (goc / "pack.yaml").write_text(yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8")

    r = ToolRunner(
        manifest=load_manifest(goc),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    nhat_ky = FlashLog(tmp_path / "flash_log.jsonl")
    ban_ghi = _flasher(r, tmp_path, log=nhat_ky).run(
        anh, port="/dev/ttyUSB0", actor="ky-su"
    )

    assert not ban_ghi.passed
    assert nhat_ky.all()[0].passed is False
    assert nhat_ky.last_success() is None


def test_nhat_ky_la_append_only(tmp_path: Path) -> None:
    nhat_ky = FlashLog(tmp_path / "flash_log.jsonl")
    for i in range(3):
        nhat_ky.append(
            FlashRecord(
                image=f"fw{i}.hex",
                image_digest="sha256:" + "0" * 64,
                commit="c" * 40,
                port="/dev/ttyUSB0",
                actor="ky-su",
                flashed_at=f"2026-08-29T0{i}:00:00+00:00",
                passed=i != 1,
            )
        )
    ban_ghi = nhat_ky.all()
    assert [r.image for r in ban_ghi] == ["fw0.hex", "fw1.hex", "fw2.hex"]
    assert nhat_ky.last_success().image == "fw2.hex"


def test_nhat_ky_hong_thi_bao_dong_nao(tmp_path: Path) -> None:
    path = tmp_path / "flash_log.jsonl"
    path.write_text('{"image": "a"}\nkhong-phai-json\n', encoding="utf-8")
    with pytest.raises(FlashError, match=":2:"):
        FlashLog(path).all()


# --------------------------------------------------------------------------
# TC-42e — engine không đoán cổng
# --------------------------------------------------------------------------


def test_cli_khong_doan_cong_khi_khong_nhan_ra(tmp_path: Path, monkeypatch) -> None:
    from eaa.cli import CliError, _chon_cong

    monkeypatch.setattr("eaa.serialport.list_ports", lambda **_: [_cong("/dev/ttyS0")])

    class _HoSo:
        raw = {"programmer": {"usb": [{"vid": "2341", "pid": "0043"}]}}

    with pytest.raises(CliError, match="Không nhận ra cổng nào"):
        _chon_cong(tmp_path, _HoSo(), "")


def test_cli_khong_chon_bua_khi_nhieu_cong_cung_khop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "eaa.serialport.list_ports",
        lambda **_: [
            _cong("/dev/ttyACM0", "2341", "0043"),
            _cong("/dev/ttyACM1", "2341", "0043"),
        ],
    )
    from eaa.cli import CliError, _chon_cong

    class _HoSo:
        raw = {"programmer": {"usb": [{"vid": "2341", "pid": "0043"}]}}

    with pytest.raises(CliError, match="2 cổng cùng khớp"):
        _chon_cong(tmp_path, _HoSo(), "")


def test_cong_chi_dinh_tay_duoc_ton_trong(tmp_path: Path) -> None:
    from eaa.cli import _chon_cong

    class _HoSo:
        raw: dict = {}

    assert _chon_cong(tmp_path, _HoSo(), "/dev/ttyUSB9") == "/dev/ttyUSB9"


def test_lenh_flash_khong_co_co_bo_qua_xac_nhan() -> None:
    """Không cờ nào bỏ qua được bốn phép kiểm — CLAUDE.md, FR-DIA-02.

    Kiểm trên chính bộ phân tích tham số của lệnh ``flash`` chứ không quét cả
    tệp: dự án có ``eaa init --force`` hợp lệ, và một phép kiểm quét chuỗi thô
    sẽ vừa báo động nhầm vừa bỏ lọt khi cờ được đặt tên khác.
    """
    from eaa.cli import build_parser

    flash = _bo_phan_tich_con(build_parser(), "flash")
    co = {c for hanh_dong in flash._actions for c in hanh_dong.option_strings}

    assert not co & {"--yes", "-y", "--force", "--skip-confirm", "--no-confirm"}
    assert "--port" in co and "--actor" in co


def _bo_phan_tich_con(parser, ten: str):
    for hanh_dong in parser._actions:
        if isinstance(hanh_dong, argparse._SubParsersAction):
            return hanh_dong.choices[ten]
    raise AssertionError(f"không tìm thấy lệnh con {ten!r}")
