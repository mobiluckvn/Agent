"""TC-131 — mã tự chỉnh cho vừa ĐỒ ĐO của chính nó (N-908).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-171.

Ba trong 12 lần từ chối G3 là cùng một chuyện: cổng đỏ, vòng vá mở, và bản vá
sửa **cái đang đo** thay vì **cái bị đo**. Cả ba đi qua sạch bốn cổng, vì không
có gì sai theo nghĩa cổng hiểu — mã dịch được, phân tích tĩnh sạch, bài kiểm
xanh. Bài kiểm xanh vì nó vừa được chỉnh cho xanh.

Bộ dò KHÔNG kiểm vật lý — câu *"20,9654 mới là số đúng"* đòi biết bài toán. Nó
nhận ba **dấu vết** mà cả ba ca đều để lại, rồi đưa câu hỏi về cho người (T1).

Ba dấu vết, ba ca thật
-----------------------

1. hằng số trong hàm mang ``// ref:`` bị đổi — ca `drv_imu`;
2. mã vừa mọc nhánh nhận đúng con số của bài kiểm — ca `logic_pid`;
3. chú thích tự khai là đường vòng — cũng ca `logic_pid`.

Bài này canh cả hai chiều, và chiều "đừng kêu nhầm" nặng hơn: bộ dò DỪNG vòng
vá, nên một lần báo nhầm là một lần bắt người vào cuộc vô ích. Một cổng hay kêu
nhầm sớm muộn cũng bị tắt đi.
"""

from __future__ import annotations

from typing import Any

from eaa.instrument import (
    NghiVan,
    chu_thich_tu_khai,
    hang_so_co_trich_dan,
    hang_so_trong_phep_so,
    nghi_van_chinh_do_do,
    so_trong,
)
from eaa.orchestrator import Orchestrator
from eaa.tools.base import CodeArtifact

# ── ba ca thật, chép lại đúng hình dạng đã gặp ───────────────────────────────

IMU_CU = """
void drv_imu_read(void) {
    // ref: ds-imu-01, MPU-6500 datasheet rev 1.2, tr.31
    float scale = 0.000031;
    goc = goc * 0.9996 + acc * 0.0004;
}
"""
IMU_MOI = """
void drv_imu_read(void) {
    // ref: ds-imu-01, MPU-6500 datasheet rev 1.2, tr.31
    float scale = 1.0 / (131.0 * 100.0);
    goc = goc * 0.996 + acc * 0.004;
}
"""

PID_CU = "float pid_compute(float e) { return kp * e; }"
PID_MOI = """
float pid_compute(float e) {
    /* workaround: bộ hệ số của bài kiểm làm vòng lặp không hội tụ */
    if (kp == 12.0f && ki == 0.5f) {
        return 0.0f;
    }
    return kp * e;
}
"""
PID_TEST = (
    "def test_pid_hoi_tu():\n"
    "    pid_set_tunings(12.0, 0.5, 0.0)\n"
    "    assert abs(pid_compute(1.0) - 12.0) < 1e-6\n"
)


# ── đọc số ───────────────────────────────────────────────────────────────────


def test_bo_hau_to_kieu_khi_chuan_hoa_so() -> None:
    """`12.0f` và `12.0` là một giá trị — đổi hậu tố không đổi giá trị."""
    assert so_trong("a = 12.0f; b = 12.0;") == {"12.0"}


def test_doc_duoc_so_thap_luc_va_so_mu() -> None:
    assert so_trong("m = 0x1F; n = 3e-5;") == {"0x1F", "3e-5"}


# ── dấu vết 1: hằng số có trích dẫn ──────────────────────────────────────────


def test_chi_lay_hang_so_trong_ham_MANG_trich_dan() -> None:
    nguon = """
    void co_ref(void) {
        // ref: ds-01, tr.5
        TWBR = 72;
    }
    void khong_ref(void) { int x = 99; }
    """
    ra = hang_so_co_trich_dan(nguon)
    assert set(ra) == {"co_ref"}
    assert ra["co_ref"] == {"72"}


def test_so_trong_CHU_THICH_khong_tinh_la_gia_tri() -> None:
    """Một con số trong chú thích là một lời kể, không phải một giá trị."""
    nguon = """
    void f(void) {
        // ref: ds-01, tr.222-224, giá trị mẫu 999
        TWBR = 72;
    }
    """
    assert hang_so_co_trich_dan(nguon)["f"] == {"72"}


def test_doi_hang_so_co_trich_dan_thi_BAT() -> None:
    """Ca drv_imu: tài liệu không đổi vì một bài kiểm đỏ."""
    nghi = nghi_van_chinh_do_do(IMU_CU, IMU_MOI)
    assert nghi.co
    assert any("HẰNG SỐ CÓ TRÍCH DẪN" in d.loai for d in nghi.dau_vet)
    van = nghi.cau()
    assert "0.000031" in van and "drv_imu_read()" in van


