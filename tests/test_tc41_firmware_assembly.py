"""TC-41 — ráp các module đã merge thành firmware chạy được.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-41a | Bản thiết kế ráp là dữ liệu đã kiểm | chu kỳ không gắn hàm, module khai hai lần, `step` thiếu `period_ms` — đều bị chặn lúc nạp |
| TC-41b | Module đã merge không được bỏ quên | merge mà vắng mặt trong bản thiết kế là LỖI, không phải cảnh báo |
| TC-41c | Mã chưa merge không vào được firmware | bản thiết kế nhắc tới module chưa qua G3 thì dừng |
| TC-41d | Vòng lặp chính sinh từ khuôn của pack | engine thay chỗ giữ, không tự viết câu lệnh C |
| TC-41e | Chuỗi ráp đầy đủ | dịch mọi module + main → liên kết → ảnh nạp được → đo lại ở tầm firmware |

Điều nhóm test này giữ, và nó là điều bốn cổng của vòng lặp chuẩn KHÔNG giữ:
bốn cổng ấy nói từng mảnh đúng, không mảnh nào nói rằng ghép lại thì chạy.

Như TC-40, kiểm ở hai tầng. Pack giả lập chứng minh engine lắp đúng, tất định
trên mọi máy. Bộ dịch của máy chủ chứng minh thứ engine sinh ra là **mã C hợp
lệ và liên kết được** — không có tầng ấy thì bài test chỉ đang xác nhận rằng
một chuỗi ký tự bằng chính nó.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from eaa.firmware import (
    AssemblyPlan,
    FirmwareAssembler,
    FirmwareError,
    ScheduledModule,
)
from eaa.platform import load_manifest
from eaa.tools.compile import SCOPE_FIRMWARE, SizeGate
from eaa.tools.runner import ToolRunner

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
PACK_AVR = REPO / "packs" / "avr"


MODULE_C = """\
    #include "{ten}.h"

    static uint8_t dem;

    void {ten}_init(void)
    {{
        dem = 0u;
    }}

    void {ten}_step(void)
    {{
        dem = (uint8_t)(dem + 1u);
    }}
"""

MODULE_H = """\
    #ifndef {HOA}_H
    #define {HOA}_H

    #include <stdint.h>

    void {ten}_init(void);
    void {ten}_step(void);

    #endif
