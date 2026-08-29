"""TC-07, TC-17 — Tool Layer: chuỗi cổng kiểm chứng.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-07 | Ràng buộc chặn tại static | mã có hàm chặn / cấp phát động / đệ quy không tới được bước commit |
| TC-17 | Trích dẫn bắt buộc | cấu hình thanh ghi mà xóa `// ref:` thì static fail |

Bộ test chạy tiến trình THẬT qua một Platform Pack giả lập (`tests/fixtures/
packs/demo`) mà "công cụ" là kịch bản Python. Cơ chế được kiểm là thật — dựng
argv, mã thoát, quy tắc parse — chỉ có bộ công cụ là giả, nên CI không đòi máy
chạy test phải cài toolchain của một họ vi điều khiển nào.

Bất biến được canh gắt nhất: **thiếu công cụ là KHÔNG ĐẠT.** Một cổng im lặng
cho qua vì không tìm thấy chương trình còn tệ hơn không có cổng — nó tạo cảm
giác đã kiểm chứng (AIS §9).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from eaa.platform import load_manifest
from eaa.tools.base import CodeArtifact, Severity
from eaa.tools.compile import CompileGate, SizeGate, UnsafePathError, write_artifact
from eaa.tools.runner import ConfirmationRequired, ToolExecutionError, ToolRunner
from eaa.tools.static import StaticGate, load_rules
from eaa.tools.unittests import UnitTestGate

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
PACK_AVR = REPO / "packs" / "avr"


@pytest.fixture()
def runner(tmp_path: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


def _artifact(**tep: str) -> CodeArtifact:
    return CodeArtifact(files={k: textwrap.dedent(v) for k, v in tep.items()})


MA_TOT = """\
    #include "m.h"
    void m_init(void)
    {
        static uint8_t n;
        n = 0u;
    }
"""


# --------------------------------------------------------------------------
# Bộ chạy công cụ
# --------------------------------------------------------------------------


def test_chay_cong_cu_that_va_doc_dung_ket_qua(runner: ToolRunner, tmp_path: Path) -> None:
    (tmp_path / "m.c").write_text(MA_TOT, encoding="utf-8")
    bao_cao = runner.run("compile", {"sources": ["m.c"], "output": "build/m.elf"})

    assert bao_cao.passed
    assert bao_cao.metrics["exit_code"] == 0
    assert (tmp_path / "build" / "m.elf").is_file()
    assert bao_cao.duration_s >= 0


def test_nhieu_tep_nguon_duoc_trai_thanh_nhieu_tham_so(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Một danh sách nối bằng dấu cách sẽ thành MỘT tên tệp có dấu cách."""
    for ten in ("a.c", "b.c"):
        (tmp_path / ten).write_text(MA_TOT, encoding="utf-8")
    bao_cao = runner.run("compile", {"sources": ["a.c", "b.c"], "output": "build/x.elf"})

    assert bao_cao.passed
    assert "da dich 2 tep" in bao_cao.raw_output


def test_loi_cua_cong_cu_duoc_boc_thanh_ToolError_co_vi_tri(
    runner: ToolRunner, tmp_path: Path
) -> None:
    (tmp_path / "m.c").write_text("void f(void)\n{\n    undeclared_helper(1);\n}\n", encoding="utf-8")
    bao_cao = runner.run("compile", {"sources": ["m.c"], "output": "build/m.elf"})

    assert not bao_cao.passed
    assert bao_cao.errors[0].file == "m.c"
    assert bao_cao.errors[0].line == 3
    assert "implicit declaration" in bao_cao.errors[0].message


def test_canh_bao_khong_lam_hong_cong(runner: ToolRunner, tmp_path: Path) -> None:
    (tmp_path / "m.c").write_text("void f(void)\n{\n    int unused_x;\n}\n", encoding="utf-8")
    bao_cao = runner.run("compile", {"sources": ["m.c"], "output": "build/m.elf"})

    assert bao_cao.passed
    assert bao_cao.warnings and bao_cao.warnings[0].severity == Severity.WARNING


