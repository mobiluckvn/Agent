"""TC-15 — hai module demo đi trọn vòng lặp chuẩn, end-to-end.

TC-15 (STP-04): "Chạy thật driver I2C + PID với LLM thật → cả hai module qua đủ
cổng, merge sau G3; KPI đầy đủ cho báo cáo."

**Bộ test này chạy bằng PHÁT LẠI, không gọi API.** Phản hồi được ghi từ một
lượt chạy thật với mô hình đã ghim phiên bản (xem ``tests/fixtures/llm_calls``)
và phát lại từ nhật ký. Điều đó khiến bộ test tất định, chạy được trong CI
không có khóa, và không tốn tiền mỗi lần chạy lại.

Ranh giới phải nói rõ, vì nó quyết định bộ test này chứng minh được cái gì:

* Phát lại chứng minh **quy trình xử lý đúng phản hồi của mô hình thật** —
  bóc tách, chạy chuỗi cổng, dừng ở gate, merge, ghi chỉ số.
* Nó KHÔNG chứng minh **mô hình hôm nay vẫn trả lời như vậy**. Câu ấy chỉ
  chứng minh được bằng một lượt chạy thật, và bằng chứng của lượt chạy ấy nằm
  trong ``llm_calls.jsonl`` của dự án.

Hai câu khác nhau. Trộn chúng lại là tự cho mình một kết luận mạnh hơn dữ liệu.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from eaa import EXIT_OK, EXIT_WAITING_GATE
from eaa.cli import main
from eaa.kpi import COLUMNS, KpiLogger
from eaa.llm.calllog import CallLog
from eaa.state import StateStore
from eaa.vcs import GitRepo
from eaa.versions import Tier, VersionRegistry

REPO = Path(__file__).resolve().parent.parent
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
DU_AN_MAU = REPO / "projects" / "robot_balance"
BAN_GHI = REPO / "tests" / "fixtures" / "llm_calls" / "demo_two_modules.jsonl"

#: Ràng buộc, hồ sơ phần cứng và trích đoạn tài liệu ĐÃ ĐÓNG BĂNG — bản chụp
#: tại thời điểm ghi ``BAN_GHI`` bằng mô hình thật. Xem
#: ``tests/fixtures/e2e_project/README.md`` để biết vì sao chúng không đọc
#: thẳng từ dự án mẫu: phản hồi trong fixture được sinh ra DƯỚI ĐÚNG bộ ràng
#: buộc này, nên ghép ràng buộc mới với phản hồi cũ là dựng một cảnh chưa từng
#: xảy ra.
DAU_VAO_DONG_BANG = REPO / "tests" / "fixtures" / "e2e_project"


@pytest.fixture()
def moi_truong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cài đặt EAA đầy đủ, dùng adapter phát lại thay cho mô hình thật."""
    home = tmp_path / "eaa_home"
    (home / "packs").mkdir(parents=True)
    shutil.copytree(PACK_DEMO, home / "packs" / "demo")
    shutil.copy(REPO / "tools.yaml", home / "tools.yaml")

    project = home / "projects" / "demo_project"
    project.mkdir(parents=True)
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        shutil.copy(DAU_VAO_DONG_BANG / ten, project / ten)
    shutil.copytree(DAU_VAO_DONG_BANG / "datasheets", project / "datasheets")
    # Mô hình mô phỏng KHÔNG vào prompt, nên nó đọc thẳng từ dự án mẫu: đóng
    # băng thứ không ảnh hưởng băm chỉ tạo ra một bản sao nữa để quên cập nhật.
    shutil.copytree(DU_AN_MAU / "sim", project / "sim")

    # Không sửa gì thêm vào constraints.yaml sau khi chép. Trước bản này ở đây
    # có một lệnh thay dòng ``platform:`` — và nó khiến tệp được băm KHÁC tệp
    # nằm trong kho, nên không cách nào đối chiếu bản ghi với đầu vào. Bản đóng
    # băng đã mang sẵn ``platform: demo``.
    # Bộ kiểm nằm trong THƯ MỤC FIRMWARE, nơi bộ sinh mã ghi vào — không phải
    # ở gốc dự án. Cổng `unittests` đọc đúng chỗ ấy từ SL-134; trước đó hai bên
    # trỏ vào hai thư mục khác nhau và chưa lần nào có tệp test thật để lộ ra.
    (project / "firmware" / "tests").mkdir(parents=True, exist_ok=True)
    (project / "firmware" / "tests" / "test_smoke.py").write_text(
        "def test_khung_du_an():\n    assert True\n", encoding="utf-8"
    )

    # Nhật ký lời gọi đã ghi từ lượt chạy thật — nguồn của bộ phát lại.
    shutil.copy(BAN_GHI, project / "llm_calls.jsonl")

    monkeypatch.setenv("EAA_HOME", str(home))
    monkeypatch.setenv("EAA_PROJECT", str(project))
    monkeypatch.setenv("EAA_ACTOR", "Vũ Trí Công")
    monkeypatch.delenv("EAA_LLM_KEY", raising=False)
    return project


