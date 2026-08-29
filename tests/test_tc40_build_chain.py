"""TC-40 — tách dịch khỏi liên kết, và chuỗi ráp ảnh nạp được.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-40a | Module không có `main()` vẫn dịch được | cổng dịch dùng `-c`, sinh tệp đối tượng, KHÔNG liên kết |
| TC-40b | Liên kết là việc riêng | thiếu `main()` thì cổng liên kết trượt — và trượt ở đúng chỗ nó nên trượt |
| TC-40c | Chuỗi ráp đầy đủ | các tệp đối tượng + `main()` → ảnh liên kết → ảnh nạp được |
| TC-40d | Đo kích thước nói rõ tầm | `size_scope` phân biệt "module lẻ" với "cả firmware" |

Lý do nhóm test này tồn tại — một lỗi đã CHẠY THẬT rồi mới lộ ra. Lệnh dịch của
Platform Pack AVR có `-o` mà không có `-c`, nên nó luôn liên kết; và liên kết
thì đòi `main()`. Mọi module driver sinh ra đều sẽ trượt cổng đầu tiên với
*undefined reference to main* — trượt vì một lý do chẳng liên quan gì tới chất
lượng mã nó sinh ra. Lỗi ấy không lộ suốt bốn sprint vì máy phát triển chưa cài
avr-gcc: cổng "không đạt vì thiếu công cụ" che mất "không đạt vì lắp lệnh sai".

Nên nhóm này kiểm ở hai tầng. Pack giả lập chứng minh phần ENGINE lắp đúng, tất
định trên mọi máy. Bộ dịch của máy chủ (`cc`) chứng minh phần SEMANTIC: `-c`
thật sự cho phép dịch một đơn vị không có `main()`, còn liên kết thật sự không.
Không có tầng thứ hai thì bài test chỉ đang xác nhận cái giả lập giống chính nó.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from eaa.platform import ASSEMBLY_CAPABILITIES, CAPABILITIES, load_manifest
from eaa.tools.base import CodeArtifact
from eaa.tools.compile import (
    SCOPE_FIRMWARE,
    SCOPE_MODULE,
    CompileGate,
    LinkGate,
    SizeGate,
)
from eaa.tools.runner import ToolRunner

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


#: Một module driver điển hình: có hàm khởi tạo, KHÔNG có main().
MODULE_KHONG_MAIN = """\
    #include <stdint.h>
    static uint8_t trang_thai;

    void m_init(void)
    {
        trang_thai = 0u;
    }

    uint8_t m_step(uint8_t vao)
    {
        trang_thai = (uint8_t)(trang_thai + vao);
        return trang_thai;
    }
"""

MA_MAIN = """\
    void m_init(void);

    int main(void)
    {
        m_init();
        for (;;) {
        }
        return 0;
    }