def test_thieu_cong_cu_la_KHONG_DAT_chu_khong_phai_bo_qua(tmp_path: Path) -> None:
    manifest = load_manifest(PACK_DEMO)
    runner = ToolRunner(
        manifest=manifest,
        work_dir=tmp_path,
        base_params={"python": "chuong-trinh-khong-ton-tai-tren-doi", "pack_dir": str(PACK_DEMO)},
    )
    bao_cao = runner.run("compile", {"sources": ["m.c"], "output": "o.elf"})

    assert not bao_cao.passed
    assert bao_cao.metrics["env_error"] is True
    assert "KHÔNG được coi là đạt" in bao_cao.errors[0].message
    assert "eaa doctor" in bao_cao.errors[0].message


def test_cong_cu_hong_ma_regex_khong_bat_duoc_thi_giu_dau_ra_tho(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Không được im lặng: giữ đầu ra thô và nói rõ quy tắc parse cần chỉnh."""
    bao_cao = runner.run("compile", {"sources": ["khong-co.c"], "output": "o.elf"})
    assert not bao_cao.passed
    assert bao_cao.errors


def test_thieu_tham_so_la_loi_lap_lenh_chu_khong_phai_cong_khong_dat(
    runner: ToolRunner,
) -> None:
    with pytest.raises(ToolExecutionError, match="Thiếu tham số"):
        runner.run("compile", {"sources": ["m.c"]})


def test_nang_luc_can_xac_nhan_khong_chay_khi_chua_co_xac_nhan(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """FR-DIA-02 — kể cả khi người gọi quên hỏi."""
    (tmp_path / "f.elf").write_bytes(b"x")
    with pytest.raises(ConfirmationRequired, match="FR-DIA-02"):
        runner.run("flash", {"binary": "f.elf"})

    bao_cao = runner.run("flash", {"binary": "f.elf"}, confirmed_by="kỹ sư tại G4")
    assert bao_cao.passed


def test_khong_chay_qua_shell(runner: ToolRunner, tmp_path: Path) -> None:
    """Tham số chứa ký tự shell phải được coi là TÊN TỆP, không phải lệnh.

    Chuỗi vẫn xuất hiện trong đầu ra — nhưng xuất hiện trong thông báo "không
    tìm thấy tệp", nghĩa là nó đã được truyền nguyên vẹn làm một phần tử argv
    chứ không bị shell tách ra và thi hành.
    """
    bao_cao = runner.run(
        "compile", {"sources": ["m.c; echo BI_CHEN_LENH"], "output": "build/m.elf"}
    )
    assert not bao_cao.passed
    assert "khong tim thay tep" in bao_cao.raw_output
    assert not (tmp_path / "build" / "m.elf").exists()


def test_available_bao_dung_cong_cu_co_hay_khong(runner: ToolRunner) -> None:
    assert runner.available("compile") is True   # chương trình do tham số quyết định
    assert runner.available("khong-co-nang-luc") is False


# --------------------------------------------------------------------------
# Ghi artifact — chặn đường dẫn không an toàn
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "duong_dan", ["../thoat_ra_ngoai.c", "/tmp/tuyet_doi.c", "a/../../b.c"]
)
def test_duong_dan_thoat_ra_ngoai_bi_chan(tmp_path: Path, duong_dan: str) -> None:
    """Tên tệp cũng do mô hình sinh ra — không được tin."""
    with pytest.raises(UnsafePathError):
        write_artifact(_artifact(**{duong_dan: "int x;"}), tmp_path / "work")


def test_ghi_artifact_tao_du_thu_muc_con(tmp_path: Path) -> None:
    da_ghi = write_artifact(_artifact(**{"src/drv/m.c": "int x;"}), tmp_path)
    assert da_ghi[0].read_text(encoding="utf-8") == "int x;"


# --------------------------------------------------------------------------
# Cổng biên dịch và cổng đo kích thước
# --------------------------------------------------------------------------


def test_cong_bien_dich_di_qua_va_ghi_lai_duong_dan_nhi_phan(runner: ToolRunner) -> None:
    bao_cao = CompileGate(runner).run(_artifact(**{"src/m.c": MA_TOT, "src/m.h": "// h"}))
    assert bao_cao.passed
    assert Path(bao_cao.metrics["binary"]).is_file()


def test_artifact_khong_co_tep_ma_nguon_thi_cong_bao_hong(runner: ToolRunner) -> None:
    bao_cao = CompileGate(runner).run(_artifact(**{"src/m.h": "// chỉ có header"}))
    assert not bao_cao.passed
    assert "không chứa tệp mã nguồn" in bao_cao.errors[0].message


def test_cong_do_kich_thuoc_doi_chieu_nguong_cua_du_an(runner: ToolRunner) -> None:
    bien_dich = CompileGate(runner).run(_artifact(**{"src/m.c": MA_TOT}))
    nhi_phan = bien_dich.metrics["binary"]

    rong_rai = SizeGate(runner, limits={"flash_pct_max": 50, "sram_pct_max": 40})
    assert rong_rai.run(nhi_phan).passed

    chat_hep = SizeGate(runner, limits={"flash_pct_max": 0.01})
    bao_cao = chat_hep.run(nhi_phan)
    assert not bao_cao.passed
    assert "vượt trần" in bao_cao.errors[0].message
    assert "flash_pct_max" in bao_cao.errors[0].message


def test_engine_khong_biet_flash_la_gi_chi_ap_quy_uoc_dat_ten(
    runner: ToolRunner,
) -> None:
    """Thêm một ngưỡng mới chỉ là thêm một dòng YAML, engine không đổi."""
    bien_dich = CompileGate(runner).run(_artifact(**{"src/m.c": MA_TOT}))
    cong = SizeGate(runner, limits={"sram_bytes_min": 10_000_000})
    bao_cao = cong.run(bien_dich.metrics["binary"])

    assert not bao_cao.passed
    assert "dưới sàn" in bao_cao.errors[0].message


def test_nguong_khong_ung_voi_so_lieu_nao_thi_khong_phai_viec_cua_cong_nay(
    runner: ToolRunner,
) -> None:
    bien_dich = CompileGate(runner).run(_artifact(**{"src/m.c": MA_TOT}))
    cong = SizeGate(runner, limits={"control_loop_ms_max": 10})
    assert cong.run(bien_dich.metrics["binary"]).passed


# --------------------------------------------------------------------------
# TC-07 — ràng buộc chặn tại static
# --------------------------------------------------------------------------


@pytest.fixture()
def static_gate(runner: ToolRunner) -> StaticGate:
    return StaticGate(
        runner=runner,
        manifest=runner.manifest,
        forbidden=["delay()", "malloc/new", "recursion", "float_in_isr"],
        limits={"max_module_lines": 300},
    )


def test_tc07_ham_chan_bi_chan(static_gate: StaticGate) -> None:
    bao_cao = static_gate.run(
        _artifact(**{"src/m.c": "void f(void)\n{\n    _delay_ms(100);\n}\n"})
    )
    assert not bao_cao.passed
    assert bao_cao.errors[0].rule_id == "delay()"
    assert bao_cao.errors[0].line == 3


def test_tc07_cap_phat_dong_bi_chan(static_gate: StaticGate) -> None:
    bao_cao = static_gate.run(
        _artifact(**{"src/m.c": "void f(void)\n{\n    char *p = malloc(16);\n}\n"})
    )
    assert not bao_cao.passed
    assert any(e.rule_id == "malloc/new" for e in bao_cao.errors)


def test_tc07_de_quy_bi_chan(static_gate: StaticGate) -> None:
    ma = """\
        uint8_t descend(uint8_t n)
        {
            if (n == 0u) {
                return 0u;
            }
            return descend((uint8_t)(n - 1u));
        }
    """
    bao_cao = static_gate.run(_artifact(**{"src/m.c": ma}))
    assert not bao_cao.passed
    assert any(e.rule_id == "recursion" and "descend" in e.message for e in bao_cao.errors)


def test_ham_khong_de_quy_khong_bi_bao_nham(static_gate: StaticGate) -> None:
    ma = """\
        uint8_t helper(uint8_t n)
        {
            return (uint8_t)(n + 1u);
        }
        uint8_t caller(uint8_t n)
        {
            return helper(n);
        }
    """
    assert static_gate.run(_artifact(**{"src/m.c": ma})).passed


def test_tc07_so_thuc_trong_ngat_bi_chan(static_gate: StaticGate) -> None:
    ma = """\
        ISR(TIMER_COMPA_vect)
        {
            float x = 1.0f;
            (void)x;
        }
    """
    bao_cao = static_gate.run(_artifact(**{"src/m.c": ma}))
    assert any(e.rule_id == "float_in_isr" for e in bao_cao.errors)


def test_so_thuc_ngoai_ngat_khong_bi_chan(static_gate: StaticGate) -> None:
    ma = "void f(void)\n{\n    float x = 1.0f;\n    (void)x;\n}\n"
    assert static_gate.run(_artifact(**{"src/m.c": ma})).passed


def test_ten_ham_bi_cam_trong_chu_thich_khong_tinh_la_vi_pham(
    static_gate: StaticGate,
) -> None:
    """Chú thích giải thích 'vì sao không dùng delay()' là mã tốt, không phải lỗi."""
    ma = """\
        // Không dùng _delay_ms() ở đây vì nó khóa CPU.
        /* malloc() cũng bị cấm trong dự án này. */
        void f(void)
        {
            static uint8_t n;
            n = 0u;
        }
    """
    assert static_gate.run(_artifact(**{"src/m.c": ma})).passed


def test_dieu_cam_khong_co_luat_kiem_lam_cong_bao_hong(runner: ToolRunner) -> None:
    """Ràng buộc không kiểm được là ràng buộc không được thi hành."""
    cong = StaticGate(
        runner=runner,
        manifest=runner.manifest,
        forbidden=["mot_dieu_cam_pack_chua_biet"],
    )
    bao_cao = cong.run(_artifact(**{"src/m.c": MA_TOT}))

    assert not bao_cao.passed
    assert bao_cao.errors[0].rule_id == "missing-rule"
    assert "không có luật nào phát hiện" in bao_cao.errors[0].message


def test_vuot_tran_do_dai_module_bi_chan(runner: ToolRunner) -> None:
    """AIS §2: kỷ luật độ dài cưỡng chế ở đây, không dựa vào trần token."""
    cong = StaticGate(runner=runner, manifest=runner.manifest, limits={"max_module_lines": 10})
    bao_cao = cong.run(_artifact(**{"src/m.c": "int x;\n" * 50}))

    assert not bao_cao.passed
    assert any(e.rule_id == "max-module-lines" for e in bao_cao.errors)


def test_cong_cu_phan_tich_tinh_ngoai_cung_duoc_chay(static_gate: StaticGate) -> None:
    """Luật nội bộ thi hành ràng buộc đề án; công cụ ngoài bắt phần còn lại."""
    ma = "void f(void)\n{\n    goto cuoi;\ncuoi:\n    return;\n}\n"
    bao_cao = static_gate.run(_artifact(**{"src/m.c": ma}))

    assert not bao_cao.passed
    assert any("cong cu ngoai" in e.message for e in bao_cao.errors)


# --------------------------------------------------------------------------
# TC-17 — trích dẫn bắt buộc
# --------------------------------------------------------------------------


MA_CO_THANH_GHI = """\
    #include "m.h"

    void m_init(void)
    {
        REG_ALPHA = 12u;
        REG_BETA |= (1u << 2);
    }
"""


def _cong_trich_dan(runner: ToolRunner, **ghi_de) -> StaticGate:
    mac_dinh = dict(
        runner=runner,
        manifest=runner.manifest,
        registers=["REG_ALPHA", "REG_BETA"],
        allowed_chunk_ids=["ds-021", "ds-022"],
    )
    mac_dinh.update(ghi_de)
    return StaticGate(**mac_dinh)


def test_tc17_xoa_trich_dan_thi_static_fail(runner: ToolRunner) -> None:
    bao_cao = _cong_trich_dan(runner).run(_artifact(**{"src/m.c": MA_CO_THANH_GHI}))

    assert not bao_cao.passed
    loi = next(e for e in bao_cao.errors if e.rule_id == "ref-citation")
    assert "m_init" in loi.message
    assert "REG_ALPHA" in loi.message and "REG_BETA" in loi.message


def test_tc17_co_trich_dan_thi_di_qua(runner: ToolRunner) -> None:
    ma = MA_CO_THANH_GHI.replace(
        "void m_init(void)", "// ref: ds-021, tr.222\nvoid m_init(void)"
    )
    assert _cong_trich_dan(runner).run(_artifact(**{"src/m.c": ma})).passed


def test_trich_dan_ben_trong_than_ham_cung_duoc_chap_nhan(runner: ToolRunner) -> None:
    ma = MA_CO_THANH_GHI.replace("    REG_ALPHA", "    // ref: ds-021\n    REG_ALPHA")
    assert _cong_trich_dan(runner).run(_artifact(**{"src/m.c": ma})).passed


def test_trich_dan_toi_chunk_khong_co_that_bi_chan(runner: ToolRunner) -> None:
    """Trích dẫn một mã chunk không tồn tại là ảo giác CÓ đóng dấu."""
    ma = MA_CO_THANH_GHI.replace(
        "void m_init(void)", "// ref: ds-999\nvoid m_init(void)"
    )
    bao_cao = _cong_trich_dan(runner).run(_artifact(**{"src/m.c": ma}))

    assert not bao_cao.passed
    assert any(e.rule_id == "ref-unknown-chunk" for e in bao_cao.errors)
    assert "ds-999" in bao_cao.errors[0].message


def test_ham_khong_cham_thanh_ghi_thi_khong_doi_trich_dan(runner: ToolRunner) -> None:
    ma = "void helper(void)\n{\n    static uint8_t n;\n    n = 0u;\n}\n"
    assert _cong_trich_dan(runner).run(_artifact(**{"src/m.c": ma})).passed


def test_khong_biet_thanh_ghi_nao_thi_khong_kiem_trich_dan(runner: ToolRunner) -> None:
    """Engine không tự nghĩ ra tên thanh ghi — danh sách do đồ thị cấp."""
    cong = _cong_trich_dan(runner, registers=[])
    assert cong.run(_artifact(**{"src/m.c": MA_CO_THANH_GHI})).passed


# --------------------------------------------------------------------------
# Nạp luật của pack
# --------------------------------------------------------------------------


def test_nap_luat_cua_pack_avr_that() -> None:
    luat = load_rules(PACK_AVR / "rules")
    for ten in ("delay()", "malloc/new", "recursion", "float_in_isr"):
        assert ten in luat, f"pack AVR thiếu luật cho điều cấm {ten!r}"
    assert luat["recursion"].kind == "self_recursion"


def test_moi_dieu_cam_cua_du_an_mau_deu_co_luat_trong_pack_avr() -> None:
    """Bảo hiểm chống trôi: thêm điều cấm vào dự án mà quên viết luật thì kêu."""
    from eaa.kb import Constraints

    rang_buoc = Constraints.load(REPO / "projects" / "robot_balance" / "constraints.yaml")
    luat = load_rules(PACK_AVR / "rules")
    thieu = [c for c in rang_buoc.forbidden if c not in luat]
    assert not thieu, f"dự án mẫu cấm {thieu} nhưng pack AVR không có luật kiểm"


def test_luat_thieu_id_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text("rules:\n  - pattern: 'x'\n", encoding="utf-8")
    with pytest.raises(Exception, match="thiếu 'id'"):
        load_rules(tmp_path)


def test_luat_kind_la_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text(
        "rules:\n  - id: a\n    kind: tu_nghi_ra\n", encoding="utf-8"
    )
    with pytest.raises(Exception, match="kind"):
        load_rules(tmp_path)


def test_luat_regex_hong_bi_bat_luc_nap(tmp_path: Path) -> None:
    (tmp_path / "r.yaml").write_text(
        "rules:\n  - id: a\n    pattern: '([unclosed'\n", encoding="utf-8"
    )
    with pytest.raises(Exception, match="biểu thức"):
        load_rules(tmp_path)


# --------------------------------------------------------------------------
# Cổng kiểm thử đơn vị
# --------------------------------------------------------------------------


def test_chua_co_test_nao_la_KHONG_DAT(tmp_path: Path) -> None:
    """'Chưa có gì để chạy' không phải là 'đã kiểm chứng'."""
    bao_cao = UnitTestGate(tests_dir=tmp_path / "tests", work_dir=tmp_path).run()
    assert not bao_cao.passed
    assert "không phải là" in bao_cao.errors[0].message


def test_bo_test_dat_thi_cong_dat(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=tmp_path).run()
    assert bao_cao.passed
    assert bao_cao.metrics["passed"] == 1


def test_bo_test_hong_thi_cong_hong_va_giu_lai_dong_huu_ich(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_hong():\n    assert 1 == 2\n", encoding="utf-8")

    bao_cao = UnitTestGate(tests_dir=tests, work_dir=tmp_path).run()
    assert not bao_cao.passed
    assert bao_cao.metrics["failed"] == 1
    assert "test_hong" in bao_cao.errors[0].message