"""


def _viet_module(thu_muc: Path, ten: str) -> None:
    thu_muc.mkdir(parents=True, exist_ok=True)
    (thu_muc / f"{ten}.c").write_text(
        textwrap.dedent(MODULE_C).format(ten=ten), encoding="utf-8"
    )
    (thu_muc / f"{ten}.h").write_text(
        textwrap.dedent(MODULE_H).format(ten=ten, HOA=ten.upper()), encoding="utf-8"
    )


@pytest.fixture()
def runner(tmp_path: Path) -> ToolRunner:
    return ToolRunner(
        manifest=load_manifest(PACK_DEMO),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )


def _plan(tmp_path: Path, **noi_dung: object) -> AssemblyPlan:
    path = tmp_path / "firmware.yaml"
    path.write_text(yaml.safe_dump(noi_dung, allow_unicode=True), encoding="utf-8")
    return AssemblyPlan.load(path)


def _plan_hai_module(tmp_path: Path) -> AssemblyPlan:
    return _plan(
        tmp_path,
        modules=[
            {"id": "mod_a", "init": "mod_a_init", "step": "mod_a_step", "period_ms": 10},
            {"id": "mod_b", "init": "mod_b_init", "step": "mod_b_step", "period_ms": 50},
        ],
    )


# --------------------------------------------------------------------------
# TC-41a — bản thiết kế ráp là dữ liệu đã kiểm
# --------------------------------------------------------------------------


def test_nap_ban_thiet_ke_day_du(tmp_path: Path) -> None:
    plan = _plan_hai_module(tmp_path)
    assert [m.id for m in plan.modules] == ["mod_a", "mod_b"]
    assert plan.scheduled[0].period_ms == 10
    assert plan.tick_ms == 1


def test_thieu_ban_thiet_ke_thi_bao_ro(tmp_path: Path) -> None:
    with pytest.raises(FirmwareError, match="KHAI BÁO chứ không suy đoán"):
        AssemblyPlan.load(tmp_path / "khong-co.yaml")


def test_danh_sach_rong_la_hop_le(tmp_path: Path) -> None:
    """Dự án chưa merge module nào thì bản thiết kế đúng là trống."""
    plan = _plan(tmp_path, modules=[])
    assert plan.modules == ()


def test_chu_ky_khong_gan_ham_bi_chan(tmp_path: Path) -> None:
    """Một chu kỳ không gắn với hàm nào là một dòng không thi hành được."""
    with pytest.raises(FirmwareError, match="period_ms mà không khai"):
        _plan(tmp_path, modules=[{"id": "m", "period_ms": 10}])


def test_chay_dinh_ky_thi_chu_ky_phai_duong(tmp_path: Path) -> None:
    with pytest.raises(FirmwareError, match="phải dương"):
        _plan(tmp_path, modules=[{"id": "m", "step": "m_step", "period_ms": 0}])


def test_module_khai_hai_lan_bi_chan(tmp_path: Path) -> None:
    with pytest.raises(FirmwareError, match="khai hai lần"):
        _plan(
            tmp_path,
            modules=[
                {"id": "m", "step": "m_step", "period_ms": 5},
                {"id": "m", "step": "m_khac", "period_ms": 5},
            ],
        )


def test_module_khong_chay_dinh_ky_van_hop_le(tmp_path: Path) -> None:
    """Thư viện chỉ để module khác gọi — khai step: null thì được."""
    plan = _plan(
        tmp_path,
        modules=[
            {"id": "lib", "init": "lib_init", "step": None},
            {"id": "m", "step": "m_step", "period_ms": 5},
        ],
    )
    assert len(plan.modules) == 2
    assert len(plan.scheduled) == 1
    assert not plan.modules[0].scheduled


# --------------------------------------------------------------------------
# TC-41b / TC-41c — đối chiếu với những gì đã merge
# --------------------------------------------------------------------------


def test_module_da_merge_ma_vang_mat_la_loi(tmp_path: Path) -> None:
    """Không phải cảnh báo.

    Merge nghĩa là mã ấy đã qua đủ cổng và đã được duyệt tại G3. Bỏ quên nó
    nghĩa là firmware nạp xuống mạch thiếu một phần mà mọi bằng chứng đều nói
    là có — và không ai đọc cảnh báo của một lệnh vừa báo thành công.
    """
    plan = _plan(tmp_path, modules=[{"id": "mod_a", "step": "mod_a_step", "period_ms": 10}])
    with pytest.raises(FirmwareError, match="đã merge nhưng không có"):
        plan.check_against_merged(["mod_a", "mod_b"])


def test_khai_step_null_la_du_de_khong_bi_coi_la_bo_quen(tmp_path: Path) -> None:
    plan = _plan(
        tmp_path,
        modules=[
            {"id": "mod_a", "step": "mod_a_step", "period_ms": 10},
            {"id": "lib", "step": None},
        ],
    )
    plan.check_against_merged(["mod_a", "lib"])  # không ném


def test_ma_chua_merge_khong_vao_duoc_firmware(tmp_path: Path) -> None:
    plan = _plan_hai_module(tmp_path)
    with pytest.raises(FirmwareError, match="chưa merge"):
        plan.check_against_merged(["mod_a"])


# --------------------------------------------------------------------------
# TC-41d — vòng lặp chính sinh từ khuôn của pack
# --------------------------------------------------------------------------


def test_sinh_vong_lap_chinh_tu_khuon(runner: ToolRunner, tmp_path: Path) -> None:
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")

    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(
        _plan_hai_module(tmp_path)
    )
    assert bao_cao.passed, bao_cao.errors

    chinh = Path(bao_cao.metrics["main_source"]).read_text(encoding="utf-8")
    assert '#include "mod_a.h"' in chinh
    assert '#include "mod_b.h"' in chinh
    assert "mod_a_init();" in chinh
    assert "{ mod_a_step, 10 }," in chinh
    assert "{ mod_b_step, 50 }," in chinh
    assert "{includes}" not in chinh and "{tasks}" not in chinh


def test_module_khong_chay_dinh_ky_khong_vao_bang_viec(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Nó vẫn được nạp tiêu đề và khởi tạo — chỉ không nằm trong bảng việc."""
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "lib")

    plan = _plan(
        tmp_path,
        modules=[
            {"id": "mod_a", "init": "mod_a_init", "step": "mod_a_step", "period_ms": 10},
            {"id": "lib", "init": "lib_init", "step": None},
        ],
    )
    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(plan)
    assert bao_cao.passed, bao_cao.errors

    chinh = Path(bao_cao.metrics["main_source"]).read_text(encoding="utf-8")
    assert '#include "lib.h"' in chinh
    assert "lib_init();" in chinh
    assert "lib_step" not in chinh


