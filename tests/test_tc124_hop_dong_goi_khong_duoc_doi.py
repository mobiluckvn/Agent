"""TC-124 — sinh lại một module KHÔNG được đổi giao diện công khai của nó.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-163.

`khoa_pham_vi_tep` (SL-154) canh QUYỀN GHI. Nhưng module sinh lại vẫn chỉ viết
tệp của CHÍNH NÓ — mà đổi một chữ ký trong header của mình là đủ làm mọi module
đã merge gọi tới nó không dịch được. Quyền ghi bị canh, hợp đồng gọi thì không.

SL-162 bắt được chuyện ấy **gián tiếp**, qua một module khác tình cờ gọi tới.
Module chưa ai gọi thì vẫn lọt — và sẽ lọt cho tới đúng lúc có người viết module
gọi tới, tức muộn nhất có thể. Bài này canh phép so THẲNG.

Hai chiều phải giữ cân
-----------------------

Bỏ lọt một hợp đồng đã đổi thì đắt. Nhưng kêu nhầm cũng đắt theo cách khác: một
cổng hay báo nhầm sớm muộn cũng bị tắt đi, và lúc ấy nó không bảo vệ được gì
nữa — kho đã ghi đúng câu này ở luật cổng an toàn của `tool`. Nên bài này canh
cả hai chiều, và số bài canh chiều "đừng kêu nhầm" nhiều hơn.
"""

from __future__ import annotations

from eaa.contract import khai_bao_ham, pha_vo_hop_dong


# -- đọc khai báo ------------------------------------------------------------


def test_bo_ten_tham_so_truoc_khi_so() -> None:
    """Đổi tên tham số không đổi cách gọi — kêu ở đây là kêu nhầm."""
    a = khai_bao_ham("float pid_compute(float angle, float sp, bool run);")
    b = khai_bao_ham("float pid_compute(float goc, float diem_dat, bool chay);")
    assert a == b


def test_khong_cat_nham_tu_khoa_kieu_thanh_ten() -> None:
    """`unsigned int` có hai từ, và từ cuối là KIỂU chứ không phải tên."""
    khai = khai_bao_ham("void f(unsigned int a, long long b, uint8_t c);")
    assert khai["f"] == "void f(unsigned int, long long, uint8_t)"


def test_con_tro_va_mang_so_nguyen_van() -> None:
    """Không tách được thì so nguyên văn — thà kêu thừa còn hơn bỏ lọt."""
    khai = khai_bao_ham("void f(void (*cb)(int), int buf[8]);")
    assert khai["f"] == "void f(void (*cb)(int), int buf[8])"


def test_bo_qua_chu_thich_va_tien_xu_ly() -> None:
    nguon = """
    #ifndef X_H
    #define X_H
    /* mô tả dài
       nhiều dòng */
    void f(int a);   // ghi chú
    #endif
    """
    assert khai_bao_ham(nguon) == {"f": "void f(int)"}


def test_bo_qua_dinh_nghia_co_than_ham() -> None:
    """`static inline` trong header: thân hàm đổi không phải hợp đồng đổi."""
    nguon = "int f(int a);\nstatic inline int g(int a) { return a; }\n"
    assert set(khai_bao_ham(nguon)) == {"f"}


def test_khong_doc_nham_lenh_goi_thanh_khai_bao() -> None:
    assert khai_bao_ham("return f(1);") == {}


# -- phân xử hợp đồng --------------------------------------------------------


CU = """
void  pid_set_tunings(float kp, float ki, float kd);
float pid_compute(float angle, float pid_setpoint, bool is_running);
"""


def test_bo_bot_tham_so_la_PHA() -> None:
    """Chỗ SL-163 nằm — đúng ca đã xảy ra ngày 03/09 với `logic_pid`."""
    moi = """
    void  pid_set_tunings(float kp, float ki, float kd);
    float pid_compute(float angle, float pid_setpoint);
    """
    vi_pham = pha_vo_hop_dong(CU, moi)
    assert len(vi_pham) == 1
    assert vi_pham[0].startswith("ĐỔI")
    assert "pid_compute" in vi_pham[0]


