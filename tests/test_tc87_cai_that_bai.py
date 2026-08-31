"""TC-87 — cài trượt phải nói VÌ SAO, và có lệnh cài cần nhiều hơn một bước.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-111.

Tìm ra ở lần đầu đường `doctor approve` → `doctor --fix` chạy thật, trên máy
thật, với bộ công cụ AVR thật. Ba lỗi, và cả ba chỉ lộ ra khi lệnh cài TRƯỢT:

1.  Nhật ký nói *"lần 1 thất bại (mã 1)"* và hết. Câu hữu ích nhất —
    *"No available formula with the name avr-gcc"* — bị `capture_output` bắt
    lấy rồi vứt đi. Người đọc không phân biệt được mạng hỏng với sai tên gói.
2.  Manifest chỉ khai được MỘT lệnh cho mỗi hệ điều hành. Trên macOS,
    `avr-gcc` nằm trong một kho ngoài và phải thêm kho trước — hai bước. Nên
    lệnh khai trong `packs/avr/tools.yaml` **chưa từng chạy được lần nào**.
3.  Quyết định duyệt neo vào một lệnh, trong khi thứ sẽ chạy là một DÃY lệnh.
    Thêm được một bước vào trước mà quyết định cũ vẫn hiệu lực thì cả tính
    chất "duyệt đúng cái sẽ chạy" sụp — mà đó là tính chất duy nhất làm cho
    việc Agent tự cài là an toàn (SL-110).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from eaa.doctor import (
    Doctor,
    EnvLock,
    InstallApprovals,
    InstallNotConfirmed,
    ToolManifest,
)

MANIFEST = """\
tools:
  - name: cong-cu-gia
    check: [cong-cu-gia, "--version"]
    blocking: true
    gate: compile
    install:
      macos: [brew, install, cong-cu-gia]
      linux: [apt-get, install, "-y", cong-cu-gia]
      windows: [choco, install, cong-cu-gia]