def _hai_module(capsys) -> None:
    """Sinh và merge CẢ HAI module, đúng thứ tự lúc ghi bản ghi.

    Thứ tự không phải chi tiết vụn: ``pid_controller`` khai báo phụ thuộc
    ``drv_i2c_mpu6050``, nên lớp interface của prompt chứa tệp tiêu đề của
    module kia. Sinh pid trước khi module kia merge sẽ cho một prompt khác, băm
    khác, và bộ phát lại — vốn cố ý không bịa phản hồi — báo trượt băm.
    """
    _den_pha_D(capsys)
    for module in ("drv_i2c_mpu6050", "pid_controller"):
        assert main(["gen", module]) == EXIT_WAITING_GATE
        assert main(["gate", "approve", "G3"]) == EXIT_OK
    capsys.readouterr()


def _den_pha_D(capsys) -> None:
    assert main(["init", "--provider", "replay", "--model", ""]) == EXIT_OK
    assert main(["plan", "add", "drv_i2c_mpu6050", "--uses", "twi,imu"]) == EXIT_OK
    assert main(["plan", "add", "pid_controller", "--depends-on", "drv_i2c_mpu6050"]) == EXIT_OK
    main(["gate", "approve", "G1"])
    main(["gate", "approve", "G2"])
    capsys.readouterr()


# --------------------------------------------------------------------------
# TC-15 — hai module đi trọn vòng
# --------------------------------------------------------------------------


def test_dau_vao_anh_huong_bam_prompt_deu_da_dong_bang() -> None:
    """TC-15 không được đọc đầu vào-sinh-prompt từ dự án mẫu đang sống.

    Đây là phép kiểm canh chính cái vừa được sửa. Trước đó, ràng buộc, hồ sơ
    phần cứng và trích đoạn tài liệu được chép thẳng từ ``projects/robot_balance``
    — nên mọi lần sửa dự án mẫu đều làm trượt băm prompt và đòi ghi lại fixture
    bằng một lượt gọi API thật, kể cả khi thay đổi ấy chẳng liên quan gì tới
    thứ TC-15 chứng minh.

    Bộ mô phỏng thì vẫn đọc từ dự án mẫu, có chủ ý: nó KHÔNG vào prompt, nên
    đóng băng nó chỉ tạo thêm một bản sao nữa để quên cập nhật.
    """
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        assert (DAU_VAO_DONG_BANG / ten).is_file(), f"thiếu đầu vào đóng băng: {ten}"
    assert list((DAU_VAO_DONG_BANG / "datasheets").glob("*.md")), "thiếu trích đoạn đóng băng"

    # Chỉ soi các dòng THẬT SỰ chép tệp vào dự án thử; các dòng khác nhắc tới
    # tên hằng số (kể cả chính phép kiểm này) không phải thứ đang bàn.
    nguon = Path(__file__).read_text(encoding="utf-8")
    dung_du_an_mau = [
        d.strip()
        for d in nguon.splitlines()
        if "DU_AN_MAU /" in d and d.lstrip().startswith("shutil.")
    ]
    assert dung_du_an_mau == ['shutil.copytree(DU_AN_MAU / "sim", project / "sim")'], (
        "TC-15 chỉ được lấy bộ mô phỏng từ dự án mẫu. Mọi đầu vào khác đi vào "
        "prompt, nên phải lấy từ tests/fixtures/e2e_project/.\n"
        f"Đang lấy thêm: {dung_du_an_mau}"
    )


def test_ban_ghi_mang_du_truy_vet_de_doi_chieu_ve_sau() -> None:
    """Mỗi bản ghi phải nói nó sinh ra dưới mô hình nào và ràng buộc phiên bản nào.

    Cố ý KHÔNG đòi ``constraints_version`` trùng băm tệp hiện tại. Băm nội dung
    phủ toàn bộ tệp — kể cả chú thích và mục ``acceptance`` — trong khi prompt
    chỉ mang ``limits``/``forbidden``/``style``. Đòi trùng sẽ bắt ghi lại
    fixture vì những sửa đổi chứng minh được là không đổi prompt, tức là đúng
    thứ phiền phức mà bản đóng băng này vừa gỡ bỏ.

    Phép kiểm thật nằm ở chính bộ phát lại: nó tra theo BĂM PROMPT và cố ý
    không bịa phản hồi khi trượt.
    """
    ban_ghi = CallLog(BAN_GHI).all()
    assert ban_ghi, "fixture không được rỗng"
    for r in ban_ghi:
        assert r.model, "bản ghi phải nói nó do mô hình nào sinh ra"
        assert r.prompt_hash.startswith("sha256:")
        assert r.constraints_version.startswith("sha256:")


