"""TC-127 — một lượt sinh lại KHÔNG được đánh rơi lời gọi liên module (N-910).

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-167.

Nửa đắt hơn của hợp đồng gọi
-----------------------------

TC-124 canh cái module này HỨA: chữ ký trong header của nó. Bài này canh cái nó
DÙNG. Chuyện đã xảy ra: một vòng vá làm ``app_init()`` mất bốn lời gọi khởi tạo
driver. Firmware câm hoàn toàn, **33 bài kiểm vẫn xanh** — không cổng nào đỏ, vì
không có gì sai. Mã dịch được, chạy được, chỉ không làm gì cả.

Đây là dạng hỏng im lặng theo đúng nghĩa đen: không có thông báo lỗi nào để đọc.

Hai chiều, và chiều "đừng kêu nhầm" nặng hơn
---------------------------------------------

Tách mấy lời gọi ra một hàm phụ rồi gọi hàm phụ ấy là tái cấu trúc ĐÚNG. Một bộ
kiểm kêu ở mỗi lần như thế sẽ bị tắt đi, và lúc ấy nó không bảo vệ được gì nữa.

Nên phép quyết định nằm ở tầm TỆP: lời gọi dời chỗ trong cùng tệp không tính là
mất; chỉ lời gọi biến khỏi tệp mới tính. Số bài canh chiều ấy nhiều hơn số bài
canh chiều bắt lỗi, và đó là cố ý.
"""

from __future__ import annotations

from eaa.contract import loi_goi, mat_loi_goi, than_ham
from eaa.orchestrator import Orchestrator
from eaa.tools.base import CodeArtifact

# Tập hàm công khai của các module KHÁC. Trong đường chạy thật nó được dựng từ
# `src/*.h` trên `main`; ở đây khai thẳng để bài kiểm không phụ thuộc kho Git.
LIEN_MODULE = frozenset({"drv_imu_init", "drv_motor_init", "drv_i2c_init", "pid_reset"})


# -- đọc thân hàm ------------------------------------------------------------


def test_than_ham_lay_dung_ruot_cua_ham() -> None:
    nguon = """
    void app_init(void) {
        drv_i2c_init();
        drv_imu_init();
    }
    """
    than = than_ham(nguon)
    assert set(than) == {"app_init"}
    assert "drv_imu_init();" in than["app_init"]


def test_than_ham_dem_dung_ngoac_long() -> None:
    """Ngoặc lồng phải khớp đúng, nếu không hàm sau bị nuốt vào hàm trước."""
    nguon = """
    void a(void) {
        if (x) { y(); }
        while (z) { w(); }
    }
    void b(void) { q(); }
    """
    than = than_ham(nguon)
    assert set(than) >= {"a", "b"}
    assert "q();" not in than["a"]
    assert "q();" in than["b"]


def test_than_ham_bo_qua_khai_bao_suong() -> None:
    """Khai báo không có thân thuộc về `khai_bao_ham`, không thuộc bộ này."""
    assert than_ham("void f(int a);") == {}


def test_ngoac_nhon_trong_chuoi_khong_lam_lech_phep_dem() -> None:
    """Một `{` trong chuỗi làm lệch phép đếm từ đó tới hết tệp — nếu không bỏ ruột chuỗi."""
    nguon = """
    void a(void) {
        log("mo ngoac { trong chuoi");
    }
    void b(void) { drv_imu_init(); }
    """
    than = than_ham(nguon)
    assert "b" in than, "hàm sau bị nuốt vì dấu ngoặc trong chuỗi"
    assert "drv_imu_init();" in than["b"]


def test_ngoac_nhon_trong_chu_thich_khong_lam_lech() -> None:
    nguon = """
    void a(void) {
        /* } đóng giả */
        drv_i2c_init();
    }
    void b(void) { drv_imu_init(); }
    """
    than = than_ham(nguon)
    assert set(than) >= {"a", "b"}
    assert "drv_i2c_init();" in than["a"]


def test_ham_static_va_con_tro_ham_trong_tham_so() -> None:
    nguon = """
    static void dang_ky(void (*cb)(int), int n) {
        cb(n);
    }
    """
    assert "dang_ky" in than_ham(nguon)


def test_ham_cut_khong_lam_no() -> None:
    """Tệp thiếu dấu đóng: bỏ qua hàm ấy, không ném ngoại lệ."""
    assert than_ham("void a(void) { drv_imu_init();") == {}


# -- đọc lời gọi -------------------------------------------------------------


def test_loi_goi_bo_tu_khoa_dieu_khien() -> None:
    """`if (`, `while (`, `sizeof (` đi liền ngoặc nhưng không phải lời gọi."""
    nguon = """
    void a(void) {
        if (x) { }
        while (y) { }
        for (int i = 0; i < 3; i++) { }
        switch (z) { }
        return (int) sizeof (int);
    }
    """
    assert loi_goi(nguon) == {"a"}