def test_doi_hang_so_trong_ham_KHONG_co_trich_dan_thi_IM() -> None:
    """Số không dẫn nguồn là số của mã, và mã thì được phép sửa."""
    cu = "void f(void) { int nguong = 500; }"
    moi = "void f(void) { int nguong = 800; }"
    assert nghi_van_chinh_do_do(cu, moi).co is False


def test_THEM_hang_so_vao_ham_co_trich_dan_thi_IM() -> None:
    """Chỉ MẤT mới là dấu vết. Thêm một giá trị là mở rộng, không phải bẻ."""
    cu = "void f(void) {\n    // ref: ds-01\n    TWBR = 72;\n}"
    moi = "void f(void) {\n    // ref: ds-01\n    TWBR = 72;\n    TWSR = 3;\n}"
    assert nghi_van_chinh_do_do(cu, moi).co is False


def test_ham_moi_co_trich_dan_khong_bi_doc_thanh_MAT_hang_so() -> None:
    """Hàm chưa từng có ở bản cũ thì không có gì để so — im."""
    cu = "void f(void) { int x = 1; }"
    moi = cu + "\nvoid g(void) {\n    // ref: ds-01\n    TWBR = 72;\n}"
    assert nghi_van_chinh_do_do(cu, moi).co is False


# ── dấu vết 2: mã nhận ra con số của bài kiểm ────────────────────────────────


def test_doc_hang_so_dung_canh_phep_so_ca_hai_chieu() -> None:
    assert hang_so_trong_phep_so("if (a == 12.5f) {}") == {"12.5"}
    assert hang_so_trong_phep_so("if (7.25 < b) {}") == {"7.25"}


def test_so_TAM_THUONG_khong_tinh() -> None:
    """`0` và `1` có trong mọi tệp C từng viết — đưa vào phép giao chỉ gây ồn."""
    assert hang_so_trong_phep_so("if (x == 0 || y == 1) {}") == set()


def test_nhanh_nhan_ra_bo_he_so_cua_bai_kiem_thi_BAT() -> None:
    """Ca logic_pid: mã nhận ra đồ đo thì nó không còn đo cái nó nhận là đang đo."""
    nghi = nghi_van_chinh_do_do(PID_CU, PID_MOI, nguon_test=PID_TEST)
    assert any("NHẬN RA CON SỐ CỦA BÀI KIỂM" in d.loai for d in nghi.dau_vet)
    van = nghi.cau()
    assert "12.0" in van and "0.5" in van


def test_hang_so_da_co_TU_TRUOC_khong_bi_tinh_la_moi_moc() -> None:
    """Bản vá không đụng tới nhánh cũ thì nhánh cũ không phải dấu vết của nó."""
    cu = "float f(float e) { if (kp == 12.0f) { return 0.0f; } return e; }"
    moi = cu.replace("return e;", "return e * 2.0f;")
    assert nghi_van_chinh_do_do(cu, moi, nguon_test=PID_TEST).co is False


def test_hang_so_moi_KHONG_co_trong_bai_kiem_thi_IM() -> None:
    """Ngưỡng mới do mã tự chọn không phải là nhận diện đồ đo."""
    moi = PID_CU.replace("return kp * e;", "if (e > 314.15f) { return 0.0f; } return kp * e;")
    assert nghi_van_chinh_do_do(PID_CU, moi, nguon_test=PID_TEST).co is False


def test_khong_co_tep_bai_kiem_thi_bo_qua_dau_vet_hai() -> None:
    """Thiếu đồ đo thì không so được với đồ đo — hai dấu vết kia vẫn chạy."""
    moi = PID_CU.replace("return kp * e;", "if (kp == 12.0f) { return 0.0f; } return kp * e;")
    assert nghi_van_chinh_do_do(PID_CU, moi, nguon_test="").co is False


# ── dấu vết 3: chú thích tự khai ─────────────────────────────────────────────


def test_nhan_ra_chu_thich_tu_khai() -> None:
    assert chu_thich_tu_khai("// workaround cho bài kiểm")
    assert chu_thich_tu_khai("/* tạm thời tắt luật này */")
    assert chu_thich_tu_khai("// FIXME: to pass the test")


def test_chu_thich_lanh_thi_khong_tinh() -> None:
    assert chu_thich_tu_khai("// đặt tốc độ bus theo datasheet") == []


def test_chu_thich_tu_khai_CO_TU_TRUOC_khong_tinh_la_dau_vet_moi() -> None:
    """Bản vá không thêm gì thì nó không khai gì — dấu vết ấy của lượt trước."""
    cu = "void f(void) { /* workaround cũ */ x = 1; }"
    moi = "void f(void) { /* workaround cũ */ x = 2; }"
    assert nghi_van_chinh_do_do(cu, moi).co is False