"""

MANIFEST_HAI_BUOC = MANIFEST.replace(
    "    install:",
    """    pre_install:
      macos: [[brew, tap, kho-ngoai/avr]]
      linux: []
      windows: []
    install:""",
)


def _doctor(tmp_path: Path, manifest: str = MANIFEST) -> Doctor:
    tep = tmp_path / "tools.yaml"
    tep.write_text(manifest, encoding="utf-8")
    return Doctor(
        manifest=ToolManifest.load(tep),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
        approvals=InstallApprovals(tmp_path / "install_approvals.jsonl"),
    )


# ═══════════ 1. trượt thì phải nói VÌ SAO ═══════════


def test_cai_truot_phai_NEU_LOI_cua_chinh_lenh_do(tmp_path: Path, monkeypatch) -> None:
    """"mã 1" không phải một chẩn đoán, nó chỉ là một con số.

    Đầu ra thật của lệnh cài đã nằm sẵn trong tay (``capture_output=True`` bắt
    được nó), rồi bị vứt đi. Người đọc nhật ký không phân biệt nổi *mạng hỏng*
    với *sai tên gói* — hai chuyện dẫn tới hai việc hoàn toàn khác nhau: một
    bên thử lại, một bên sửa manifest.

    Cùng bài học SL-100: bỏ thông tin thì được, bỏ IM LẶNG thì không.
    """
    import subprocess

    d = _doctor(tmp_path)

    def gia_lap(argv, **kw):
        return subprocess.CompletedProcess(
            argv, 1, stdout="", stderr='Warning: No available formula with the name "cong-cu-gia".'
        )

    monkeypatch.setattr(subprocess, "run", gia_lap)
    nhat_ky = d._run_install(d.manifest.get("cong-cu-gia"), ("brew", "install", "cong-cu-gia"))

    ca = "\n".join(nhat_ky)
    assert "No available formula" in ca, "đầu ra thật của lệnh bị vứt đi"
    assert "mã 1" in ca, "mã thoát vẫn phải còn"


def test_nhat_ky_loi_bi_CAT_thi_noi_ra_da_cat(tmp_path: Path, monkeypatch) -> None:
    """Đầu ra dài không được nuốt cả nhật ký — nhưng cắt thì phải khai là đã cắt."""
    import subprocess

    d = _doctor(tmp_path)
    dai = "\n".join(f"dòng {i}" for i in range(200))
    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 1, stdout="", stderr=dai),
    )
    ca = "\n".join(d._run_install(d.manifest.get("cong-cu-gia"), ("x",)))

    assert "dòng 199" in ca, "phải giữ phần CUỐI — lỗi nằm ở đó"
    assert "dòng 0" not in ca, "không in cả 200 dòng"
    assert "bỏ" in ca or "cắt" in ca, "cắt mà không khai là bỏ thông tin im lặng"


# ═══════════ 2. có lệnh cài cần nhiều hơn một bước ═══════════


def test_lenh_cai_nhieu_buoc_chay_DUNG_THU_TU(tmp_path: Path) -> None:
    """Thêm kho gói rồi mới cài được — manifest phải nói được điều đó.

    Không nói được thì mục trong manifest là một khẳng định sai: nó bảo "cài
    bằng lệnh này", mà lệnh ấy chưa từng chạy được lần nào trên hệ đó.
    """
    d = _doctor(tmp_path, MANIFEST_HAI_BUOC)
    buoc = d.install_steps(d.manifest.get("cong-cu-gia"))

    if d.install_command(d.manifest.get("cong-cu-gia"))[0] == "brew":  # macos
        assert buoc == [("brew", "tap", "kho-ngoai/avr"), ("brew", "install", "cong-cu-gia")]
    else:
        assert buoc == [d.install_command(d.manifest.get("cong-cu-gia"))]


def test_mot_buoc_thi_install_steps_van_dung(tmp_path: Path) -> None:
    d = _doctor(tmp_path)
    spec = d.manifest.get("cong-cu-gia")
    assert d.install_steps(spec) == [d.install_command(spec)]


# ═══════════ 3. duyệt neo vào CẢ DÃY sẽ chạy ═══════════


def test_them_mot_buoc_thi_quyet_dinh_cu_HET_HIEU_LUC(tmp_path: Path) -> None:
    """Tính chất duy nhất làm cho việc Agent tự cài là an toàn (SL-110).

    Quyết định neo vào một lệnh, trong khi thứ sẽ chạy là một dãy lệnh, thì
    chèn thêm một bước vào trước là chèn được mã tùy ý sau lưng người duyệt —
    và quyết định cũ vẫn trông hợp lệ.
    """
    d = _doctor(tmp_path)
    spec = d.manifest.get("cong-cu-gia")
    d.approvals.approve("cong-cu-gia", d.install_steps(spec), by="người duyệt")
    assert d.approvals.find("cong-cu-gia", d.install_steps(spec)) is not None

    # Manifest mọc thêm một bước chuẩn bị — quyết định cũ phải mất hiệu lực.
    d2 = _doctor(tmp_path, MANIFEST_HAI_BUOC)
    d2.approvals = d.approvals
    spec2 = d2.manifest.get("cong-cu-gia")
    if len(d2.install_steps(spec2)) > 1:
        assert d2.approvals.find("cong-cu-gia", d2.install_steps(spec2)) is None


def test_fix_chay_DU_cac_buoc_da_duyet(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    d = _doctor(tmp_path, MANIFEST_HAI_BUOC)
    spec = d.manifest.get("cong-cu-gia")
    buoc = d.install_steps(spec)
    if len(buoc) == 1:
        pytest.skip("hệ này không có bước chuẩn bị")

    d.approvals.approve("cong-cu-gia", buoc, by="người duyệt")
    d.confirm = lambda ten, lenh: None
    da_chay: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, **kw: da_chay.append(tuple(argv))
        or subprocess.CompletedProcess(argv, 0, stdout="", stderr=""),
    )

    d.fix(d.scan())
    assert da_chay == [tuple(b) for b in buoc], "phải chạy đủ dãy, đúng thứ tự"


def test_buoc_chuan_bi_TRUOT_thi_dung_luon(tmp_path: Path, monkeypatch) -> None:
    """Thêm kho không xong thì cài chắc chắn trượt — chạy tiếp là phí và gây nhiễu."""
    import subprocess

    d = _doctor(tmp_path, MANIFEST_HAI_BUOC)
    spec = d.manifest.get("cong-cu-gia")
    buoc = d.install_steps(spec)
    if len(buoc) == 1:
        pytest.skip("hệ này không có bước chuẩn bị")

    da_chay: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda argv, **kw: da_chay.append(tuple(argv))
        or subprocess.CompletedProcess(argv, 3, stdout="", stderr="kho không tồn tại"),
    )
    ca = "\n".join(d._run_install(spec, buoc))

    assert da_chay == [tuple(buoc[0])] * 2, "chỉ thử bước chuẩn bị, không cài tiếp"
    assert "kho không tồn tại" in ca


# ═══════════ manifest thật của pack AVR ═══════════


def test_manifest_avr_khai_duoc_duong_cai_tren_may_nay() -> None:
    """Mục manifest là một KHẲNG ĐỊNH: "cài bằng lệnh này". Nó phải đúng.

    Bài này không cài gì; nó chỉ đòi rằng với hệ đang chạy, mục ấy khai ra một
    dãy lệnh khác rỗng. Trước SL-111, mục macOS khai một lệnh chưa từng chạy
    được lần nào.
    """
    from eaa.doctor import _os_key

    REPO = Path(__file__).resolve().parent.parent
    m = ToolManifest.load(REPO / "tools.yaml", REPO / "packs" / "avr" / "tools.yaml", pack="avr")
    d = Doctor(manifest=m, tools_kb=REPO / "x", env_lock=EnvLock(REPO / "y"))

    for ten in ("avr-gcc", "avr-size"):
        spec = m.get(ten)
        if spec is None or _os_key() not in spec.install:
            continue
        assert d.install_steps(spec), f"{ten}: không khai được đường cài trên hệ này"
