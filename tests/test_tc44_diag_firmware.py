"""TC-44 — sinh firmware đo cho từng kịch bản chẩn đoán.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-44a | Ba tầng đúng chỗ | bộ khung ở pack, phần đo ở dự án, engine chỉ ghép bằng LIÊN KẾT |
| TC-44b | Không dựng firmware rỗng | kịch bản chưa khai phần đo thì DỪNG, không sinh một ảnh im lặng |
| TC-44c | Định dạng khung khớp bộ đọc | firmware phát ra đúng thứ `eaa telemetry` đọc được |
| TC-44d | Cảnh báo an toàn theo được tới lúc nạp | thẻ đi kèm ảnh mang checklist của kịch bản chuyển động |

Vì sao TC-44b đáng một mục riêng: một firmware nạp được mà không đo gì sẽ chạy,
sẽ im lặng, và sự im lặng ấy không phân biệt được với "mạch hỏng". Sinh bừa một
ảnh rỗng để lệnh có vẻ thành công là cách nhanh nhất biến công cụ chẩn đoán
thành nguồn kết luận sai.

Và vì sao TC-44c cần bộ dịch thật: bộ khung sinh ra phải là mã C hợp lệ VÀ phải
phát ra đúng khung mà `eaa/telemetry.py` bóc được. Hai nửa ấy do hai tệp khác
nhau giữ, nên chỉ chạy thật mới biết chúng có khớp nhau không.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from eaa.diagnostics import Scenario, ScenarioLibrary
from eaa.firmware import DiagnosticFirmwareBuilder
from eaa.platform import load_manifest
from eaa.telemetry import FrameSpec, load_frame_spec, verify_frame
from eaa.tools.runner import ToolRunner

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
PACK_AVR = REPO / "packs" / "avr"
DU_AN_MAU = REPO / "projects" / "robot_balance"

XOR8 = FrameSpec(checksum="xor8", settle_ms=0)


PHAN_DO = """\
    #include <stdint.h>

    void eaa_emit(const char *json);

    void diag_run(void)
    {
        eaa_emit("{\\"i2c_addresses\\": [\\"0x68\\"]}");
    }
"""


@pytest.fixture()
def runner(tmp_path: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


def _kich_ban(tmp_path: Path, **kw) -> Scenario:
    kw.setdefault("id", "DS-01")
    kw.setdefault("title", "Quét bus")
    if "firmware_template" in kw:
        # Truyền None nghĩa là "kịch bản chưa khai phần đo".
        kw["firmware_template"] = kw["firmware_template"] or ""
    else:
        duong_dan = tmp_path / "diagnostics" / "DS-01.c"
        duong_dan.parent.mkdir(parents=True, exist_ok=True)
        duong_dan.write_text(textwrap.dedent(PHAN_DO), encoding="utf-8")
        kw["firmware_template"] = "diagnostics/DS-01.c"
    return Scenario(**kw)


def _dung(runner: ToolRunner, tmp_path: Path, scenario: Scenario, spec=XOR8):
    return DiagnosticFirmwareBuilder(runner=runner, project_dir=tmp_path).run(
        scenario, spec
    )


# --------------------------------------------------------------------------
# TC-44a — ba tầng đúng chỗ
# --------------------------------------------------------------------------


def test_dung_duoc_firmware_do(runner: ToolRunner, tmp_path: Path) -> None:
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path))

    assert bao_cao.passed, bao_cao.errors
    assert bao_cao.metrics["scenario"] == "DS-01"
    assert Path(bao_cao.metrics["binary"]).is_file()
    assert Path(bao_cao.metrics["image"]).is_file()


def test_bo_khung_va_phan_do_duoc_LIEN_KET_chu_khong_dan_chuoi(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Cả hai đều là mã C thật, nên bộ dịch kiểm được cả hai."""
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path))
    bo_khung = Path(bao_cao.metrics["source"]).read_text(encoding="utf-8")

    assert "void diag_run(void);" in bo_khung, "bộ khung chỉ KHAI BÁO phần đo"
    assert "eaa_emit" in bo_khung
    assert "i2c_addresses" not in bo_khung, "phần đo không được dán vào bộ khung"


def test_engine_chi_thay_cho_giu(runner: ToolRunner, tmp_path: Path) -> None:
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path))
    bo_khung = Path(bao_cao.metrics["source"]).read_text(encoding="utf-8")

    assert '#define EAA_CHECKSUM_XOR8 1' in bo_khung
    assert '"DS-01"' in bo_khung
    for cho_giu in ("{scenario_id}", "{checksum_define}", "{separator}"):
        assert cho_giu not in bo_khung


def test_khong_dung_checksum_thi_khong_sinh_macro(runner: ToolRunner, tmp_path: Path) -> None:
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path), FrameSpec(checksum="none"))
    bo_khung = Path(bao_cao.metrics["source"]).read_text(encoding="utf-8")
    assert "EAA_CHECKSUM_" not in bo_khung.replace("defined(EAA_CHECKSUM_", "")