"""


def _artifact(**tep: str) -> CodeArtifact:
    return CodeArtifact(files={k: textwrap.dedent(v) for k, v in tep.items()})


# --------------------------------------------------------------------------
# TC-40a — module không có main() vẫn dịch được
# --------------------------------------------------------------------------


def test_module_khong_co_main_van_dich_duoc(runner: ToolRunner, tmp_path: Path) -> None:
    """Đây chính là lỗi đã chạy thật rồi mới lộ ra."""
    bao_cao = CompileGate(runner).run(_artifact(**{"src/m.c": MODULE_KHONG_MAIN}))

    assert bao_cao.passed, f"module driver phải dịch được: {bao_cao.errors}"
    assert (tmp_path / "build" / "m.o").is_file(), "phải sinh tệp ĐỐI TƯỢNG"
    assert not list((tmp_path / "build").glob("*.elf")), "cổng dịch KHÔNG được liên kết"


def test_moi_tep_nguon_thanh_mot_tep_doi_tuong(runner: ToolRunner, tmp_path: Path) -> None:
    bao_cao = CompileGate(runner).run(
        _artifact(
            **{
                "src/a.c": "void a(void) { }\n",
                "src/b.c": "void b(void) { }\n",
            }
        )
    )
    assert bao_cao.passed
    assert bao_cao.metrics["source_files"] == 2
    assert len(bao_cao.metrics["objects"]) == 2
    assert (tmp_path / "build" / "a.o").is_file()
    assert (tmp_path / "build" / "b.o").is_file()


def test_dich_het_moi_nguon_roi_moi_ket_luan(runner: ToolRunner) -> None:
    """Không dừng ở lỗi đầu tiên: prompt vá phải thấy hết lỗi của lượt này.

    Sửa một lỗi rồi lượt sau mới phát hiện lỗi kế tiếp là đốt phí một lần trong
    ba lần của vòng tự sửa.
    """
    bao_cao = CompileGate(runner).run(
        _artifact(
            **{
                "src/a.c": "void a(void) { undeclared_helper(1); }\n",
                "src/b.c": "void b(void) { undeclared_helper(2); }\n",
            }
        )
    )
    assert not bao_cao.passed
    tep_co_loi = {e.file for e in bao_cao.errors if e.file}
    assert len(tep_co_loi) == 2, f"chỉ báo lỗi của một tệp: {tep_co_loi}"


def test_cong_dich_danh_dau_dang_do_tam_module(runner: ToolRunner) -> None:
    bao_cao = CompileGate(runner).run(_artifact(**{"src/m.c": MODULE_KHONG_MAIN}))
    assert bao_cao.metrics["size_scope"] == SCOPE_MODULE


# --------------------------------------------------------------------------
# TC-40b — liên kết là việc riêng, và nó trượt ở đúng chỗ nó nên trượt
# --------------------------------------------------------------------------


def test_lien_ket_thieu_main_thi_truot(runner: ToolRunner) -> None:
    dich = CompileGate(runner).run(_artifact(**{"src/m.c": MODULE_KHONG_MAIN}))
    assert dich.passed

    lien_ket = LinkGate(runner).run(dich.metrics["objects"])

    assert not lien_ket.passed
    assert any("main" in (e.message or "") for e in lien_ket.errors), (
        f"phải nêu đúng nguyên nhân thiếu main: {lien_ket.errors}"
    )


def test_khong_co_tep_doi_tuong_thi_la_loi_cau_hinh(runner: ToolRunner) -> None:
    bao_cao = LinkGate(runner).run([])
    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True


def test_pack_khong_khai_link_thi_bao_loi_chu_khong_im_lang(tmp_path: Path) -> None:
    """Một firmware không liên kết được là một firmware không tồn tại.

    Đó không phải thứ để suy diễn từ sự im lặng của cổng.
    """
    import yaml

    goc = tmp_path / "packs" / "khong-link"
    goc.mkdir(parents=True)
    du_lieu = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["pack"] = "khong-link"
    del du_lieu["capabilities"]["link"]
    (goc / "pack.yaml").write_text(yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8")

    runner = ToolRunner(
        manifest=load_manifest(goc),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    (tmp_path / "x.o").write_text("noi dung", encoding="utf-8")

    bao_cao = LinkGate(runner).run([tmp_path / "x.o"])
    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True
    assert "link" in bao_cao.errors[0].message


# --------------------------------------------------------------------------
# TC-40c — chuỗi ráp đầy đủ tới ảnh nạp được
# --------------------------------------------------------------------------


def test_chuoi_day_du_ra_anh_nap_duoc(runner: ToolRunner, tmp_path: Path) -> None:
    dich = CompileGate(runner).run(
        _artifact(**{"src/m.c": MODULE_KHONG_MAIN, "src/main.c": MA_MAIN})
    )
    assert dich.passed, dich.errors

    lien_ket = LinkGate(runner).run(dich.metrics["objects"])

    assert lien_ket.passed, lien_ket.errors
    assert Path(lien_ket.metrics["binary"]).is_file(), "phải có ảnh liên kết"
    assert Path(lien_ket.metrics["image"]).is_file(), "phải có ảnh nạp được"
    assert lien_ket.metrics["image"].endswith(".hex")
    assert (tmp_path / "build" / "firmware.map").is_file(), "phải giữ bản đồ liên kết"


def test_anh_lien_ket_danh_dau_dang_do_tam_firmware(runner: ToolRunner) -> None:
    dich = CompileGate(runner).run(
        _artifact(**{"src/m.c": MODULE_KHONG_MAIN, "src/main.c": MA_MAIN})
    )
    lien_ket = LinkGate(runner).run(dich.metrics["objects"])
    assert lien_ket.metrics["size_scope"] == SCOPE_FIRMWARE


# --------------------------------------------------------------------------
# TC-40d — cổng đo kích thước
# --------------------------------------------------------------------------


def test_do_kich_thuoc_cong_nhieu_tep_doi_tuong(runner: ToolRunner) -> None:
    """Chiếm dụng của module gồm nhiều đơn vị dịch là TỔNG của chúng."""
    dich = CompileGate(runner).run(
        _artifact(**{"src/a.c": "void a(void) { }\n", "src/b.c": "void b(void) { }\n"})
    )
    cong = SizeGate(runner)

    rieng = [cong.run(o).metrics["flash_bytes"] for o in dich.metrics["objects"]]
    chung = cong.run(dich.metrics["objects"])

    assert chung.metrics["measured_files"] == 2
    assert chung.metrics["flash_bytes"] == sum(rieng)


def test_bao_cao_kich_thuoc_noi_ro_dang_do_tam_nao(runner: ToolRunner) -> None:
    """Trần "Flash < 50%" áp lên một module lẻ là phép kiểm dễ dãi hơn nó trông.

    Người đọc báo cáo phải thấy được điều đó, nên tầm đo đi kèm số đo.
    """
    dich = CompileGate(runner).run(_artifact(**{"src/m.c": MODULE_KHONG_MAIN}))
    cong = SizeGate(runner)

    assert cong.run(dich.metrics["objects"]).metrics["size_scope"] == SCOPE_MODULE
    assert (
        cong.run(dich.metrics["binary"], scope=SCOPE_FIRMWARE).metrics["size_scope"]
        == SCOPE_FIRMWARE
    )


def test_khong_co_gi_de_do_thi_khong_dat(runner: ToolRunner) -> None:
    bao_cao = SizeGate(runner).run([])
    assert not bao_cao.passed


# --------------------------------------------------------------------------
# Interface năng lực
# --------------------------------------------------------------------------


def test_nang_luc_rap_duoc_khai_o_interface() -> None:
    """Năng lực mới phải mở rộng eaa/platform.py, không khai lén trong pack."""
    for ten in ASSEMBLY_CAPABILITIES:
        assert ten in CAPABILITIES


def test_pack_avr_tach_dich_khoi_lien_ket() -> None:
    pack = load_manifest(PACK_AVR)

    dich = pack.invocation("compile").command
    assert "-c" in dich, "lệnh dịch phải có -c, nếu không nó sẽ liên kết"
    assert not any(c.startswith("-Wl,") for c in dich), (
        "cờ của trình liên kết không có việc gì ở lệnh dịch"
    )

    assert pack.has("link"), "pack phải khai báo năng lực liên kết riêng"
    assert pack.has("hex"), "phải có bước đổi sang định dạng nạp được"
    assert "{objects}" in pack.invocation("link").command


# --------------------------------------------------------------------------
# Tầng hai: bộ dịch THẬT của máy chủ chứng minh phần semantic
# --------------------------------------------------------------------------

CC = shutil.which("cc") or shutil.which("gcc")
can_cc = pytest.mark.skipif(CC is None, reason="máy chạy test không có bộ dịch C")


@can_cc
def test_bo_dich_that_dich_duoc_don_vi_khong_co_main(tmp_path: Path) -> None:
    """Chứng minh -c thật sự cho phép dịch một đơn vị không có main()."""
    nguon = tmp_path / "m.c"
    nguon.write_text(textwrap.dedent(MODULE_KHONG_MAIN), encoding="utf-8")

    ket_qua = subprocess.run(
        [CC, "-c", "-o", str(tmp_path / "m.o"), str(nguon)],
        capture_output=True,
        text=True,
    )
    assert ket_qua.returncode == 0, ket_qua.stderr
    assert (tmp_path / "m.o").is_file()


@can_cc
def test_bo_dich_that_khong_lien_ket_duoc_khi_thieu_main(tmp_path: Path) -> None:
    """Và chứng minh vì sao lệnh dịch cũ (có -o, không -c) luôn trượt.

    Đây là lỗi gốc, tái hiện bằng chính bộ dịch của máy chạy test.
    """
    nguon = tmp_path / "m.c"
    nguon.write_text(textwrap.dedent(MODULE_KHONG_MAIN), encoding="utf-8")

    ket_qua = subprocess.run(
        [CC, "-o", str(tmp_path / "m.elf"), str(nguon)],
        capture_output=True,
        text=True,
    )
    assert ket_qua.returncode != 0
    assert "main" in (ket_qua.stderr + ket_qua.stdout).lower()


@can_cc
def test_bo_dich_that_lien_ket_duoc_khi_co_main(tmp_path: Path) -> None:
    for ten, ma in (("m.c", MODULE_KHONG_MAIN), ("main.c", MA_MAIN)):
        (tmp_path / ten).write_text(textwrap.dedent(ma), encoding="utf-8")
        r = subprocess.run(
            [CC, "-c", "-o", str(tmp_path / ten.replace(".c", ".o")), str(tmp_path / ten)],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr

    r = subprocess.run(
        [CC, "-o", str(tmp_path / "fw.elf"), str(tmp_path / "m.o"), str(tmp_path / "main.o")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "fw.elf").is_file()


# --------------------------------------------------------------------------
# Gộp báo cáo không được đánh rơi cờ "không phải lỗi của mã"
# --------------------------------------------------------------------------


def test_gop_bao_cao_giu_co_loi_moi_truong(tmp_path: Path) -> None:
    """Thiếu công cụ phải chặn ngay, không đốt ba lượt tự sửa.

    Lỗi thật khi tách cổng dịch: cổng dịch giờ chạy nhiều lượt và gộp kết quả,
    mà bản gộp đầu tiên bỏ mất ``metrics`` — nên cờ ``env_error`` biến mất và
    Orchestrator tưởng đây là lỗi mã, gửi mô hình vá ba lần một thứ mô hình
    không sửa được.
    """
    import yaml

    goc = tmp_path / "packs" / "hong"
    goc.mkdir(parents=True)
    du_lieu = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["pack"] = "hong"
    du_lieu["capabilities"]["compile"]["command"][0] = "chuong-trinh-khong-ton-tai"
    (goc / "pack.yaml").write_text(yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8")

    runner = ToolRunner(
        manifest=load_manifest(goc),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    bao_cao = CompileGate(runner).run(_artifact(**{"src/m.c": MODULE_KHONG_MAIN}))

    assert not bao_cao.passed
    assert bao_cao.metrics.get("env_error") is True, "cờ môi trường bị đánh rơi khi gộp"


def test_mot_luot_hong_moi_truong_la_ca_cong_hong(runner: ToolRunner, tmp_path: Path) -> None:
    """Cờ được HỢP qua các lượt, không lấy theo lượt cuối."""
    from eaa.tools.base import ToolReport
    from eaa.tools.compile import _gop_bao_cao

    gop = _gop_bao_cao(
        "compile",
        [
            ToolReport(gate="compile", passed=False, metrics={"env_error": True}),
            ToolReport(gate="compile", passed=True, metrics={"exit_code": 0}),
        ],
    )
    assert gop.metrics["env_error"] is True
    assert not gop.passed