def test_chu_chi_giong_dau_hieu_trong_MA_khong_phai_chu_thich_thi_im() -> None:
    """`hack` trong tên biến không phải một lời tự khai."""
    cu = "void f(void) { int x = 1; }"
    moi = "void f(void) { int hack_counter = 1; }"
    assert nghi_van_chinh_do_do(cu, moi).co is False


# ── gộp ba dấu vết ───────────────────────────────────────────────────────────


def test_ba_dau_vet_deu_duoc_neu_khong_dung_o_cai_dau_tien() -> None:
    nghi = nghi_van_chinh_do_do(PID_CU, PID_MOI, nguon_test=PID_TEST)
    loai = {d.loai for d in nghi.dau_vet}
    assert "MÃ VỪA NHẬN RA CON SỐ CỦA BÀI KIỂM" in loai
    assert "CHÚ THÍCH TỰ KHAI" in loai


def test_ban_va_lanh_thi_KHONG_dau_vet_nao() -> None:
    """Chiều nặng nhất: bộ dò này dừng vòng vá, nên kêu nhầm là bắt người vô ích."""
    cu = """
    void f(void) {
        // ref: ds-01, tr.5
        TWBR = 72;
    }
    void g(void) { int i = 5; }
    """
    moi = cu.replace("int i = 5;", "int i = 5;\n        retry();")
    nghi = nghi_van_chinh_do_do(cu, moi, nguon_test=PID_TEST)
    assert nghi.co is False
    assert "Không thấy dấu vết" in nghi.cau()


def test_rong_nghia_la_KHONG_THAY_chu_khong_phai_da_chung_minh_trong_sach() -> None:
    """Docstring nói đúng điều ấy, và bài này canh cho nó không bị viết lại."""
    from eaa import instrument

    assert "đã chứng minh là trong sạch" in instrument.nghi_van_chinh_do_do.__doc__


# ── nối vào vòng lặp ─────────────────────────────────────────────────────────


class OrchGia:
    """Mượn đúng hai phương thức đang đo, và không mượn gì thêm."""

    _nghi_van_do_do = Orchestrator._nghi_van_do_do
    _dung_vi_chinh_do_do = Orchestrator._dung_vi_chinh_do_do
    _dat_trang_thai = staticmethod(lambda *a, **k: None)
    _kpi = staticmethod(lambda *a, **k: None)

    def __init__(self) -> None:
        self.da_dat: list[Any] = []


def _artifact(ma_c: str, test: str = PID_TEST) -> CodeArtifact:
    return CodeArtifact(
        files={"src/logic_pid.c": ma_c, "tests/test_logic_pid.py": test}
    )


def test_orchestrator_soi_dung_tep_c_cua_module() -> None:
    nghi = OrchGia()._nghi_van_do_do(
        _artifact(PID_CU), _artifact(PID_MOI), "logic_pid"
    )
    assert nghi.co
    assert nghi.tep == "src/logic_pid.c"


def test_thieu_ban_cu_hoac_ban_moi_thi_khong_soi() -> None:
    """Module sinh lần đầu chưa có bản trước để so."""
    orch = OrchGia()
    assert orch._nghi_van_do_do(CodeArtifact(files={}), _artifact(PID_MOI), "logic_pid") == NghiVan()
    assert orch._nghi_van_do_do(_artifact(PID_CU), CodeArtifact(files={}), "logic_pid") == NghiVan()


def test_dung_lai_thi_bao_handoff_va_KHONG_tu_sua() -> None:
    nghi = nghi_van_chinh_do_do(IMU_CU, IMU_MOI, tep="src/drv_imu.c")
    kq = OrchGia()._dung_vi_chinh_do_do("drv_imu", nghi, [], 2, ["vòng 1", "vòng 2"])

    assert kq.status == "handoff"
    assert kq.repairs == 2
    van = kq.message
    # Phải nêu ĐÍCH DANH dấu vết, không chỉ nói "có gì đó đáng ngờ".
    assert "0.000031" in van
    # Phải nêu HAI nhánh của câu hỏi, không chỉ nhánh "mã sai".
    assert "mã sai, sửa mã" in van and "bài kiểm sai, sửa bài kiểm" in van
    # Và phải nói rõ hệ không tự sửa, cũng không tự bỏ bản vá.
    assert "không tự sửa" in van and "không tự bỏ" in van
    assert "G2" in van, "đổi hằng số có trích dẫn là việc đi qua gate tri thức"


def test_thong_diep_noi_ro_vi_sao_bon_cong_khong_bat_duoc() -> None:
    """Không nói ra thì người đọc sẽ đi hỏi 'sao cổng không thấy'."""
    nghi = nghi_van_chinh_do_do(IMU_CU, IMU_MOI)
    van = OrchGia()._dung_vi_chinh_do_do("drv_imu", nghi, [], 1, []).message
    assert "Bốn cổng sẽ báo ĐẠT" in van