def test_pack_khong_co_bo_khung_thi_engine_khong_tu_viet(tmp_path: Path) -> None:
    goc = tmp_path / "packs" / "khong-khung"
    goc.mkdir(parents=True)
    du_lieu = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["pack"] = "khong-khung"
    del du_lieu["diagnostics"]
    (goc / "pack.yaml").write_text(yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8")

    r = ToolRunner(
        manifest=load_manifest(goc),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    bao_cao = _dung(r, tmp_path, _kich_ban(tmp_path))

    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True
    assert "bộ khung" in bao_cao.errors[0].message


def test_pack_avr_co_bo_khung_va_hop_dong_dung() -> None:
    pack = load_manifest(PACK_AVR)
    assert pack.diagnostics is not None
    khuon = pack.diagnostics.template.read_text(encoding="utf-8")

    assert "void diag_run(void);" in khuon, "bộ khung phải khai báo hợp đồng"
    assert "eaa_emit" in khuon
    for cho_giu in ("{scenario_id}", "{checksum_define}", "{separator}"):
        assert cho_giu in khuon


def test_phan_do_cua_du_an_o_tang_du_an() -> None:
    """Phần đo biết bus nào, địa chỉ nào — đúng thứ engine không được biết."""
    thu_vien = ScenarioLibrary.load(DU_AN_MAU / "diagnostics.yaml")
    co_phan_do = [s for s in thu_vien.scenarios if s.firmware_template]

    assert co_phan_do, "dự án mẫu phải có ít nhất một kịch bản dựng được"
    for s in co_phan_do:
        tep = DU_AN_MAU / s.firmware_template
        assert tep.is_file(), f"{s.id} trỏ tới {tep} không có"
        ma = tep.read_text(encoding="utf-8")
        assert "void diag_run(void)" in ma, f"{s.id} phải định nghĩa diag_run"
        assert "eaa_emit" in ma


def test_phan_do_khong_cho_vo_han(  ) -> None:
    """Firmware chẩn đoán treo thì không báo được rằng nó treo.

    Đây là chỗ ràng buộc blocking_io của dự án có lý do rõ nhất: một thiết bị
    giữ bus thấp sẽ treo vòng chờ mãi mãi.
    """
    ma = (DU_AN_MAU / "diagnostics" / "DS-01.c").read_text(encoding="utf-8")
    assert "han" in ma and "quá hạn" in ma, "vòng chờ cờ phải có hạn đếm"


# --------------------------------------------------------------------------
# TC-44b — không dựng firmware rỗng
# --------------------------------------------------------------------------


def test_kich_ban_chua_khai_phan_do_thi_dung(runner: ToolRunner, tmp_path: Path) -> None:
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path, firmware_template=None))

    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True
    assert "firmware rỗng" in bao_cao.errors[0].message


def test_phan_do_khai_ma_khong_co_tep_thi_dung(runner: ToolRunner, tmp_path: Path) -> None:
    kb = Scenario(id="DS-09", title="x", firmware_template="diagnostics/khong-co.c")
    bao_cao = _dung(runner, tmp_path, kb)

    assert not bao_cao.passed
    assert "không có" in bao_cao.errors[0].message


def test_phan_do_hong_thi_dung_o_cong_doan_dich(runner: ToolRunner, tmp_path: Path) -> None:
    kb = _kich_ban(tmp_path)
    (tmp_path / "diagnostics" / "DS-01.c").write_text(
        "void diag_run(void) { undeclared_helper(1); }\n", encoding="utf-8"
    )
    bao_cao = _dung(runner, tmp_path, kb)

    assert not bao_cao.passed
    assert bao_cao.metrics["stage"] == "compile"


# --------------------------------------------------------------------------
# TC-44d — cảnh báo an toàn theo được tới lúc nạp
# --------------------------------------------------------------------------


def test_the_kem_anh_mang_checklist_an_toan(runner: ToolRunner, tmp_path: Path) -> None:
    """Một ảnh chẩn đoán làm robot chuyển động trông y hệt một ảnh đo tĩnh."""
    kb = _kich_ban(
        tmp_path,
        id="DS-05",
        motion=True,
        safety_checklist=("Robot đã kê lên giá, bánh không chạm đất",),
    )
    bao_cao = _dung(runner, tmp_path, kb)
    assert bao_cao.passed, bao_cao.errors

    the = Path(str(bao_cao.metrics["image"]) + ".meta.json")
    du_lieu = json.loads(the.read_text(encoding="utf-8"))

    assert du_lieu["scenario"] == "DS-05"
    assert du_lieu["motion"] is True
    assert du_lieu["safety_checklist"] == ["Robot đã kê lên giá, bánh không chạm đất"]


