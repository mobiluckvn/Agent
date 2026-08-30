"""Ghi lại bản ghi lời gọi mô hình dùng cho TC-15.

Chạy đúng dãy lệnh mà ``tests/test_tc15_e2e.py`` chạy, nhưng với MÔ HÌNH THẬT,
rồi lưu ``llm_calls.jsonl`` thành fixture. Bộ test sau đó phát lại từ fixture
ấy nên chạy tất định, không tốn API, và chạy được trong CI không có khóa.

**Vì sao phải ghi từ chính môi trường test, không ghi từ một dự án tùy ý.**
Băm prompt phủ toàn bộ ngữ cảnh: phiên bản ràng buộc, nội dung chunk, tệp
tiêu đề của module phụ thuộc. Ghi ở một dự án dựng hơi khác sẽ cho băm khác,
và bộ phát lại — vốn cố ý KHÔNG bịa phản hồi khi trượt băm — sẽ báo thiếu bản
ghi. Dựng môi trường bằng đúng đoạn mã mà bộ test dùng thì băm khớp theo cấu
trúc, không nhờ may.

Cách dùng::

    export EAA_LLM_KEY=...          # hoặc điền vào .env
    .venv/bin/python scripts/record_e2e_fixture.py

Chạy lại khi nào: khi ràng buộc, chunk tài liệu, hồ sơ phần cứng hay cách lắp
prompt thay đổi — tức khi băm prompt đổi. Bộ test sẽ báo trượt băm và chỉ ra
điều đó.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from eaa.cli import load_env_file, main  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "llm_calls" / "demo_two_modules.jsonl"
PACK_DEMO = REPO / "tests" / "fixtures" / "packs" / "demo"
DU_AN_MAU = REPO / "projects" / "robot_balance"
#: Đầu vào ảnh hưởng băm prompt, đã đóng băng cạnh fixture. Muốn ghi lại theo
#: một bộ ràng buộc mới thì chép từ dự án mẫu vào đó TRƯỚC — hai bước, có chủ
#: ý. Xem tests/fixtures/e2e_project/README.md.
DAU_VAO_DONG_BANG = REPO / "tests" / "fixtures" / "e2e_project"

#: Hai module demo của TC-15, theo đúng thứ tự bộ test chạy.
MODULES = (
    ("drv_i2c_mpu6050", ["--uses", "twi,imu"]),
    ("pid_controller", ["--depends-on", "drv_i2c_mpu6050"]),
)


def dung_moi_truong(home: Path) -> Path:
    """Dựng cài đặt EAA y hệt fixture ``moi_truong`` của bộ test.

    Đoạn này PHẢI khớp từng bước với ``tests/test_tc15_e2e.py``. Lệch một chi
    tiết là lệch băm prompt, và bộ test sẽ đỏ với thông báo trượt băm.
    """
    (home / "packs").mkdir(parents=True)
    shutil.copytree(PACK_DEMO, home / "packs" / "demo")
    shutil.copy(REPO / "tools.yaml", home / "tools.yaml")

    project = home / "projects" / "demo_project"
    project.mkdir(parents=True)
    for ten in ("constraints.yaml", "hardware_profile.yaml"):
        shutil.copy(DAU_VAO_DONG_BANG / ten, project / ten)
    shutil.copytree(DAU_VAO_DONG_BANG / "datasheets", project / "datasheets")
    shutil.copytree(DU_AN_MAU / "sim", project / "sim")

    # Bản đóng băng đã mang sẵn ``platform: demo`` — không sửa gì sau khi chép,
    # để tệp được băm đúng bằng tệp nằm trong kho.
    (project / "tests").mkdir()
    (project / "tests" / "test_smoke.py").write_text(
        "def test_khung_du_an():\n    assert True\n", encoding="utf-8"
    )
    return project


def main_() -> int:
    load_env_file(REPO)
    if not os.environ.get("EAA_LLM_KEY"):
        print(
            "Chưa có EAA_LLM_KEY. Điền vào .env hoặc export trước khi chạy.\n"
            "Kịch bản này gọi mô hình THẬT và có tính phí.",
            file=sys.stderr,
        )
        return 4

    model = os.environ.get("EAA_LLM_MODEL", "")
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "eaa_home"
        project = dung_moi_truong(home)

        os.environ["EAA_HOME"] = str(home)
        os.environ["EAA_PROJECT"] = str(project)
        os.environ.setdefault("EAA_ACTOR", "Vũ Trí Công")

        print(f"Ghi bản ghi với mô hình thật: {model or '(mặc định của adapter)'}")
        ma = main(["init", "--provider", "gemini"] + (["--model", model] if model else []))
        if ma != 0:
            return ma

        for module, co in MODULES:
            if main(["plan", "add", module] + co) != 0:
                return 1
        main(["gate", "approve", "G1"])
        main(["gate", "approve", "G2"])

        for module, _ in MODULES:
            print(f"\n── sinh {module} ──")
            ma = main(["gen", module])
            if ma not in (0, 2):
                print(f"Sinh {module} thất bại với mã {ma}", file=sys.stderr)
                return ma
            main(["gate", "approve", "G3"])

        nguon = project / "llm_calls.jsonl"
        if not nguon.is_file():
            print("Không có lời gọi nào được ghi.", file=sys.stderr)
            return 1

        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(nguon, FIXTURE)

    from eaa.llm.calllog import CallLog

    ban_ghi = CallLog(FIXTURE).all()
    print(f"\nĐã ghi {len(ban_ghi)} lời gọi vào {FIXTURE.relative_to(REPO)}")
    for r in ban_ghi:
        print(f"  {r.module:<20}{r.model:<26}{r.tokens_in}→{r.tokens_out}")

    noi_dung = FIXTURE.read_text(encoding="utf-8")
    for dau_hieu in ("AIzaSy", "sk-"):
        if dau_hieu in noi_dung:
            print(f"\n!! Fixture chứa chuỗi giống khóa API ({dau_hieu}) — DỪNG", file=sys.stderr)
            FIXTURE.unlink()
            return 1
    print("Đã kiểm: fixture không chứa khóa API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_())
