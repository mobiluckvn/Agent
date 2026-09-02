"""TC-121 — nhánh làm việc của module luôn mọc từ nhánh chính hiện tại.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-158.

`start_module` gọi `checkout(branch, create=True)`. Nhánh chưa có thì tạo mới
từ `main` — đúng. Nhánh ĐÃ CÓ thì chỉ nhảy sang, và nhánh ấy đứng yên từ lần
sinh trước trong khi `main` đã nhận thêm module.

Đo được ngày 02/09/2026: `eaa plan reopen drv_i2c` rồi sinh lại chạy trên
`feature/drv_i2c` mở từ trước khi `drv_stepper` merge::

    main tests: button, buzzer, i2c, stepper
    HEAD tests: button, buzzer, i2c          ← thiếu stepper

Cổng `unittests` báo ĐẠT trên một bộ kiểm thiếu hẳn một module. Cùng họ với
SL-152 (chấm bằng nhị phân cũ) và SL-153 (bỏ qua đọc thành đạt): cổng xanh vì
nó không chạy thứ cần chạy.

Chỉ cắn khi sinh LẠI một module đã có nhánh — tức đúng luồng `plan reopen`
vừa mở ra, nên nó ra đời cùng lúc với chỗ dùng nó.
"""

from __future__ import annotations

from pathlib import Path

from eaa.vcs import GitRepo


def _kho(tmp_path: Path) -> GitRepo:
    repo = GitRepo(tmp_path / "firmware")
    repo.init()
    (repo.root / "tests").mkdir(parents=True, exist_ok=True)
    return repo


def _commit_tren_main(repo: GitRepo, ten: str) -> None:
    repo.checkout(repo.main_branch)
    (repo.root / "tests" / ten).write_text("def test_x():\n    assert True\n", encoding="utf-8")
    repo._git("add", "-A")
    repo._git("commit", "-q", "-m", f"them {ten}")


def test_nhanh_moi_moc_tu_main(tmp_path: Path) -> None:
    repo = _kho(tmp_path)
    _commit_tren_main(repo, "test_a.py")

    repo.start_module("drv_a")

    assert repo.current_branch() == "feature/drv_a"
    assert (repo.root / "tests" / "test_a.py").exists()


def test_nhanh_CU_duoc_dat_lai_ve_main(tmp_path: Path) -> None:
    """Chỗ SL-158 nằm."""
    repo = _kho(tmp_path)
    _commit_tren_main(repo, "test_a.py")

    # Lượt sinh đầu của drv_a: mở nhánh, commit gì đó.
    repo.start_module("drv_a")
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / "drv_a.c").write_text("void a(void){}\n", encoding="utf-8")
    repo._git("add", "-A")
    repo._git("commit", "-q", "-m", "drv_a ban dau")

    # Trong lúc ấy main nhận thêm một module khác.
    _commit_tren_main(repo, "test_b.py")

    # Sinh LẠI drv_a.
    repo.start_module("drv_a")

    assert repo.current_branch() == "feature/drv_a"
    assert (repo.root / "tests" / "test_b.py").exists(), (
        "Nhánh làm việc đứng sau main: cổng unittests sẽ chạy trên một bộ kiểm "
        "THIẾU module đã merge sau đó, và báo ĐẠT vì không chạy thứ cần chạy."
    )
    assert (repo.root / "tests" / "test_a.py").exists()


def test_dat_lai_nhanh_khong_keo_theo_ma_cua_lan_thu_truoc(tmp_path: Path) -> None:
    """Lượt sinh mới bắt đầu từ mã ĐÃ MERGE, không từ bản nháp bị bỏ."""
    repo = _kho(tmp_path)
    _commit_tren_main(repo, "test_a.py")

    repo.start_module("drv_a")
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / "drv_a.c").write_text("// ban bi tu choi\n", encoding="utf-8")
    repo._git("add", "-A")
    repo._git("commit", "-q", "-m", "ban bi tu choi")

    repo.start_module("drv_a")

    assert not (repo.root / "src" / "drv_a.c").exists(), (
        "Bản bị từ chối ở lượt trước vẫn nằm trong cây làm việc của lượt mới."
    )


def test_khong_dung_toi_nhanh_chinh(tmp_path: Path) -> None:
    """`checkout -B` đặt lại NHÁNH MODULE, không được chạm `main`."""
    repo = _kho(tmp_path)
    _commit_tren_main(repo, "test_a.py")
    main_truoc = repo._git("rev-parse", repo.main_branch)

    repo.start_module("drv_a")
    (repo.root / "src").mkdir(exist_ok=True)
    (repo.root / "src" / "drv_a.c").write_text("x\n", encoding="utf-8")
    repo._git("add", "-A")
    repo._git("commit", "-q", "-m", "x")
    repo.start_module("drv_a")

    assert repo._git("rev-parse", repo.main_branch) == main_truoc