def test_khong_viec_nao_chay_dinh_ky_thi_dung(runner: ToolRunner, tmp_path: Path) -> None:
    _viet_module(tmp_path / "src", "lib")
    plan = _plan(tmp_path, modules=[{"id": "lib", "init": "lib_init", "step": None}])

    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(plan)
    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True


def test_pack_khong_co_khuon_thi_engine_khong_tu_viet(tmp_path: Path) -> None:
    """Khuôn thuộc về nền tảng. Engine thiếu khuôn thì dừng, không ứng biến."""
    goc = tmp_path / "packs" / "khong-khuon"
    goc.mkdir(parents=True)
    du_lieu = yaml.safe_load((PACK_DEMO / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["pack"] = "khong-khuon"
    del du_lieu["firmware"]
    (goc / "pack.yaml").write_text(yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8")

    runner = ToolRunner(
        manifest=load_manifest(goc),
        work_dir=tmp_path,
        base_params={"python": sys.executable, "pack_dir": str(PACK_DEMO)},
    )
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")

    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(
        _plan_hai_module(tmp_path)
    )
    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True
    assert "khuôn" in bao_cao.errors[0].message


# --------------------------------------------------------------------------
# TC-41e — chuỗi ráp đầy đủ
# --------------------------------------------------------------------------


def test_rap_ra_anh_nap_duoc(runner: ToolRunner, tmp_path: Path) -> None:
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")

    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(
        _plan_hai_module(tmp_path)
    )

    assert bao_cao.passed, bao_cao.errors
    assert Path(bao_cao.metrics["binary"]).is_file()
    assert Path(bao_cao.metrics["image"]).is_file()
    assert bao_cao.metrics["module_count"] == 2
    assert bao_cao.metrics["scheduled_count"] == 2


def test_do_kich_thuoc_o_tam_firmware_chu_khong_tam_module(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Đây là lần đầu ngưỡng bộ nhớ được đo trên thứ sẽ nạp xuống mạch."""
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")

    bao_cao = FirmwareAssembler(
        runner=runner,
        source_dir=tmp_path / "src",
        size_gate=SizeGate(runner),
    ).run(_plan_hai_module(tmp_path))

    assert bao_cao.passed, bao_cao.errors
    assert bao_cao.metrics["size_scope"] == SCOPE_FIRMWARE
    assert bao_cao.metrics["flash_bytes"] > 0


def test_vuot_tran_bo_nho_thi_rap_khong_dat(runner: ToolRunner, tmp_path: Path) -> None:
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")

    bao_cao = FirmwareAssembler(
        runner=runner,
        source_dir=tmp_path / "src",
        size_gate=SizeGate(runner, limits={"flash_bytes_max": 1}),
    ).run(_plan_hai_module(tmp_path))

    assert not bao_cao.passed
    assert bao_cao.metrics["stage"] == "size"


def test_module_hong_thi_dung_o_cong_doan_dich(runner: ToolRunner, tmp_path: Path) -> None:
    _viet_module(tmp_path / "src", "mod_a")
    _viet_module(tmp_path / "src", "mod_b")
    (tmp_path / "src" / "mod_b.c").write_text(
        "void mod_b_step(void) { undeclared_helper(1); }\n", encoding="utf-8"
    )

    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "src").run(
        _plan_hai_module(tmp_path)
    )
    assert not bao_cao.passed
    assert bao_cao.metrics["stage"] == "compile"


def test_thieu_ma_nguon_module_thi_bao_loi_cau_hinh(
    runner: ToolRunner, tmp_path: Path
) -> None:
    bao_cao = FirmwareAssembler(runner=runner, source_dir=tmp_path / "trong").run(
        _plan_hai_module(tmp_path)
    )
    assert not bao_cao.passed
    assert bao_cao.metrics["config_error"] is True


# --------------------------------------------------------------------------
# Pack AVR khai đủ khuôn
# --------------------------------------------------------------------------


def test_pack_avr_co_khuon_vong_lap_chinh() -> None:
    pack = load_manifest(PACK_AVR)
    assert pack.firmware is not None
    assert pack.firmware.template.is_file()

    khuon = pack.firmware.template.read_text(encoding="utf-8")
    for cho_giu in ("{includes}", "{init_calls}", "{tasks}"):
        assert cho_giu in khuon, f"khuôn thiếu chỗ giữ {cho_giu}"


def test_khuon_avr_ton_trong_rang_buoc_cung() -> None:
    """Khuôn cũng là mã chạy trên chip, nên nó chịu chung ràng buộc.

    Ngắt chỉ tăng một biến volatile; không cấp phát động; không đệ quy; đọc
    biến nhiều byte trong khối nguyên tử — đúng isr_policy của dự án.
    """
    khuon = (PACK_AVR / "templates" / "main.c.tmpl").read_text(encoding="utf-8")
    assert "malloc" not in khuon and "calloc" not in khuon
    assert "delay" not in khuon
    assert "ATOMIC_BLOCK" in khuon, "đọc bộ đếm nhiều byte phải nguyên tử"
    assert "volatile" in khuon


# --------------------------------------------------------------------------
# Tầng hai: bộ dịch THẬT xác nhận mã sinh ra là C hợp lệ
# --------------------------------------------------------------------------

CC = shutil.which("cc") or shutil.which("gcc")
can_cc = pytest.mark.skipif(CC is None, reason="máy chạy test không có bộ dịch C")


@can_cc
def test_vong_lap_chinh_sinh_ra_dich_va_lien_ket_that(
    runner: ToolRunner, tmp_path: Path
) -> None:
    """Thứ engine sinh ra phải là mã C hợp lệ, không chỉ là chuỗi ký tự đúng dạng."""
    src = tmp_path / "src"
    _viet_module(src, "mod_a")
    _viet_module(src, "mod_b")

    bao_cao = FirmwareAssembler(runner=runner, source_dir=src).run(
        _plan_hai_module(tmp_path)
    )
    assert bao_cao.passed, bao_cao.errors
    chinh = Path(bao_cao.metrics["main_source"])

    doi_tuong = []
    for tep in (src / "mod_a.c", src / "mod_b.c", chinh):
        o = tmp_path / f"that_{tep.stem}.o"
        r = subprocess.run(
            [CC, "-c", "-Wall", "-Wextra", f"-I{src}", "-o", str(o), str(tep)],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"{tep.name} không dịch được:\n{r.stderr}"
        doi_tuong.append(str(o))

    r = subprocess.run(
        [CC, "-o", str(tmp_path / "that.elf"), *doi_tuong], capture_output=True, text=True
    )
    assert r.returncode == 0, f"không liên kết được:\n{r.stderr}"
    assert (tmp_path / "that.elf").is_file()


# --------------------------------------------------------------------------
# Qua CLI: từ module đã merge tới ảnh nạp được
# --------------------------------------------------------------------------


def test_build_qua_cli_sau_khi_merge(tmp_path: Path, monkeypatch, capsys) -> None:
    """Nối trọn: G3 duyệt → module vào firmware/ → `eaa build` ra ảnh nạp được."""
    from eaa import EXIT_OK, EXIT_WAITING_GATE
    from eaa.cli import main

    from tests.test_cli_e2e import dung_moi_truong

    project = dung_moi_truong(tmp_path, monkeypatch)

    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    assert main(["gen", "drv_bus_sensor"]) == EXIT_WAITING_GATE
    assert main(["gate", "approve", "G3"]) == EXIT_OK
    capsys.readouterr()

    # Mô hình đặt tên tệp là module.c chứ không theo id, nên khai rõ nguồn —
    # đúng tình huống mà bản thiết kế ráp có trường 'sources' để xử lý.
    (project / "firmware.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "tick_ms": 1,
                "modules": [
                    {
                        "id": "drv_bus_sensor",
                        "init": "module_init",
                        "step": "module_step",
                        "period_ms": 10,
                        "sources": ["src/module.c"],
                    }
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    assert main(["build"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "drv_bus_sensor" in ra
    assert "mỗi 10 ms" in ra
    assert "Ảnh nạp được" in ra
    assert (project / "firmware" / "build" / "firmware.hex").is_file()


def test_build_chan_khi_module_da_merge_bi_bo_quen(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from eaa import EXIT_ENV_ERROR, EXIT_OK, EXIT_WAITING_GATE
    from eaa.cli import main

    from tests.test_cli_e2e import dung_moi_truong

    project = dung_moi_truong(tmp_path, monkeypatch)

    assert main(["init"]) == EXIT_OK
    assert main(["plan", "add", "drv_bus_sensor", "--uses", "twi,imu"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    main(["gen", "drv_bus_sensor"])
    assert main(["gate", "approve", "G3"]) == EXIT_OK
    capsys.readouterr()

    (project / "firmware.yaml").write_text(
        yaml.safe_dump({"version": 1, "modules": []}, allow_unicode=True),
        encoding="utf-8",
    )

    assert main(["build"]) == EXIT_ENV_ERROR
    assert "đã merge nhưng không có" in capsys.readouterr().err