def test_canh_bao_an_toan_vao_toi_man_hinh_xac_nhan(runner: ToolRunner, tmp_path: Path) -> None:
    """Checklist phải hiện lúc người sắp bấm đồng ý, không phải lúc dựng ảnh.

    Giữa hai thời điểm ấy có thể là vài ngày.
    """
    from eaa.cli import _canh_bao_an_toan_cua_anh

    kb = _kich_ban(
        tmp_path, id="DS-05", motion=True, safety_checklist=("Bánh không chạm đất",)
    )
    bao_cao = _dung(runner, tmp_path, kb)
    ghi_chu = _canh_bao_an_toan_cua_anh(Path(bao_cao.metrics["image"]))

    assert any("CHUYỂN ĐỘNG" in d for d in ghi_chu)
    assert any("Bánh không chạm đất" in d for d in ghi_chu)


def test_anh_thuong_khong_co_canh_bao_thua(tmp_path: Path) -> None:
    from eaa.cli import _canh_bao_an_toan_cua_anh

    anh = tmp_path / "firmware.hex"
    anh.write_text(":00000001FF\n", encoding="utf-8")
    assert _canh_bao_an_toan_cua_anh(anh) == []


def test_kich_ban_tinh_thi_the_khong_doi_checklist(runner: ToolRunner, tmp_path: Path) -> None:
    from eaa.cli import _canh_bao_an_toan_cua_anh

    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path))
    ghi_chu = _canh_bao_an_toan_cua_anh(Path(bao_cao.metrics["image"]))

    assert ghi_chu, "vẫn nói rõ đang nạp ảnh của kịch bản nào"
    assert not any("CHUYỂN ĐỘNG" in d for d in ghi_chu)


# --------------------------------------------------------------------------
# TC-44c — bộ dịch thật: mã hợp lệ VÀ khung khớp bộ đọc
# --------------------------------------------------------------------------

CC = shutil.which("cc") or shutil.which("gcc")
can_cc = pytest.mark.skipif(CC is None, reason="máy chạy test không có bộ dịch C")


@can_cc
def test_firmware_do_chay_that_va_phat_dung_khung(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Chạy firmware đo rồi cho `eaa/telemetry.py` bóc chính đầu ra của nó.

    Bộ khung sinh mã và bộ đọc telemetry do hai tệp khác nhau giữ. Chỉ chạy
    thật mới biết checksum một bên tính có khớp bên kia kiểm hay không.
    """
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path))
    assert bao_cao.passed, bao_cao.errors

    bo_khung = Path(bao_cao.metrics["source"])
    phan_do = tmp_path / "diagnostics" / "DS-01.c"

    chay = tmp_path / "diag_that"
    r = subprocess.run(
        [CC, "-Wall", "-Wextra", "-o", str(chay), str(bo_khung), str(phan_do)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"mã sinh ra không dịch được:\n{r.stderr}"

    ra = subprocess.run([str(chay)], capture_output=True, text=True, timeout=10)
    assert ra.returncode == 0, ra.stderr

    khung = [verify_frame(d, XOR8) for d in ra.stdout.splitlines() if d.strip()]
    assert khung, "firmware không phát khung nào"
    assert all(f.ok for f in khung), [f.reason for f in khung if not f.ok]

    du_lieu: dict = {}
    for f in khung:
        du_lieu.update(f.data)
    assert du_lieu["scenario"] == "DS-01", "khung đầu phải nói rõ kịch bản nào"
    assert du_lieu["i2c_addresses"] == ["0x68"]
    assert du_lieu["done"] is True


@can_cc
def test_dinh_dang_khung_theo_khai_bao_cua_du_an(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Đổi phép kiểm tổng ở dự án thì firmware đổi theo, không phải sửa engine."""
    spec = FrameSpec(checksum="sum8", settle_ms=0)
    bao_cao = _dung(runner, tmp_path, _kich_ban(tmp_path), spec)

    chay = tmp_path / "diag_sum8"
    subprocess.run(
        [
            CC, "-o", str(chay),
            str(Path(bao_cao.metrics["source"])),
            str(tmp_path / "diagnostics" / "DS-01.c"),
        ],
        check=True,
        capture_output=True,
    )
    ra = subprocess.run([str(chay)], capture_output=True, text=True, timeout=10)

    khung = [verify_frame(d, spec) for d in ra.stdout.splitlines() if d.strip()]
    assert all(f.ok for f in khung), [f.reason for f in khung if not f.ok]
    # Và bộ đọc cấu hình xor8 phải TỪ CHỐI chính những khung ấy.
    assert not any(verify_frame(d, XOR8).ok for d in ra.stdout.splitlines() if d.strip())


def test_du_an_mau_khai_khung_khop_voi_bo_doc() -> None:
    spec = load_frame_spec(DU_AN_MAU / "diagnostics.yaml")
    khuon = (PACK_AVR / "templates" / "diagnostic.c.tmpl").read_text(encoding="utf-8")
    assert f"EAA_CHECKSUM_{spec.checksum.upper()}" in khuon, (
        "bộ khung của pack không hiện thực phép kiểm tổng mà dự án khai"
    )