def test_xoa_han_mot_ham_la_PHA() -> None:
    vi_pham = pha_vo_hop_dong(CU, "float pid_compute(float a, float b, bool c);")
    assert len(vi_pham) == 1
    assert vi_pham[0].startswith("MẤT")
    assert "pid_set_tunings" in vi_pham[0]


def test_doi_kieu_tra_ve_la_PHA() -> None:
    """Cùng số tham số nên bộ dịch của module này vẫn xanh — chỉ bên gọi mới đỏ."""
    moi = "void pid_set_tunings(float kp, float ki, float kd);\nint pid_compute(float a, float b, bool c);"
    vi_pham = pha_vo_hop_dong(CU, moi)
    assert len(vi_pham) == 1 and "pid_compute" in vi_pham[0]


def test_doi_KIEU_tham_so_la_PHA() -> None:
    """Cùng số tham số, chỉ đổi `float` thành `int` — dạng lặng lẽ nhất."""
    moi = CU.replace("float pid_compute(float angle", "float pid_compute(int angle")
    assert len(pha_vo_hop_dong(CU, moi)) == 1


# -- và những chiều KHÔNG được kêu -------------------------------------------


def test_them_ham_moi_KHONG_pha() -> None:
    """Mở rộng cái nó làm là việc bình thường; chỉ thu hẹp hay đổi mới là phá."""
    assert pha_vo_hop_dong(CU, CU + "\nvoid pid_reset(void);\n") == []


def test_doi_ten_tham_so_KHONG_pha() -> None:
    moi = CU.replace("float angle, float pid_setpoint", "float goc, float diem_dat")
    assert pha_vo_hop_dong(CU, moi) == []


def test_doi_dinh_dang_va_chu_thich_KHONG_pha() -> None:
    moi = """
    /* Bộ điều khiển PID — theo V3 */
    void pid_set_tunings(
        float kp,
        float ki,
        float kd
    );

    float   pid_compute(float angle, float pid_setpoint, bool is_running);
    """
    assert pha_vo_hop_dong(CU, moi) == []


def test_header_giong_het_KHONG_pha() -> None:
    assert pha_vo_hop_dong(CU, CU) == []


# -- nối vào vòng lặp --------------------------------------------------------


def test_bao_cao_di_vao_duong_VA_chu_khong_chan() -> None:
    """Khác SL-162 có chủ ý: đây là mã của chính nó, và nó sửa được.

    Lỗi ngoài phạm vi là thứ vòng vá KHÔNG có quyền chạm tới nên phải chặn.
    Bỏ sót một tham số thì thêm lại là một lượt vá bình thường — chặn ở đây là
    đòi người làm hộ việc máy làm được.
    """
    from eaa.orchestrator import Orchestrator

    bao_cao = Orchestrator._bao_cao_hop_dong(["MẤT   void f(void);"], "logic_pid")

    assert bao_cao.passed is False
    assert bao_cao.gate == "contract"
    assert bao_cao.metrics["contract_violations"] == 1
    # Không mang dấu env_error/config_error — hai thứ ấy mới là đường CHẶN.
    assert not bao_cao.metrics.get("env_error")
    assert not bao_cao.metrics.get("config_error")
    # Và không bị SL-162 đọc nhầm thành lỗi ngoài phạm vi: header là tệp của
    # chính module này.
    assert Orchestrator._loi_ngoai_pham_vi(bao_cao, "logic_pid") == []


def test_thong_diep_chi_thang_vao_viec_phai_lam() -> None:
    from eaa.orchestrator import Orchestrator

    van_ban = str(
        Orchestrator._bao_cao_hop_dong(
            ["ĐỔI   float pid_compute(float, float, bool);"], "logic_pid"
        ).errors[0]
    )
    assert "src/logic_pid.h" in van_ban
    assert "Giữ NGUYÊN chữ ký cũ" in van_ban
    assert "thêm hàm" in van_ban  # đường thoát hợp lệ, không chỉ lời cấm
