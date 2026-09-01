"""TC-118 — vòng sinh mã của module này không viết đè module đã merge.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-154.

Ngày 02/09/2026, `eaa gen drv_imu` trả về `src/drv_i2c.c` ở cả ba vòng tự sửa,
mỗi lần viết lại từ đầu. `drv_i2c` là module đã merge, đã qua G3 từ hôm trước.
Bản viết lại xoá bốn hàm công khai của nó::

    AttributeError: dlsym(0x40f28900, i2c_init): symbol not found

Mô hình không làm gì sai theo lời nó được dặn: cổng `unittests` chạy CẢ thư mục
test, báo cáo lỗi nó nhận được có tên `tests/test_drv_i2c.py`, và nó đi sửa chỗ
được chỉ. Chỗ hở nằm ở đường ống — `write_artifact` chặn đường dẫn THOÁT RA
NGOÀI thư mục làm việc, còn bên trong thư mục ấy thì tệp nào cũng ghi được.

Bất biến
--------

**Mã đã merge chỉ đổi qua vòng sinh của CHÍNH module đó.** Mỗi tệp trên nhánh
chính đã đi qua một lượt review G3 mang tên một module; một lượt sinh cho module
khác viết đè lên nó là xoá quyết định ấy mà không ai bấm nút gì.

Ranh giới cố ý đặt ở "đã có trên nhánh chính", không phải "ngoài danh sách tệp
cần sinh": một module có quyền thêm tệp phụ của chính nó, và tệp chưa merge thì
chưa là tài sản của ai.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.orchestrator import Orchestrator
from eaa.tools.base import CodeArtifact, ToolError, ToolReport
from eaa.vcs import GitRepo


# --------------------------------------------------------------------------
# Kho firmware có sẵn một module ĐÃ MERGE
# --------------------------------------------------------------------------


def _kho_co_module_da_merge(tmp_path: Path) -> GitRepo:
    repo = GitRepo(tmp_path / "firmware")
    repo.init()
    (repo.root / "src").mkdir(parents=True, exist_ok=True)
    (repo.root / "tests").mkdir(parents=True, exist_ok=True)
    (repo.root / "src" / "drv_i2c.c").write_text("void i2c_init(void) {}\n", encoding="utf-8")
    (repo.root / "src" / "drv_i2c.h").write_text("void i2c_init(void);\n", encoding="utf-8")
    (repo.root / "tests" / "test_drv_i2c.py").write_text(
        "def test_i2c():\n    assert True\n", encoding="utf-8"
    )
    repo._git("add", "-A")
    repo._git("commit", "-q", "-m", "drv_i2c: merged")
    return repo


def _orch(repo: GitRepo) -> Orchestrator:
    """Chỉ hai thứ được dùng ở đây: kho và bảng tệp cần sinh."""
    return Orchestrator(
        state_store=None,
        composer=None,
        llm=None,
        gates=None,
        repo=repo,
        graph=None,
        runs_dir=repo.root.parent / ".eaa" / "runs",
    )


# --------------------------------------------------------------------------
# files_on_main — câu hỏi "tệp này đã merge chưa"
# --------------------------------------------------------------------------


def test_files_on_main_liet_ke_dung_tep_da_merge(tmp_path: Path) -> None:
    repo = _kho_co_module_da_merge(tmp_path)
    tren_main = repo.files_on_main()

    assert "src/drv_i2c.c" in tren_main
    assert "src/drv_imu.c" not in tren_main


def test_files_on_main_rong_khi_chua_co_nhanh_chinh(tmp_path: Path) -> None:
    """Chưa có gì để bảo vệ thì không chặn gì — và không nổ.

    Kho vừa `git init`, chưa commit lần nào: `main` chưa trỏ vào đâu cả. Hỏi
    git về một nhánh không tồn tại là một lỗi, và một bộ lọc nổ ở đây sẽ chặn
    module ĐẦU TIÊN của mọi dự án mới.
    """
    goc = tmp_path / "firmware"
    goc.mkdir()
    repo = GitRepo(goc)
    repo._git("init", "-q", "-b", "main")

    assert repo.files_on_main() == frozenset()

    artifact = CodeArtifact(files={"src/drv_imu.c": "c"})
    assert _orch(repo).khoa_pham_vi_tep(artifact, "drv_imu") == []


# --------------------------------------------------------------------------
# Khoá phạm vi
# --------------------------------------------------------------------------


def test_tep_cua_module_da_merge_bi_bo_ra(tmp_path: Path) -> None:
    """Chỗ SL-154 nằm."""
    repo = _kho_co_module_da_merge(tmp_path)
    artifact = CodeArtifact(
        files={
            "src/drv_imu.c": "// mã đúng của module đang sinh",
            "src/drv_i2c.c": "// mô hình viết lại module của người khác",
        }
    )

    bo_ra = _orch(repo).khoa_pham_vi_tep(artifact, "drv_imu")

    assert bo_ra == ["src/drv_i2c.c"]
    assert "src/drv_i2c.c" not in artifact.files, (
        "Tệp của module đã merge vẫn nằm trong artifact — nó sẽ được ghi xuống "
        "đĩa và commit vào nhánh review của module KHÁC."
    )
    assert artifact.files["src/drv_imu.c"].startswith("// mã đúng")


def test_ba_tep_cua_chinh_module_deu_qua(tmp_path: Path) -> None:
    """Danh sách cho phép sinh từ `tep_can_sinh` — cùng hàm viết câu trong prompt."""
    repo = _kho_co_module_da_merge(tmp_path)
    artifact = CodeArtifact(
        files={
            "src/drv_imu.c": "c",
            "src/drv_imu.h": "h",
            "tests/test_drv_imu.py": "py",
        }
    )

    assert _orch(repo).khoa_pham_vi_tep(artifact, "drv_imu") == []
    assert len(artifact.files) == 3


def test_module_sua_lai_chinh_no_sau_khi_da_merge_van_qua(tmp_path: Path) -> None:
    """`drv_i2c` sinh lại `drv_i2c` là chuyện bình thường, không phải vi phạm."""
    repo = _kho_co_module_da_merge(tmp_path)
    artifact = CodeArtifact(files={"src/drv_i2c.c": "// bản mới"})

    assert _orch(repo).khoa_pham_vi_tep(artifact, "drv_i2c") == []
    assert artifact.files["src/drv_i2c.c"] == "// bản mới"


def test_tep_phu_moi_cua_chinh_module_van_qua(tmp_path: Path) -> None:
    """Ranh giới là 'đã merge', không phải 'ngoài danh sách'.

    Một cổng hay báo nhầm sớm muộn cũng bị tắt đi, và lúc ấy nó không bảo vệ
    được gì nữa. Tệp chưa có trên nhánh chính thì chưa là tài sản của ai.
    """
    repo = _kho_co_module_da_merge(tmp_path)
    artifact = CodeArtifact(
        files={"src/drv_imu.c": "c", "src/drv_imu_bang_tra.h": "bảng tra riêng"}
    )

    assert _orch(repo).khoa_pham_vi_tep(artifact, "drv_imu") == []
    assert "src/drv_imu_bang_tra.h" in artifact.files


def test_viec_bo_tep_duoc_NOI_RA(tmp_path: Path) -> None:
    """Bỏ im lặng là cách một bản vá biến mất mà không ai biết (bài học SL-151)."""
    repo = _kho_co_module_da_merge(tmp_path)
    cau = _orch(repo)._cau_bo_tep(["src/drv_i2c.c"], "drv_imu")

    assert "src/drv_i2c.c" in cau
    assert "drv_imu" in cau


# --------------------------------------------------------------------------
# Đường ống: vòng VÁ là chỗ lỗi thật đã xảy ra
# --------------------------------------------------------------------------


class _ComposerGia:
    def build_repair(self, *a, **k):  # noqa: ANN002, ANN003
        return "prompt vá"


class _LLMGia:
    """Trả về đúng thứ mô hình thật đã trả về hôm 02/09: tệp của module khác."""

    def generate(self, prompt):  # noqa: ANN001
        return CodeArtifact(
            files={"src/drv_i2c.c": "// viết lại module đã merge"},
            prompt_hash="sha256:x",
            model="mock",
            constraints_version="sha256:y",
        )

    def count_tokens(self, text: str) -> int:  # noqa: D102
        return len(text)


def test_vong_va_khong_mang_theo_tep_cua_module_da_merge(tmp_path: Path) -> None:
    repo = _kho_co_module_da_merge(tmp_path)
    orch = _orch(repo)
    orch.composer = _ComposerGia()
    orch.llm = _LLMGia()

    truoc = CodeArtifact(files={"src/drv_imu.c": "// bản trước khi vá"})
    bao_cao_hong = ToolReport(
        gate="unittests", passed=False, errors=[ToolError("test_drv_i2c.py đỏ")]
    )

    ban_va, canh_bao = orch._va_loi(
        task=None, state=None, bao_cao_hong=bao_cao_hong, artifact=truoc, module_id="drv_imu"
    )

    assert "src/drv_i2c.c" not in ban_va.files, (
        "Vòng tự sửa vừa mang mã ghi đè một module đã merge sang bước commit."
    )
    assert ban_va.files["src/drv_imu.c"] == "// bản trước khi vá"
    assert "src/drv_i2c.c" in canh_bao, "bỏ tệp mà không nói ra"


def test_loc_TRUOC_khi_gop_de_con_phan_biet_duoc_nguon_goc(tmp_path: Path) -> None:
    """Gộp xong mới lọc thì không còn biết tệp đến từ bản vá hay từ lượt sinh.

    Ở đây artifact TRƯỚC khi vá đã (sai) mang sẵn tệp của module khác. Bản vá
    không đụng tới nó. Lọc đặt đúng chỗ thì tệp ấy vẫn còn — vì nó không phải
    thứ vòng vá này vừa sinh ra — và bài kiểm ghi lại đúng ranh giới ấy để lần
    sau ai đổi thứ tự sẽ thấy.
    """
    repo = _kho_co_module_da_merge(tmp_path)
    orch = _orch(repo)
    orch.composer = _ComposerGia()
    orch.llm = _LLMGia()

    truoc = CodeArtifact(files={"src/drv_imu.c": "c", "src/drv_i2c.c": "// từ lượt trước"})
    ban_va, _ = orch._va_loi(
        task=None,
        state=None,
        bao_cao_hong=ToolReport(gate="unittests", passed=False, errors=[ToolError("đỏ")]),
        artifact=truoc,
        module_id="drv_imu",
    )

    assert ban_va.files["src/drv_i2c.c"] == "// từ lượt trước", (
        "Bản vá đã ghi đè tệp của module đã merge dù bộ lọc đứng trước bước gộp."
    )


@pytest.mark.parametrize("module_id", ["drv_imu", "logic_pid", "app_balance"])
def test_bat_bien_khong_phu_thuoc_ten_module(tmp_path: Path, module_id: str) -> None:
    repo = _kho_co_module_da_merge(tmp_path)
    artifact = CodeArtifact(files={"src/drv_i2c.h": "// viết lại tiêu đề đã merge"})

    assert _orch(repo).khoa_pham_vi_tep(artifact, module_id) == ["src/drv_i2c.h"]
    assert artifact.files == {}
