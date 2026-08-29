"""TC-34..37 — phát hiện, chuẩn bị và khóa môi trường công cụ.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-34 | Gỡ một công cụ khỏi PATH rồi quét | báo THIẾU kèm cổng bị chặn; `--fix` sinh đúng lệnh theo hệ điều hành; **KHÔNG tự thực thi** |
| TC-35 | Gói tải trực tiếp có checksum sai | từ chối cài, nêu rõ lý do |
| TC-36 | Nâng phiên bản khác với env_lock rồi build | cảnh báo trôi môi trường; người chấp nhận thì cập nhật khóa và chỉ số ghi băm mới |
| TC-37 | Cài mới một công cụ qua `--fix` | smoke test tự chạy; Thẻ công cụ xuất hiện với cú pháp gọi chạy được |

Lý do cả nhóm này quan trọng hơn vẻ ngoài của nó (AIS §9): thiếu hoặc lệch một
mắt xích thì cổng kiểm chứng thành vô nghĩa — mà nó vẫn trông y hệt như khi
mọi thứ đều đạt. Một chuỗi cổng không chạy được thì mọi kết luận phía sau đều
rỗng.
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from eaa.doctor import (
    ChecksumMismatch,
    Doctor,
    DoctorError,
    EnvLock,
    InstallNotConfirmed,
    ToolCard,
    ToolManifest,
    ToolStatus,
)

REPO = Path(__file__).resolve().parent.parent


MANIFEST_MAU = """\
scope: engine
tools:
  - name: python
    check: ["{python}", "--version"]
    min_version: "3.10"
    level: Must
    gates: [unittests, sim]
    install:
      macos: ["brew", "install", "python@3.12"]
      linux: ["sudo", "apt-get", "install", "-y", "python3"]
      windows: ["winget", "install", "-e", "--id", "Python.Python.3.12"]
    smoke: ["{python}", "-c", "print('eaa-smoke-ok')"]
    smoke_expect: "eaa-smoke-ok"
  - name: cong-cu-khong-ton-tai
    check: ["cong-cu-chac-chan-khong-co-tren-may-nay", "--version"]
    min_version: "1.0"
    level: Must
    gates: [static]
    install:
      macos: ["brew", "install", "cong-cu-khong-ton-tai"]
      linux: ["sudo", "apt-get", "install", "-y", "cong-cu-khong-ton-tai"]
      windows: ["winget", "install", "-e", "--id", "X.Y"]