def test_loi_goi_bo_ruot_chuoi() -> None:
    """Một dòng in ra màn hình có chữ `foo(` không phải một lời gọi."""
    nguon = 'void a(void) { log("goi foo( o day"); }'
    assert "foo" not in loi_goi(nguon)
    assert {"a", "log"} <= loi_goi(nguon)


def test_loi_goi_khong_dem_ten_ham_bi_chu_thich() -> None:
    nguon = """
    void a(void) {
        // drv_imu_init();
        drv_i2c_init();
    }
    """
    goi = loi_goi(nguon)
    assert "drv_i2c_init" in goi
    assert "drv_imu_init" not in goi


# -- chiều BẮT ĐƯỢC ----------------------------------------------------------


def test_mat_loi_goi_lien_module_thi_keu() -> None:
    """Chuyện thật: `app_init` mất lời gọi khởi tạo, mọi bài kiểm vẫn xanh."""
    cu = """
    void app_init(void) {
        drv_i2c_init();
        drv_imu_init();
    }
    """
    moi = """
    void app_init(void) {
        drv_i2c_init();
    }
    """
    ra = mat_loi_goi(cu, moi, LIEN_MODULE)
    assert len(ra) == 1
    assert "drv_imu_init()" in ra[0]
    assert "app_init()" in ra[0], "phải nêu tên hàm cũ từng gọi, không chỉ nêu cái bị mất"


def test_mat_nhieu_loi_goi_thi_neu_du_va_theo_thu_tu_on_dinh() -> None:
    cu = """
    void app_init(void) {
        drv_i2c_init();
        drv_imu_init();
        drv_motor_init();
    }
    """
    moi = "void app_init(void) { drv_i2c_init(); }"
    ra = mat_loi_goi(cu, moi, LIEN_MODULE)
    assert len(ra) == 2
    assert ra == sorted(ra), "thứ tự phải ổn định để so hai lượt chạy được với nhau"
    assert "drv_imu_init()" in ra[0] and "drv_motor_init()" in ra[1]


def test_xoa_ca_ham_chua_loi_goi_van_bi_keu() -> None:
    """Việc không còn ai làm vẫn là việc không còn ai làm, dù hàm chứa nó bị xoá."""
    cu = """
    static void khoi_tao(void) { drv_imu_init(); }
    void app_init(void) { khoi_tao(); }
    """
    moi = "void app_init(void) { }"
    ra = mat_loi_goi(cu, moi, LIEN_MODULE)
    assert len(ra) == 1
    assert "drv_imu_init()" in ra[0]
    assert "khoi_tao()" in ra[0]


def test_binh_luan_mot_loi_goi_di_cung_la_mat() -> None:
    """Chú thích lại một lời gọi là bỏ nó đi, chỉ khác cách viết."""
    cu = "void app_init(void) { drv_imu_init(); }"
    moi = "void app_init(void) { /* drv_imu_init(); */ }"
    assert len(mat_loi_goi(cu, moi, LIEN_MODULE)) == 1


def test_khong_neu_duoc_chu_thi_van_bao() -> None:
    """Không tra được ai từng gọi thì vẫn báo — im lặng vì thiếu nửa câu là đổi
    một lỗi thật lấy một dòng đẹp."""
    cu = "drv_imu_init();"  # không nằm trong hàm nào đọc ra được
    moi = ""
    ra = mat_loi_goi(cu, moi, LIEN_MODULE)
    assert len(ra) == 1
    assert "drv_imu_init()" in ra[0]


# -- chiều ĐỪNG KÊU NHẦM -----------------------------------------------------


def test_doi_loi_goi_sang_ham_khac_cung_tep_thi_khong_keu() -> None:
    """Tái cấu trúc ĐÚNG: gom lời gọi vào một hàm phụ rồi gọi hàm phụ ấy."""
    cu = """
    void app_init(void) {
        drv_i2c_init();
        drv_imu_init();
    }
    """
    moi = """
    static void khoi_tao_phan_cung(void) {
        drv_i2c_init();
        drv_imu_init();
    }
    void app_init(void) { khoi_tao_phan_cung(); }
    """
    assert mat_loi_goi(cu, moi, LIEN_MODULE) == []


def test_mat_loi_goi_NOI_BO_thi_khong_keu() -> None:
    """Hàm nội bộ mất đi thường là tái cấu trúc, và nó không sang module nào."""
    cu = "void app_init(void) { tinh_lai(); drv_imu_init(); }"
    moi = "void app_init(void) { drv_imu_init(); }"
    assert mat_loi_goi(cu, moi, LIEN_MODULE) == []


