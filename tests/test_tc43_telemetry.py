"""TC-43 — kênh máy đọc thẳng từ mạch qua cổng nối tiếp.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-43a | Khung tin kiểm được | checksum đúng/sai/thiếu/không hex, phần tải không phải JSON — mỗi thứ một lý do riêng |
| TC-43b | Luôn có hạn thời gian | đọc không hạn bị từ chối; mạch câm thì phiên vẫn kết thúc |
| TC-43c | Khung hỏng được ĐẾM, không bị nuốt | tỉ lệ hỏng vượt ngưỡng thì cả phiên bị coi là không tin được |
| TC-43d | Giữ nguyên văn thứ nhận được | bản thô nằm cạnh bản đã lọc; phát lại được không cần mạch |
| TC-43e | Ăn khớp với chẩn đoán sẵn có | dòng ra là JSON từng dòng, đúng thứ DiagnosticSession.parse_telemetry đọc |

Vì sao TC-43c là mục quan trọng nhất ở đây: một phiên đo mà 40% khung hỏng vẫn
cho ra vài con số trông hoàn toàn hợp lý. Sai tốc độ truyền, dây dài quá, nguồn
sụt khi động cơ chạy — cả ba đều biểu hiện như vậy, và cả ba đều sẽ đi thẳng
vào Chương 3 nếu khung hỏng bị bỏ lặng lẽ.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.telemetry import (
    CHECKSUMS,
    Capture,
    FrameSpec,
    SerialTelemetryReader,
    TelemetryError,
    load_frame_spec,
    read_capture,
    verify_frame,
)

REPO = Path(__file__).resolve().parent.parent


def _dong(tai: str, spec: FrameSpec) -> str:
    """Đóng gói một phần tải đúng theo khai báo của dự án."""
    if spec.checksum == "none":
        return tai
    cs = CHECKSUMS[spec.checksum](tai.encode("utf-8"))
    return f"{tai}{spec.separator}{cs:02X}"


#: Dùng cho phần kiểm KHUNG và phần ĐẾM: cửa sổ ổn định bằng 0 để không lẫn
#: hai chuyện với nhau. Hành vi của cửa sổ ổn định được kiểm riêng bên dưới.
XOR8 = FrameSpec(checksum="xor8", settle_ms=0)


# --------------------------------------------------------------------------
# TC-43a — kiểm khung
# --------------------------------------------------------------------------


def test_khung_dung_thi_dat() -> None:
    khung = verify_frame(_dong('{"angle_deg": 1.5}', XOR8), XOR8)
    assert khung.ok
    assert khung.data == {"angle_deg": 1.5}


def test_khong_dung_checksum_thi_lay_ca_dong_lam_phan_tai() -> None:
    spec = FrameSpec(checksum="none")
    assert verify_frame('{"a": 1}', spec).ok


def test_checksum_lech_bi_bat() -> None:
    khung = verify_frame('{"a": 1}*00', XOR8)
    assert not khung.ok
    assert "checksum lệch" in khung.reason


def test_thieu_dau_ngan_checksum() -> None:
    khung = verify_frame('{"a": 1}', XOR8)
    assert not khung.ok
    assert "thiếu dấu" in khung.reason


def test_checksum_khong_phai_hex() -> None:
    khung = verify_frame('{"a": 1}*ZZ', XOR8)
    assert not khung.ok
    assert "không phải hex" in khung.reason


def test_phan_tai_khong_phai_json() -> None:
    khung = verify_frame(_dong("boot ok", XOR8), XOR8)
    assert not khung.ok
    assert "không phải JSON" in khung.reason


def test_json_hong_bi_bat() -> None:
    khung = verify_frame(_dong('{"a": }', XOR8), XOR8)
    assert not khung.ok
    assert "JSON hỏng" in khung.reason


def test_moi_khung_hong_co_ly_do_rieng() -> None:
    """Gộp mọi lỗi thành "khung hỏng" thì mất đúng thứ dùng để sửa."""
    ly_do = {
        verify_frame(d, XOR8).reason
        for d in ('{"a": 1}*00', '{"a": 1}', '{"a": 1}*ZZ', _dong("rac", XOR8))
    }
    assert len(ly_do) == 4


def test_phep_kiem_tong_khong_ho_tro_bi_tu_choi() -> None:
    with pytest.raises(TelemetryError, match="không được hỗ trợ"):
        FrameSpec(checksum="crc32-khong-co")


def test_du_an_mau_khai_dinh_dang_khung() -> None:
    spec = load_frame_spec(REPO / "projects" / "robot_balance" / "diagnostics.yaml")
    assert spec.checksum in CHECKSUMS
    assert spec.baud > 0
    assert 0 < spec.max_bad_ratio < 1


def test_khong_khai_thi_dung_mac_dinh(tmp_path: Path) -> None:
    assert load_frame_spec(tmp_path / "khong-co.yaml") == FrameSpec()


# --------------------------------------------------------------------------
# Cổng giả — thay cho mạch thật
# --------------------------------------------------------------------------


class _CongGia:
    """Cổng nối tiếp giả: trả lần lượt các dòng đã dựng, rồi im lặng."""

    def __init__(self, dong: list[str], *, cham: bool = False) -> None:
        self.dong = list(dong)
        self.da_dong = False
        self.cham = cham

    def readline(self) -> str:
        if not self.dong:
            return ""  # mạch câm — đúng hành vi của pyserial khi hết hạn chờ
        return self.dong.pop(0)

    def close(self) -> None:
        self.da_dong = True


def _doc(dong: list[str], spec: FrameSpec = XOR8, **kw) -> Capture:
    cong = _CongGia(dong)
    doc = SerialTelemetryReader(
        port="/dev/gia", spec=spec, open_port=lambda *_: cong, line_timeout_s=0.01
    )
    kw.setdefault("duration_s", 2.0)
    ban_thu = doc.read(**kw)
    assert cong.da_dong, "cổng phải được đóng dù kết thúc kiểu gì"
    return ban_thu


# --------------------------------------------------------------------------
# TC-43b — luôn có hạn thời gian
# --------------------------------------------------------------------------


def test_doc_khong_han_bi_tu_choi() -> None:
    """"Treo" trông giống hệt "đang đo" — nên không có đường nào đọc vô hạn."""
    doc = SerialTelemetryReader(port="/dev/gia", open_port=lambda *_: _CongGia([]))
    with pytest.raises(TelemetryError, match="treo mãi"):
        doc.read(duration_s=0)


def test_mach_cam_thi_phien_van_ket_thuc() -> None:
    ban_thu = _doc([], duration_s=0.2)
    assert ban_thu.frames == []
    assert "Không nhận được gì" in ban_thu.render()


def test_du_khung_thi_dung_som() -> None:
    tai = [_dong(json.dumps({"n": i}), XOR8) for i in range(10)]
    ban_thu = _doc(tai, max_frames=3, duration_s=5.0)
    assert len(ban_thu.good) == 3
    assert ban_thu.duration_s < 5.0


def test_cong_luon_duoc_dong_ke_ca_khi_hong() -> None:
    class _CongNo:
        def __init__(self) -> None:
            self.da_dong = False

        def readline(self) -> str:
            raise OSError("dây rơi ra")

        def close(self) -> None:
            self.da_dong = True

    cong = _CongNo()
    doc = SerialTelemetryReader(port="/dev/gia", open_port=lambda *_: cong)
    with pytest.raises(OSError):
        doc.read(duration_s=1.0)
    assert cong.da_dong


# --------------------------------------------------------------------------
# TC-43c — khung hỏng được đếm, không bị nuốt
# --------------------------------------------------------------------------


def test_khung_hong_duoc_dem() -> None:
    ban_thu = _doc([_dong('{"a": 1}', XOR8), '{"b": 2}*00'])
    assert len(ban_thu.good) == 1
    assert len(ban_thu.bad) == 1
    assert ban_thu.bad_ratio == 0.5


def test_qua_nhieu_khung_hong_thi_phien_khong_tin_duoc() -> None:
    """Một phiên 40% khung hỏng vẫn cho ra vài con số trông hợp lý."""
    dong = [_dong('{"a": 1}', XOR8)] + ['{"b": 2}*00'] * 4
    ban_thu = _doc(dong)

    assert ban_thu.good, "vẫn có khung đạt"
    assert not ban_thu.trustworthy
    assert "KHÔNG TIN ĐƯỢC" in ban_thu.render()


def test_it_khung_hong_thi_van_dung_duoc() -> None:
    dong = [_dong(json.dumps({"n": i}), XOR8) for i in range(9)] + ['{"x": 1}*00']
    ban_thu = _doc(dong)
    assert ban_thu.trustworthy
    assert ban_thu.bad_ratio == 0.1


def test_bao_cao_neu_nguyen_nhan_pho_bien_nhat() -> None:
    ban_thu = _doc(['{"a": 1}*00'] * 3 + ['{"a": 1}*ZZ'])
    van_ban = ban_thu.render()
    assert "3× checksum lệch" in van_ban


def test_khong_khung_nao_dat_thi_khong_tin_duoc() -> None:
    assert not _doc(['{"a": 1}*00']).trustworthy


# --------------------------------------------------------------------------
# Cửa sổ ổn định — bỏ rác khởi động, GIỮ dữ liệu thật
# --------------------------------------------------------------------------


def test_cua_so_on_dinh_bo_rac_khoi_dong() -> None:
    """Mở cổng nối tiếp làm nhiều bo tự khởi động lại; byte đầu thường là rác."""
    spec = FrameSpec(checksum="xor8", settle_ms=5_000)
    ban_thu = _doc(["rac khoi dong", '{"a": 1}*00'], spec, duration_s=0.3)

    assert ban_thu.frames == [], "rác đầu phiên không được tính là đường truyền hỏng"


def test_cua_so_on_dinh_khong_vut_du_lieu_that() -> None:
    """Khung ĐẠT tới sớm vẫn là dữ liệu thật.

    Lỗi đã mắc khi viết module này: cửa sổ ổn định bỏ theo THỜI GIAN, nên nguồn
    dữ liệu nhanh bị vứt sạch. Nó chỉ được phép bỏ thứ không kiểm được.
    """
    spec = FrameSpec(checksum="xor8", settle_ms=5_000)
    ban_thu = _doc([_dong('{"a": 1}', spec)], spec, duration_s=0.3)

    assert len(ban_thu.good) == 1


# --------------------------------------------------------------------------
# TC-43d — giữ nguyên văn, phát lại được
# --------------------------------------------------------------------------


def test_ghi_ca_ban_loc_va_ban_nguyen_van(tmp_path: Path) -> None:
    ban_thu = _doc([_dong('{"a": 1}', XOR8), "rac dau phien", '{"b": 2}*00'])
    da_loc, tho = ban_thu.write(tmp_path / "thu.jsonl")

    assert json.loads(da_loc.read_text(encoding="utf-8").strip()) == {"a": 1}
    noi_dung_tho = tho.read_text(encoding="utf-8")
    assert "rac dau phien" in noi_dung_tho, "bản nguyên văn phải giữ cả rác"
    assert '{"b": 2}*00' in noi_dung_tho


def test_phat_lai_ban_thu_khong_can_mach(tmp_path: Path) -> None:
    """Cùng vai trò với ReplayClient ở tầng mô hình."""
    goc = _doc([_dong('{"a": 1}', XOR8), '{"b": 2}*00'])
    _, tho = goc.write(tmp_path / "thu.jsonl")

    lai = read_capture(tho, XOR8)
    assert len(lai.good) == len(goc.good)
    assert len(lai.bad) == len(goc.bad)
    assert lai.stream() == goc.stream()


def test_phat_lai_ban_thu_khong_co_thi_bao_ro(tmp_path: Path) -> None:
    with pytest.raises(TelemetryError, match="Không có bản thu"):
        read_capture(tmp_path / "khong-co.raw")


# --------------------------------------------------------------------------
# TC-43e — ăn khớp với chẩn đoán sẵn có
# --------------------------------------------------------------------------


def test_dong_ra_dung_dinh_dang_chan_doan_doc() -> None:
    from eaa.diagnostics import DiagnosticSession

    ban_thu = _doc(
        [
            _dong('{"i2c_devices": ["0x68"]}', XOR8),
            _dong('{"whoami": "0x68"}', XOR8),
            '{"hong": 1}*00',
        ]
    )
    du_lieu = DiagnosticSession.parse_telemetry(ban_thu.stream())

    assert du_lieu["i2c_devices"] == ["0x68"]
    assert du_lieu["whoami"] == "0x68"
    assert "hong" not in du_lieu, "khung sai checksum không được vào kết luận"


def test_khung_sai_checksum_khong_lot_vao_ket_luan() -> None:
    """Kiểm riêng vì đây là chỗ một lỗi thầm lặng sẽ đi thẳng vào Chương 3."""
    ban_thu = _doc([_dong('{"angle_deg": 1.0}', XOR8), '{"angle_deg": 99.0}*00'])
    assert "99" not in ban_thu.stream()


# --------------------------------------------------------------------------
# Ranh giới ba tầng
# --------------------------------------------------------------------------


def test_engine_khong_ghim_toc_do_truyen_cua_du_an() -> None:
    """Tốc độ truyền là hợp đồng giữa firmware và dự án, không phải hằng số engine."""
    ma_nguon = (REPO / "eaa" / "telemetry.py").read_text(encoding="utf-8")
    dong_dinh_nghia = [
        d for d in ma_nguon.splitlines() if "115200" in d and "baud" in d
    ]
    assert len(dong_dinh_nghia) <= 1, (
        "tốc độ truyền chỉ được xuất hiện làm giá trị mặc định của FrameSpec, "
        "không rải khắp engine"
    )
