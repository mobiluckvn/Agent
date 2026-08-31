"""TC-89 — checksum phải được TÍNH, không phải được KHAI.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-113.

Tìm ra khi đi tìm đường cài `avr-gcc` trên một máy mà Homebrew không có bản
dựng sẵn. Đường thiết kế đã chừa cho đúng tình huống ấy là tải trực tiếp kèm
checksum — `ToolSpec.download` + `ToolSpec.checksum`.

Đọc mã thì thấy đường ấy **không tồn tại**:

* `Doctor.verify_checksum()` có, có bài kiểm riêng (TC-35), và **không nơi nào
  trong engine gọi nó**.
* `fix()` gặp `download` + `checksum` thì in ra một dòng nhật ký:
  *"tải trực tiếp từ …, bắt buộc khớp checksum …"* — rồi chạy lệnh cài như
  thường. Không tải, không tính, không đối chiếu.

Nên tính chất số 3 mà chính docstring của `eaa/doctor.py` khai — *"Checksum sai
là từ chối, không phải cảnh báo rồi vẫn chạy (TC-35)"* — **không được thi hành
trên bất kỳ đường sống nào**. Có hàm, có test, không có người gọi; và có một
dòng nhật ký khẳng định việc ấy đã xảy ra.

Đây là dạng hỏng tệ nhất trong nhóm: không phải thiếu một tính năng, mà là
**một lời hứa an toàn được in ra cho người đọc tin**.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from eaa.doctor import (
    ChecksumMismatch,
    Doctor,
    EnvLock,
    InstallApprovals,
    ToolManifest,
)

NOI_DUNG = b"gia lam mot goi cai dat"
BAM_DUNG = "sha256:" + hashlib.sha256(NOI_DUNG).hexdigest()
BAM_SAI = "sha256:" + "0" * 64
REPO_GOC = Path(__file__).resolve().parent.parent


def _manifest(bam: str) -> str:
    return f"""\
tools:
  - name: cong-cu-tai-ve
    check: [cong-cu-tai-ve, "--version"]
    blocking: true
    gate: compile
    download: https://vi-du.test/goi.tar.bz2
    checksum: "{bam}"
    install:
      macos: [tar, -xf, "{{tai_ve}}", -C, /dich]
      linux: [tar, -xf, "{{tai_ve}}", -C, /dich]
      windows: [tar, -xf, "{{tai_ve}}", -C, /dich]