def test_mat_loi_goi_THU_VIEN_C_thi_khong_keu() -> None:
    """`memset` không nằm trong header của module nào — nó ngoài phạm vi bộ này."""
    cu = "void app_init(void) { memset(b, 0, 4); drv_imu_init(); }"
    moi = "void app_init(void) { drv_imu_init(); }"
    assert mat_loi_goi(cu, moi, LIEN_MODULE) == []


def test_them_loi_goi_moi_thi_khong_keu() -> None:
    """Mở rộng cái nó làm là việc bình thường; chỉ thu hẹp mới là mất."""
    cu = "void app_init(void) { drv_imu_init(); }"
    moi = "void app_init(void) { drv_imu_init(); drv_motor_init(); }"
    assert mat_loi_goi(cu, moi, LIEN_MODULE) == []


def test_viet_lai_ca_tep_ma_giu_du_loi_goi_thi_khong_keu() -> None:
    """Đổi tên biến, đổi thứ tự, thêm chú thích — không đụng vào việc nào cả."""
    cu = """
    void app_init(void) {
        drv_i2c_init();
        drv_imu_init();
        pid_reset();
    }
    """
    moi = """
    /* Khởi tạo theo thứ tự bus → cảm biến → điều khiển. */
    void app_init(void) {
        pid_reset();
        drv_imu_init();   // sau bus
        drv_i2c_init();
    }
    """
    assert mat_loi_goi(cu, moi, LIEN_MODULE) == []


def test_tap_quan_tam_rong_thi_khong_bao_gio_keu() -> None:
    """Module đầu tiên của dự án: chưa có module nào khác để mà gọi sang."""
    cu = "void app_init(void) { drv_imu_init(); }"
    assert mat_loi_goi(cu, "", frozenset()) == []


def test_ban_moi_rong_va_tap_quan_tam_co_thi_van_keu() -> None:
    """Phân biệt với bài trên: rỗng vì KHÔNG CÓ GÌ ĐỂ SO khác rỗng vì mất hết."""
    cu = "void app_init(void) { drv_imu_init(); }"
    assert len(mat_loi_goi(cu, "", LIEN_MODULE)) == 1


# -- nối vào vòng lặp --------------------------------------------------------
#
# Hai phương thức dưới đây chỉ dùng `self.repo`, nên gọi được với một kho giả.
# Dựng kho Git thật cho từng bài sẽ đo Git chứ không đo luật đang cần đo.


class KhoGia:
    """Kho tối thiểu: đúng hai câu hỏi mà phép so lời gọi cần hỏi."""

    def __init__(self, tep: dict[str, str], *, no_khi_doc: bool = False) -> None:
        self.tep = tep
        self.no_khi_doc = no_khi_doc

    def files_on_main(self) -> frozenset[str]:
        return frozenset(self.tep)

    def read_on_main(self, duong_dan: str) -> str | None:
        if self.no_khi_doc:
            raise RuntimeError("kho không đọc được")
        return self.tep.get(duong_dan)


class KhoHong:
    def files_on_main(self) -> frozenset[str]:
        raise RuntimeError("chưa có nhánh chính")

    def read_on_main(self, duong_dan: str) -> str | None:
        raise RuntimeError("chưa có nhánh chính")


class OrchGia:
    """Mượn đúng hai phương thức đang cần đo, và không mượn gì thêm.

    Viết ra thành lớp thay vì dựng `Orchestrator` thật là để danh sách này
    thành lời khai: hai phương thức ấy chỉ được phép đụng tới `self.repo`.
    Ngày nào chúng đụng thêm thứ khác, bài kiểm đỏ ngay tại đây.
    """

    _ham_cong_khai_module_khac = Orchestrator._ham_cong_khai_module_khac
    _mat_loi_goi = Orchestrator._mat_loi_goi

    def __init__(self, repo: object) -> None:
        self.repo = repo


def _orch(kho: object) -> OrchGia:
    return OrchGia(kho)


def test_tap_quan_tam_gom_ham_cong_khai_cua_module_KHAC() -> None:
    kho = KhoGia(
        {
            "src/drv_imu.h": "void drv_imu_init(void);\nfloat drv_imu_read(void);",
            "src/logic_pid.h": "void pid_reset(void);",
        }
    )
    ra = Orchestrator._ham_cong_khai_module_khac(_orch(kho), "logic_pid")
    assert ra == frozenset({"drv_imu_init", "drv_imu_read"})
    assert "pid_reset" not in ra, "hàm của CHÍNH module này là việc nội bộ"