def test_tc15_hai_module_demo_qua_du_cong_va_merge_sau_G3(
    moi_truong: Path, capsys
) -> None:
    _den_pha_D(capsys)

    for module in ("drv_i2c_mpu6050", "pid_controller"):
        assert main(["gen", module]) == EXIT_WAITING_GATE, f"{module} không tới được G3"
        ra = capsys.readouterr().out
        for cong in ("compile", "size", "static", "unittests"):
            assert f"{cong}: ĐẠT" in ra, f"{module} không qua cổng {cong}"

        assert main(["gate", "approve", "G3"]) == EXIT_OK
        assert f"Đã merge {module}" in capsys.readouterr().out

    state = StateStore(moi_truong / "project_state.json").load()
    assert [m.status for m in state.backlog] == ["merged", "merged"]

    repo = GitRepo(moi_truong / "firmware")
    assert repo.current_branch() == "main"
    for ten in ("drv_i2c_mpu6050", "pid_controller"):
        assert (moi_truong / "firmware" / "src" / f"{ten}.c").is_file()


def test_tc15_ma_sinh_ra_dung_dung_chunk_da_nap(moi_truong: Path, capsys) -> None:
    """Bằng chứng cho luận điểm Datasheet Injection của đề án.

    Không kiểm "mã chạy được" — bốn cổng đã kiểm rồi. Kiểm rằng những con số
    trong mã ĐẾN TỪ trích đoạn tài liệu được nạp, chứ không phải từ trí nhớ của
    mô hình. Đó là khác biệt giữa một giá trị tra được và một giá trị đoán.
    """
    _den_pha_D(capsys)
    main(["gen", "drv_i2c_mpu6050"])
    capsys.readouterr()

    ma = (moi_truong / "firmware" / "src" / "drv_i2c_mpu6050.c").read_text(encoding="utf-8")

    # ds-021 nói: f_SCL 400 kHz ở 16 MHz → TWBR = 12, TWPS = 0.
    assert "TWBR = 12" in ma
    # ds-022 nói: phải che ba bit thấp trước khi so mã trạng thái.
    assert "0xF8" in ma, "quên che bit chia trước — đúng lỗi ds-022 cảnh báo"
    # Mọi hàm chạm thanh ghi phải trích dẫn nguồn (FR-RAG-02).
    assert ma.count("// ref: ds-") >= 3


def test_tc15_commit_truy_vet_duoc_ve_prompt_va_mo_hinh(
    moi_truong: Path, capsys
) -> None:
    """NFR-07 trên dữ liệu thật, không phải trên artifact dựng sẵn."""
    _den_pha_D(capsys)
    main(["gen", "drv_i2c_mpu6050"])
    main(["gate", "approve", "G3"])
    capsys.readouterr()

    repo = GitRepo(moi_truong / "firmware")
    thong_diep = repo.commit_message("HEAD^2")

    assert "prompt-hash: sha256:" in thong_diep
    assert "constraints-version: sha256:" in thong_diep
    assert "chunk-ids: ds-" in thong_diep
    assert "gemini" in thong_diep, "phải ghi mô hình đã sinh ra mã"


def test_tc15_kpi_du_cot_cho_chuong_3(moi_truong: Path, capsys) -> None:
    _den_pha_D(capsys)
    for module in ("drv_i2c_mpu6050", "pid_controller"):
        main(["gen", module])
        main(["gate", "approve", "G3"])
    capsys.readouterr()

    kpi = KpiLogger(moi_truong / "kpi_log.csv")
    dong = kpi.rows()
    assert dong
    for r in dong:
        assert list(r.keys()) == list(COLUMNS)

    tom_tat = kpi.summary()
    assert tom_tat["merges"] == 2
    assert sorted(tom_tat["modules"]) == ["drv_i2c_mpu6050", "pid_controller"]
    assert tom_tat["tokens_in_total"] > 0, "thiếu số liệu token thì không tính được chi phí"


def test_tc15_nhat_ky_loi_goi_la_bang_chung_tai_lap(moi_truong: Path, capsys) -> None:
    """Mỗi lời gọi truy về được prompt hash, mô hình, và số token."""
    nhat_ky = CallLog(moi_truong / "llm_calls.jsonl")
    ban_ghi = nhat_ky.all()

    assert ban_ghi, "thiếu bản ghi từ lượt chạy thật"
    assert all(r.prompt_hash.startswith("sha256:") for r in ban_ghi)
    assert all(r.model for r in ban_ghi)
    assert {r.module for r in ban_ghi} >= {"drv_i2c_mpu6050", "pid_controller"}
    # Cùng một băm prompt không được cho hai phản hồi khác nhau.
    assert nhat_ky.drift() == [], "mô hình trôi hành vi giữa các lần ghi"