"""


def _doctor(tmp_path: Path, bam: str = BAM_DUNG) -> Doctor:
    tep = tmp_path / "tools.yaml"
    tep.write_text(_manifest(bam), encoding="utf-8")
    return Doctor(
        manifest=ToolManifest.load(tep),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
        approvals=InstallApprovals(tmp_path / "install_approvals.jsonl"),
    )


@pytest.fixture()
def gia_lap_tai(monkeypatch):
    """Thay chỗ tải thật bằng một chỗ ghi ra nội dung định sẵn."""
    da_tai: list[str] = []

    def _tai(url: str, dich: Path) -> None:
        da_tai.append(url)
        Path(dich).write_bytes(NOI_DUNG)

    import eaa.doctor as d

    monkeypatch.setattr(d, "_tai_ve", _tai)
    return da_tai


def _khong_chay(doctor: Doctor, monkeypatch) -> list:
    """Ghi lại lệnh sẽ chạy thay vì chạy nó.

    Dùng ``monkeypatch`` chứ KHÔNG gán thẳng ``eaa.doctor.subprocess.run``:
    thuộc tính ấy là chính module ``subprocess`` toàn cục, nên gán thẳng làm
    hỏng mọi bài kiểm chạy sau trong cùng phiên — và hỏng im lặng, vì lệnh
    con vẫn "thành công". Tôi tự dính đúng bẫy đó khi viết bài này.
    """
    da_chay: list = []
    import subprocess

    goc = subprocess.run

    def _gia(argv, **kw):
        da_chay.append(tuple(argv))
        return goc(["true"], capture_output=True, text=True)

    monkeypatch.setattr(subprocess, "run", _gia)
    return da_chay


# ═══════════ checksum sai thì KHÔNG chạy lệnh cài ═══════════


def test_checksum_sai_thi_TU_CHOI_va_khong_chay_gi(tmp_path: Path, gia_lap_tai, monkeypatch) -> None:
    """Điểm cốt lõi. "Cảnh báo rồi vẫn chạy" là chỗ tính chất này chết.

    Gói tải về không khớp nghĩa là nguồn có thể đã bị can thiệp. Chạy lệnh cài
    trên nó là chạy mã của người lạ với quyền của người dùng.
    """
    d = _doctor(tmp_path, BAM_SAI)
    da_chay = _khong_chay(d, monkeypatch)
    spec = d.manifest.get("cong-cu-tai-ve")

    with pytest.raises(ChecksumMismatch):
        d._run_install(spec, d.install_steps(spec))

    assert gia_lap_tai, "phải có tải về thật thì mới có gì để đối chiếu"
    assert da_chay == [], "checksum sai mà vẫn chạy lệnh cài"


def test_checksum_dung_thi_di_tiep_va_TRUYEN_duong_dan_goi(
    tmp_path: Path, gia_lap_tai, monkeypatch
) -> None:
    """Chỗ giữ ``{tai_ve}`` phải được thay bằng đường dẫn gói ĐÃ KIỂM.

    Không thay thì lệnh cài chạy trên một chuỗi vô nghĩa; thay bằng đường dẫn
    chưa kiểm thì cả phép kiểm là trang trí.
    """
    d = _doctor(tmp_path, BAM_DUNG)
    da_chay = _khong_chay(d, monkeypatch)
    spec = d.manifest.get("cong-cu-tai-ve")

    d._run_install(spec, d.install_steps(spec))

    assert len(da_chay) == 1
    argv = da_chay[0]
    assert "{tai_ve}" not in " ".join(argv), "chỗ giữ không được thay"
    duong_dan = [x for x in argv if x.endswith(".tar.bz2") or "goi" in x]
    assert duong_dan, f"không truyền đường dẫn gói vào lệnh cài: {argv}"


def test_khong_khai_checksum_thi_KHONG_tai(tmp_path: Path, gia_lap_tai) -> None:
    """Tải mà không có gì đối chiếu thì tệ hơn không tải.

    Khai ``download`` mà quên ``checksum`` phải là một lỗi nói ra, không phải
    một lượt tải im lặng không ai kiểm.
    """
    tep = tmp_path / "t.yaml"
    tep.write_text(
        'tools:\n'
        '  - name: x\n'
        '    check: [x]\n'
        '    download: https://vi-du.test/g.tar\n'
        '    install:\n'
        '      macos: [tar, -xf, "{tai_ve}"]\n'
        '      linux: [tar, -xf, "{tai_ve}"]\n'
        '      windows: [tar, -xf, "{tai_ve}"]\n',
        encoding="utf-8",
    )
    d = Doctor(
        manifest=ToolManifest.load(tep),
        tools_kb=tmp_path / "kb",
        env_lock=EnvLock(tmp_path / "l.json"),
    )
    spec = d.manifest.get("x")
    with pytest.raises(Exception, match="checksum"):
        d._run_install(spec, d.install_steps(spec))
    assert gia_lap_tai == [], "chưa có checksum thì không được tải"


# ═══════════ không còn hàm nào có test mà không có người gọi ═══════════


def test_verify_checksum_PHAI_co_nguoi_goi_trong_engine() -> None:
    """Bài canh chống tái phát, dạng quét mã nguồn như TC-38.

    Một hàm an toàn có bài kiểm mà không ai gọi là thứ nguy hiểm nhất trong
    kho: bảng test xanh, tài liệu khai có tính chất, và đường chạy thật thì
    trống. Bài này đòi ít nhất một chỗ trong engine THỰC SỰ gọi nó.
    """
    from pathlib import Path as P

    goc = P(__file__).resolve().parent.parent / "eaa"
    goi = []
    for tep in sorted(goc.rglob("*.py")):
        nguon = tep.read_text(encoding="utf-8")
        for dong in nguon.splitlines():
            d = dong.strip()
            if "verify_checksum(" in d and not d.startswith("def "):
                goi.append(f"{tep.name}: {d[:70]}")
    assert goi, (
        "Không nơi nào trong engine gọi verify_checksum(). Tính chất số 3 của "
        "eaa/doctor.py — 'checksum sai là TỪ CHỐI, không phải cảnh báo rồi vẫn "
        "chạy' — chỉ tồn tại trong lời khai."
    )


# ═══════════ G1 phải THỰC SỰ chốt lại bộ ràng buộc ═══════════


def test_duyet_G1_ghim_lai_bam_rang_buoc(tmp_path: Path) -> None:
    """Cảnh báo trôi băm nói "chốt lại qua gate G1" — và G1 phải làm được điều đó.

    Trước SL-113, `constraints_version` chỉ được ghi MỘT lần ở `eaa init`;
    không đường nào chốt lại. Nên `eaa status` cảnh báo trôi, chỉ sang `gate
    approve G1`, người duyệt G1 — và cảnh báo vẫn còn nguyên. Lệnh chỉ sang
    một cánh cửa không tồn tại.

    Ghim lại ở đây là AN TOÀN chứ không phải tiện: hồ sơ G1 mà người vừa đọc
    CHỨA nội dung ràng buộc, và quyết định neo vào băm hồ sơ ấy. Ta ghi lại
    băm của đúng thứ họ vừa duyệt, không phải của bất cứ gì đang nằm trên đĩa.
    """
    import subprocess
    import sys

    from eaa.kb import Constraints
    from eaa.state import StateStore

    du_an = tmp_path / "da"
    du_an.mkdir()
    (du_an / "constraints.yaml").write_text(
        "version: 1\nplatform: avr\nmcu: atmega328p\n"
        "forbidden:\n  - delay()\n",
        encoding="utf-8",
    )
    (du_an / "hardware_profile.yaml").write_text(
        "version: 1\nproject: da\nmcu:\n  part: atmega328p\n  clock_hz: 16000000\n",
        encoding="utf-8",
    )
    kq = subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(du_an), "init"],
        capture_output=True, text=True, cwd=REPO_GOC, check=False,
    )
    assert (du_an / "project_state.json").is_file(), (
        f"eaa init không dựng được dự án:\n{kq.stdout}\n{kq.stderr}"
    )
    tep = du_an / "constraints.yaml"

    # Sửa ràng buộc → băm trên đĩa lệch khỏi băm đã ghim.
    tep.write_text(tep.read_text(encoding="utf-8") + "\n# thêm một dòng\n",
                   encoding="utf-8")
    bam_moi = Constraints.load(tep).content_version
    truoc = StateStore(du_an / "project_state.json").load().constraints_version
    assert truoc != bam_moi, "chưa dựng được tình huống trôi băm"

    subprocess.run(
        [sys.executable, "-m", "eaa.cli", "--project", str(du_an),
         "gate", "approve", "G1", "--actor", "người kiểm"],
        capture_output=True, text=True, cwd=REPO_GOC, check=False,
    )
    sau = StateStore(du_an / "project_state.json").load().constraints_version
    assert sau == bam_moi, (
        "duyệt G1 xong mà băm ràng buộc chưa được ghim lại — cảnh báo trôi sẽ "
        "còn mãi, và nó chỉ sang đúng cái lệnh vừa chạy"
    )