def test_tap_quan_tam_bo_qua_tep_khong_phai_header_trong_src() -> None:
    kho = KhoGia(
        {
            "src/drv_imu.h": "void drv_imu_init(void);",
            "src/drv_imu.c": "void ham_trong_c(void) { }",
            "tests/test_drv_imu.py": "def test_x(): pass",
            "packs/avr/khuon.h": "void ham_cua_pack(void);",
        }
    )
    assert Orchestrator._ham_cong_khai_module_khac(_orch(kho), "logic_pid") == frozenset(
        {"drv_imu_init"}
    )


def test_kho_chua_dung_thi_tap_quan_tam_rong_chu_khong_no() -> None:
    """Một phép kiểm phụ trợ không được làm hỏng lượt sinh vì lý do của nó."""
    assert Orchestrator._ham_cong_khai_module_khac(_orch(KhoHong()), "x") == frozenset()


def test_doc_mot_header_that_bai_thi_bo_qua_dung_header_ay() -> None:
    kho = KhoGia({"src/drv_imu.h": "void drv_imu_init(void);"}, no_khi_doc=True)
    assert Orchestrator._ham_cong_khai_module_khac(_orch(kho), "x") == frozenset()


def test_mat_loi_goi_qua_orchestrator_bat_duoc_chuyen_that() -> None:
    kho = KhoGia(
        {
            "src/drv_imu.h": "void drv_imu_init(void);",
            "src/app_balance.c": "void app_init(void) { drv_imu_init(); }",
        }
    )
    artifact = CodeArtifact(files={"src/app_balance.c": "void app_init(void) { }"})
    ra = Orchestrator._mat_loi_goi(_orch(kho), artifact, "app_balance")
    assert len(ra) == 1 and "drv_imu_init()" in ra[0]


def test_module_sinh_lan_dau_thi_khong_co_gi_de_so() -> None:
    kho = KhoGia({"src/drv_imu.h": "void drv_imu_init(void);"})
    artifact = CodeArtifact(files={"src/app_balance.c": "void app_init(void) { }"})
    assert Orchestrator._mat_loi_goi(_orch(kho), artifact, "app_balance") == []


def test_luot_sinh_khong_tra_ve_tep_c_thi_khong_so() -> None:
    kho = KhoGia({"src/app_balance.c": "void app_init(void) { drv_imu_init(); }"})
    artifact = CodeArtifact(files={"src/app_balance.h": "void app_init(void);"})
    assert Orchestrator._mat_loi_goi(_orch(kho), artifact, "app_balance") == []


def test_kho_khong_doc_duoc_thi_khong_so_chu_khong_no() -> None:
    artifact = CodeArtifact(files={"src/app_balance.c": "void app_init(void) { }"})
    assert Orchestrator._mat_loi_goi(_orch(KhoHong()), artifact, "app_balance") == []


# -- báo cáo -----------------------------------------------------------------


def test_hai_hang_vi_pham_di_thanh_hai_loi_gan_dung_tep() -> None:
    """Gộp một dòng thì lớp quy lỗi về tệp của SL-162 mất nửa địa chỉ."""
    bao_cao = Orchestrator._bao_cao_hop_dong(
        ["MẤT   void f(void);"],
        ["MẤT   app_init() không còn gọi drv_imu_init()"],
        "app_balance",
    )
    tep = sorted(e.file for e in bao_cao.errors)
    assert tep == ["src/app_balance.c", "src/app_balance.h"]
    assert bao_cao.metrics["contract_violations"] == 1
    assert bao_cao.metrics["lost_calls"] == 1


def test_chi_mat_loi_goi_thi_bao_cao_van_do_va_van_di_duong_va() -> None:
    bao_cao = Orchestrator._bao_cao_hop_dong(
        [], ["MẤT   app_init() không còn gọi drv_imu_init()"], "app_balance"
    )
    assert bao_cao.passed is False
    assert bao_cao.gate == "contract"
    assert len(bao_cao.errors) == 1
    # Đường VÁ, không phải đường CHẶN — mã của chính nó thì nó sửa được.
    assert not bao_cao.metrics.get("env_error")
    assert not bao_cao.metrics.get("config_error")
    # Và SL-162 không đọc nhầm thành lỗi ngoài phạm vi: `.c` là tệp của nó.
    assert Orchestrator._loi_ngoai_pham_vi(bao_cao, "app_balance") == []


def test_thong_diep_noi_ro_vi_sao_cong_khac_khong_bat_duoc() -> None:
    """Mô hình phải hiểu vì sao "test xanh" không phải bằng chứng ở đây."""
    van_ban = str(
        Orchestrator._bao_cao_hop_dong(
            [], ["MẤT   app_init() không còn gọi drv_imu_init()"], "app_balance"
        ).errors[0]
    )
    assert "src/app_balance.c" in van_ban
    assert "KHÔNG CÒN AI LÀM" in van_ban
    assert "Gọi lại đủ" in van_ban  # đường thoát, không chỉ lời trách