def test_tc15_khoa_API_khong_can_de_chay_lai(moi_truong: Path, capsys) -> None:
    """Chạy lại toàn bộ thí nghiệm không tốn một lời gọi nào."""
    import os

    assert "EAA_LLM_KEY" not in os.environ
    _den_pha_D(capsys)
    assert main(["gen", "drv_i2c_mpu6050"]) == EXIT_WAITING_GATE


# --------------------------------------------------------------------------
# Nghiệm thu vật lý và quay lui trên dữ liệu thật
# --------------------------------------------------------------------------


def test_nghiem_thu_G4_phong_hang_va_cap_nhat_known_good(
    moi_truong: Path, capsys, tmp_path: Path
) -> None:
    _hai_module(capsys)

    do = tmp_path / "measures.yaml"
    do.write_text(
        "measurements:\n"
        "  - name: goc_nghieng_max\n    value: 0.9\n    unit: '°'\n"
        "  - name: loop_latency\n    value: 8.4\n    unit: ms\n",
        encoding="utf-8",
    )

    assert main(["gate", "approve", "G4"]) == EXIT_OK
    capsys.readouterr()
    assert main(["tune", "pid_controller", "--input", str(do)]) == EXIT_OK
    assert "hw-verified" in capsys.readouterr().out

    kho = VersionRegistry(
        ledger_path=moi_truong / "build_ledger.jsonl",
        lock_path=moi_truong / "known_good.lock",
    )
    assert kho.status("pid_controller")["tier"] == Tier.HW_VERIFIED
    assert kho.known_good_of("pid_controller")


def test_nghiem_thu_khong_dat_roi_quay_lui_giu_nguyen_known_good(
    moi_truong: Path, capsys, tmp_path: Path
) -> None:
    _hai_module(capsys)
    do = tmp_path / "measures.yaml"
    do.write_text(
        "measurements:\n  - name: goc_nghieng_max\n    value: 0.9\n", encoding="utf-8"
    )
    main(["gate", "approve", "G4"])
    main(["tune", "pid_controller", "--input", str(do)])
    capsys.readouterr()

    khoa_truoc = json.loads((moi_truong / "known_good.lock").read_text(encoding="utf-8"))

    assert main(["tune", "pid_controller", "--reject", "dao động ±2,3° vượt ngưỡng"]) != EXIT_OK
    assert main(["rollback", "pid_controller", "--reason", "không đạt nghiệm thu"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "known_good.lock KHÔNG đổi" in ra

    khoa_sau = json.loads((moi_truong / "known_good.lock").read_text(encoding="utf-8"))
    assert khoa_sau == khoa_truoc


def test_report_versions_tra_ban_tot_nhat_kem_so_do(
    moi_truong: Path, capsys, tmp_path: Path
) -> None:
    _hai_module(capsys)
    do = tmp_path / "measures.yaml"
    do.write_text(
        "measurements:\n  - name: goc_nghieng_max\n    value: 0.9\n    unit: '°'\n",
        encoding="utf-8",
    )
    main(["gate", "approve", "G4"])
    main(["tune", "pid_controller", "--input", str(do)])
    capsys.readouterr()

    assert main(["report", "versions"]) == EXIT_OK
    ra = capsys.readouterr().out
    assert "hw-verified" in ra
    assert "goc_nghieng_max=0.9" in ra
    assert "Bản known-good của toàn firmware:" in ra


# --------------------------------------------------------------------------
# Gate G4 và G5 có hồ sơ dựng được
# --------------------------------------------------------------------------


def test_ho_so_G4_neu_TIEU_CHI_truoc_khong_phai_diff(moi_truong: Path, capsys) -> None:
    """G4 không phải chỗ xem lại mã — đó là việc của G3."""
    _hai_module(capsys)

    main(["gate", "show", "G4"])
    ra = capsys.readouterr().out

    assert "TIÊU CHÍ NGHIỆM THU" in ra
    assert "Dung sai góc: ±1.0°" in ra
    assert "khởi động tĩnh" in ra and "kháng nhiễu" in ra
    assert "diff --git" not in ra


def test_ho_so_G5_gom_so_lieu_cho_nguoi_viet_ket_luan(moi_truong: Path, capsys) -> None:
    _hai_module(capsys)

    main(["gate", "show", "G5"])
    ra = capsys.readouterr().out

    assert "lời gọi mô hình" in ra
    assert "prompt bị trôi hành vi" in ra
    assert "Số liệu Chương 3 xuất được" in ra