"""


@pytest.fixture()
def doctor(tmp_path: Path) -> Doctor:
    manifest_path = tmp_path / "tools.yaml"
    manifest_path.write_text(
        MANIFEST_MAU.replace("{python}", sys.executable), encoding="utf-8"
    )
    return Doctor(
        manifest=ToolManifest.load(manifest_path),
        tools_kb=tmp_path / "tools_kb",
        env_lock=EnvLock(tmp_path / "env_lock.json"),
    )


# --------------------------------------------------------------------------
# Manifest là dữ liệu, chia engine / pack
# --------------------------------------------------------------------------


def test_manifest_that_cua_du_an_nap_duoc() -> None:
    m = ToolManifest.load(REPO / "tools.yaml", REPO / "packs" / "avr" / "tools.yaml", pack="avr")
    ten = {s.name for s in m.specs}
    # Engine chỉ khai những gì CHÍNH NÓ chạy trên đó — Python và Git. Bộ phân
    # tích tĩnh do pack gọi, nên nó thuộc manifest của pack (AIS §9.1).
    assert {"python", "git"} <= ten, "thiếu phần chung của engine"
    assert "cppcheck" not in {
        s_.name for s_ in ToolManifest.load(REPO / "tools.yaml").specs
    }, "công cụ của pack bị khai ở manifest engine"


def test_manifest_cua_pack_khong_chep_san_nhu_cau() -> None:
    """AIS §9.1–9.2: manifest ghi thứ ĐÃ DUYỆT, nhu cầu thì suy từ pack.

    Chép sẵn ``avr-gcc`` vào manifest là khai nhu cầu ở sai chỗ: nó lệch khỏi
    ``pack.yaml`` ngay lần đầu pack đổi lệnh, và lệch theo hướng nguy hiểm —
    doctor báo "đủ công cụ" trong khi cổng kiểm chứng sắp gọi một chương trình
    không có. Nhu cầu nằm ở pack; hiểu biết nằm ở manifest.
    """
    from eaa.platform import load_manifest
    from eaa.toolsearch import derive_requirements

    can = {r.program for r in derive_requirements(load_manifest(REPO / "packs" / "avr"))}
    assert {"avr-gcc", "avr-size", "avrdude"} <= can, "nhu cầu phải suy được từ pack"

    # Manifest của pack được phép có mục — nhưng chỉ những mục đã đi qua G2.
    # Một mục không có dấu vết người duyệt nghĩa là ai đó viết tay vào đây.
    import yaml

    du_lieu = yaml.safe_load(
        (REPO / "packs" / "avr" / "tools.yaml").read_text(encoding="utf-8")
    ) or {}
    khong_dau_vet = [
        m["name"] for m in (du_lieu.get("tools") or []) if not m.get("approved_by")
    ]
    assert not khong_dau_vet, (
        f"Mục viết tay trong manifest của pack: {khong_dau_vet}. Công cụ vào "
        "manifest qua G2 và mang theo approved_by/approved_at (AIS §9.1)."
    )


def test_khong_cai_pack_thi_khong_quet_cong_cu_cua_pack() -> None:
    """AIS §9.1: cài pack nào thì quét thêm phần của pack đó, không quét thừa."""
    m = ToolManifest.load(REPO / "tools.yaml", REPO / "packs" / "avr" / "tools.yaml", pack="stm32")
    ten = {s.name for s in m.specs}
    assert "python" in ten
    assert "avr-gcc" not in ten


def test_moi_cong_cu_khai_bao_cong_nao_bi_chan_neu_thieu() -> None:
    """Không có trường này thì báo cáo chỉ nói "thiếu", không nói "hỏng cái gì"."""
    m = ToolManifest.load(REPO / "tools.yaml", REPO / "packs" / "avr" / "tools.yaml", pack="avr")
    for spec in m.specs:
        assert spec.gates, f"{spec.name} không khai báo cổng nào nó phục vụ"


def test_lenh_kiem_tra_phai_la_danh_sach_argv(tmp_path: Path) -> None:
    (tmp_path / "t.yaml").write_text(
        'tools:\n  - name: x\n    check: "x --version"\n', encoding="utf-8"
    )
    with pytest.raises(DoctorError, match="danh sách argv"):
        ToolManifest.load(tmp_path / "t.yaml")


def test_muc_thieu_ten_bi_tu_choi(tmp_path: Path) -> None:
    (tmp_path / "t.yaml").write_text('tools:\n  - check: ["x"]\n', encoding="utf-8")
    with pytest.raises(DoctorError, match="thiếu 'name'"):
        ToolManifest.load(tmp_path / "t.yaml")


def test_manifest_cua_pack_ghi_de_muc_trung_ten(tmp_path: Path) -> None:
    """Pack nói được "trên nền tảng này công cụ ấy phải là bản khác"."""
    (tmp_path / "engine.yaml").write_text(
        'scope: engine\ntools:\n  - name: cc\n    check: ["cc"]\n    min_version: "1.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "pack.yaml").write_text(
        'scope: "pack:x"\ntools:\n  - name: cc\n    check: ["cc"]\n    min_version: "9.9"\n',
        encoding="utf-8",
    )
    m = ToolManifest.load(tmp_path / "engine.yaml", tmp_path / "pack.yaml", pack="x")
    assert m.get("cc").min_version == "9.9"


# --------------------------------------------------------------------------
# TC-34 — quét và sinh lệnh cài
# --------------------------------------------------------------------------


def test_tc34_cong_cu_thieu_bi_bao_THIEU_kem_cong_bi_chan(doctor: Doctor) -> None:
    bao_cao = doctor.scan()
    thieu = next(r for r in bao_cao if r.spec.name == "cong-cu-khong-ton-tai")

    assert thieu.status == ToolStatus.MISSING
    assert thieu.blocking
    assert "static" in thieu.spec.gates

    van_ban = doctor.render_scan(bao_cao)
    assert "THIẾU" in van_ban
    assert "chặn cổng: static" in van_ban
    assert "KHÔNG được coi là đạt" in van_ban


def test_tc34_cong_cu_co_san_bi_bao_OK_kem_phien_ban(doctor: Doctor) -> None:
    bao_cao = doctor.scan()
    python = next(r for r in bao_cao if r.spec.name == "python")

    assert python.status == ToolStatus.OK
    assert python.version.startswith("3.")
    assert python.path


def test_tc34_fix_sinh_dung_lenh_theo_he_dieu_hanh(doctor: Doctor) -> None:
    import platform

    spec = doctor.manifest.get("cong-cu-khong-ton-tai")
    lenh = doctor.install_command(spec)

    he = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}[platform.system()]
    assert lenh == spec.install[he]


def test_tc34_fix_KHONG_tu_thuc_thi_khi_chua_xac_nhan(doctor: Doctor) -> None:
    """Điểm cốt lõi: doctor không bao giờ tự đổi máy của kỹ sư."""
    assert doctor.confirm is None
    with pytest.raises(InstallNotConfirmed, match="không có ai để xác nhận"):
        doctor.fix(doctor.scan())


def test_tc34_fix_hien_thi_NGUYEN_VAN_lenh_se_chay(doctor: Doctor) -> None:
    nhat_ky = doctor.fix(doctor.scan(), dry_run=True)
    assert any("sẽ chạy →" in d for d in nhat_ky)
    assert any("cong-cu-khong-ton-tai" in d for d in nhat_ky)


def test_tc34_nguoi_tu_choi_thi_khong_cai(doctor: Doctor) -> None:
    da_hoi: list[str] = []

    def tu_choi(ten: str, lenh: str) -> bool:
        da_hoi.append(ten)
        return False

    doctor.confirm = tu_choi
    nhat_ky = doctor.fix(doctor.scan())

    assert da_hoi == ["cong-cu-khong-ton-tai"]
    assert any("người dùng từ chối" in d for d in nhat_ky)


def test_khong_co_lenh_cai_cho_he_dieu_hanh_nay_thi_noi_ro(
    doctor: Doctor, tmp_path: Path
) -> None:
    (tmp_path / "t.yaml").write_text(
        'tools:\n  - name: x\n    check: ["khong-co-that"]\n    install:\n'
        '      solaris: ["pkg", "install", "x"]\n',
        encoding="utf-8",
    )
    d = Doctor(
        manifest=ToolManifest.load(tmp_path / "t.yaml"),
        tools_kb=tmp_path / "kb",
        env_lock=EnvLock(tmp_path / "lock.json"),
    )
    nhat_ky = d.fix(d.scan(), dry_run=True)
    assert any("Cài tay theo hướng dẫn" in n for n in nhat_ky)


# --------------------------------------------------------------------------
# TC-35 — checksum sai là TỪ CHỐI
# --------------------------------------------------------------------------


def test_tc35_checksum_dung_thi_di_qua(tmp_path: Path) -> None:
    import hashlib

    goi = tmp_path / "goi.tar.gz"
    goi.write_bytes(b"noi dung goi cai dat")
    dung = "sha256:" + hashlib.sha256(goi.read_bytes()).hexdigest()

    assert Doctor.verify_checksum(goi, dung) == dung
    assert Doctor.verify_checksum(goi, dung[7:]) == dung  # chấp nhận cả dạng trần


def test_tc35_checksum_sai_thi_TU_CHOI_cai(tmp_path: Path) -> None:
    goi = tmp_path / "goi.tar.gz"
    goi.write_bytes(b"goi da bi thay doi")

    with pytest.raises(ChecksumMismatch) as loi:
        Doctor.verify_checksum(goi, "sha256:" + "0" * 64)

    thong_diep = str(loi.value)
    assert "TỪ CHỐI cài đặt" in thong_diep
    assert "nguồn bị can thiệp" in thong_diep


def test_tc35_goi_khong_ton_tai_bao_loi(tmp_path: Path) -> None:
    with pytest.raises(DoctorError, match="Không tìm thấy gói"):
        Doctor.verify_checksum(tmp_path / "khong-co.tar.gz", "sha256:x")


# --------------------------------------------------------------------------
# TC-36 — khóa môi trường và phát hiện trôi phiên bản
# --------------------------------------------------------------------------


def test_tc36_khoa_moi_truong_sinh_env_hash(doctor: Doctor) -> None:
    khoa = doctor.lock(doctor.scan())
    assert khoa["env_hash"].startswith("sha256:")
    assert "python" in khoa["tools"]
    assert doctor.env_lock.read()["env_hash"] == khoa["env_hash"]


def test_tc36_moi_truong_khong_doi_thi_khong_bao_troi(doctor: Doctor) -> None:
    bao_cao = doctor.scan()
    doctor.lock(bao_cao)
    assert doctor.check_drift(bao_cao) == {}


def test_tc36_nang_phien_ban_thi_canh_bao_troi_moi_truong(doctor: Doctor) -> None:
    doctor.env_lock.write({"python": "3.10.0", "cppcheck": "2.10"})

    lech = doctor.env_lock.drift({"python": "3.12.13", "cppcheck": "2.10"})
    assert lech == {"python": ("3.10.0", "3.12.13")}


def test_tc36_cong_cu_bien_mat_cung_la_troi_moi_truong(doctor: Doctor) -> None:
    doctor.env_lock.write({"python": "3.12.13", "cppcheck": "2.10"})
    lech = doctor.env_lock.drift({"python": "3.12.13"})
    assert lech["cppcheck"] == ("2.10", "(không còn)")


def test_tc36_nguoi_chap_nhan_thi_khoa_cap_nhat_va_bam_doi(doctor: Doctor) -> None:
    cu = doctor.env_lock.write({"python": "3.10.0"})
    moi = doctor.env_lock.write({"python": "3.12.13"})

    assert moi["env_hash"] != cu["env_hash"]
    assert doctor.env_lock.drift({"python": "3.12.13"}) == {}


def test_env_hash_tat_dinh_va_khong_phu_thuoc_thu_tu() -> None:
    """Cùng một môi trường phải cho cùng một băm, nếu không việc so là vô nghĩa."""
    a = EnvLock.compute_hash({"b": "2", "a": "1"}, "linux")
    b = EnvLock.compute_hash({"a": "1", "b": "2"}, "linux")
    assert a == b
    assert EnvLock.compute_hash({"a": "1"}, "linux") != EnvLock.compute_hash({"a": "1"}, "macos")


def test_env_lock_hong_bao_loi(tmp_path: Path) -> None:
    path = tmp_path / "env_lock.json"
    path.write_text("{khong phai json", encoding="utf-8")
    with pytest.raises(DoctorError, match="JSON hỏng"):
        EnvLock(path).read()


# --------------------------------------------------------------------------
# TC-37 — smoke test và Thẻ công cụ
# --------------------------------------------------------------------------


def test_tc37_smoke_test_chay_that_va_kiem_dau_ra(doctor: Doctor) -> None:
    dat, dau_ra = doctor.smoke_test(doctor.manifest.get("python"))
    assert dat
    assert "eaa-smoke-ok" in dau_ra


def test_tc37_the_cong_cu_ghi_cu_phap_da_chung_minh_chay_duoc(doctor: Doctor) -> None:
    bao_cao = next(r for r in doctor.scan() if r.spec.name == "python")
    the = doctor.write_tool_card(bao_cao)

    assert the.name == "python"
    assert the.version.startswith("3.")
    assert Path(the.executable).exists()
    assert the.invocation[0] == sys.executable
    assert "unittests" in the.gates
    assert "eaa-smoke-ok" in the.smoke_output

    tren_dia = ToolCard.load(doctor.tools_kb / "python.json")
    assert tren_dia.to_dict() == the.to_dict()


def test_tc37_smoke_test_khong_dat_thi_KHONG_ghi_the(doctor: Doctor, tmp_path: Path) -> None:
    """Một thẻ ghi cú pháp chưa chứng minh được chính là nguồn ảo giác cú pháp."""
    (tmp_path / "t.yaml").write_text(
        textwrap.dedent(
            f"""\
            tools:
              - name: python
                check: ["{sys.executable}", "--version"]
                smoke: ["{sys.executable}", "-c", "raise SystemExit(3)"]
            """
        ),
        encoding="utf-8",
    )
    d = Doctor(
        manifest=ToolManifest.load(tmp_path / "t.yaml"),
        tools_kb=tmp_path / "kb",
        env_lock=EnvLock(tmp_path / "lock.json"),
    )
    bao_cao = d.scan()[0]

    with pytest.raises(DoctorError, match="ảo giác cú pháp lệnh"):
        d.write_tool_card(bao_cao)
    assert not (tmp_path / "kb" / "python.json").exists()


def test_tc37_the_cong_cu_nen_mot_dong_de_nap_vao_ngu_canh(doctor: Doctor) -> None:
    """AIS §9.5: thẻ được nạp dạng nén vào ngữ cảnh khi Agent cần sinh lệnh."""
    bao_cao = next(r for r in doctor.scan() if r.spec.name == "python")
    doctor.write_tool_card(bao_cao)

    dong = doctor.context_lines()
    assert len(dong) == 1
    assert dong[0].startswith("python ")
    assert "gọi:" in dong[0]
    assert len(dong[0]) < 300, "một dòng phải thật sự là một dòng"


def test_chua_co_the_nao_thi_tra_rong(doctor: Doctor) -> None:
    assert doctor.cards() == []
    assert doctor.context_lines() == []


def test_smoke_test_khong_khai_bao_thi_coi_nhu_dat(tmp_path: Path) -> None:
    (tmp_path / "t.yaml").write_text(
        f'tools:\n  - name: python\n    check: ["{sys.executable}", "--version"]\n',
        encoding="utf-8",
    )
    d = Doctor(
        manifest=ToolManifest.load(tmp_path / "t.yaml"),
        tools_kb=tmp_path / "kb",
        env_lock=EnvLock(tmp_path / "lock.json"),
    )
    dat, ghi_chu = d.smoke_test(d.manifest.get("python"))
    assert dat and "không khai báo" in ghi_chu


# --------------------------------------------------------------------------
# So phiên bản
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hien_tai", "toi_thieu", "dat"),
    [
        ("3.12.13", "3.10", True),
        ("3.10.0", "3.10", True),
        ("3.9.6", "3.10", False),
        ("12.2.0", "12.0", True),
        ("2.9", "2.10", False),      # so theo số, không so theo chuỗi
        ("2.10", "2.9", True),
    ],
)
def test_so_phien_ban_theo_semver(hien_tai: str, toi_thieu: str, dat: bool) -> None:
    from eaa.doctor import _compare

    assert _compare(hien_tai, toi_thieu) is dat


def test_khong_doc_duoc_phien_ban_thi_khong_ket_luan_la_qua_cu() -> None:
    """Thà báo KHÔNG RÕ còn hơn báo QUÁ CŨ cho một công cụ vẫn dùng được."""
    from eaa.doctor import _compare

    assert _compare("", "3.10") is True
    assert _compare("bản dựng nội bộ", "3.10") is True
