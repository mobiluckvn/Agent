"""TC-39 — tự tìm công cụ chưa biết (AIS §9.2 chế độ 3, §9.4, FR-ENV-03).

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-39a | Nhu cầu công cụ suy từ Platform Pack | pack đổi lệnh thì nhu cầu đổi theo; chỗ giữ `{python}` không tính là công cụ phải cài |
| TC-39b | Đề xuất chỉ dùng nguồn cài cho phép | trình quản lý gói ngoài danh sách, nối lệnh, tải-rồi-chạy, tải trực tiếp thiếu checksum — đều bị chặn TRƯỚC khi tới tay người |
| TC-39c | Đề xuất là *proposed fact* | tra cứu xong chưa vào manifest, chưa cài được |
| TC-39d | Duyệt rồi mới ghi manifest | append + supersede, mang theo dấu vết người duyệt |

Điều nhóm test này giữ: **doctor không được tự bịa ra một lệnh cài rồi chạy
nó.** Ba chốt chặn nằm nối tiếp — kiểm nguồn bằng máy, người duyệt ở G2, xác
nhận từng lệnh lúc cài — và mỗi chốt phải hỏng độc lập thì mới có ý nghĩa, nên
mỗi chốt được kiểm riêng ở đây.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eaa.toolsearch import (
    LlmToolResearcher,
    ToolProposal,
    ToolRequirement,
    ToolSearchError,
    UnsafeInstallSource,
    append_to_manifest,
    derive_requirements,
    validate_proposal,
)

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# TC-39a — nhu cầu suy từ pack, không chép tay
# --------------------------------------------------------------------------


def _pack(tmp_path: Path, **capabilities: list[str]) -> object:
    """Pack tối thiểu hợp lệ, chỉ khai những năng lực bài test quan tâm.

    Năng lực bắt buộc mà bài test không nêu được lấp bằng chỗ giữ ``{python}``:
    pack vẫn hợp lệ, mà ``derive_requirements`` bỏ qua chúng, nên kết quả chỉ
    còn đúng thứ bài test dựng lên.
    """
    from eaa.platform import REQUIRED_CAPABILITIES, load_manifest

    kha_nang = {
        ten: ["{python}", "-c", "pass"]
        for ten in REQUIRED_CAPABILITIES
        if ten not in capabilities
    }
    kha_nang.update(capabilities)

    thu_muc = tmp_path / "packs" / "thu"
    thu_muc.mkdir(parents=True)
    (thu_muc / "pack.yaml").write_text(
        yaml.safe_dump(
            {
                "pack": "thu",
                "version": "1.0",
                "targets": ["thiet-bi-thu"],
                "capabilities": {
                    ten: {"command": cmd, "output": "{output}"}
                    for ten, cmd in kha_nang.items()
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return load_manifest(thu_muc)


def test_nhu_cau_di_theo_pack(tmp_path: Path) -> None:
    """Đổi lệnh trong pack thì nhu cầu công cụ đổi theo — không phải sửa hai chỗ."""
    pack = _pack(
        tmp_path,
        compile=["cong-cu-bien-dich", "-c", "{source}"],
        size=["cong-cu-do-kich-thuoc", "{output}"],
    )
    yc = {r.program: r for r in derive_requirements(pack)}
    assert set(yc) == {"cong-cu-bien-dich", "cong-cu-do-kich-thuoc"}
    assert yc["cong-cu-bien-dich"].capabilities == ("compile",)
    assert yc["cong-cu-bien-dich"].pack == "thu"


def test_mot_cong_cu_phuc_vu_nhieu_nang_luc(tmp_path: Path) -> None:
    """Thiếu nó thì chặn mấy cổng — báo cáo phải nói được câu đó."""
    pack = _pack(
        tmp_path,
        compile=["cong-cu-chung", "-c", "{source}"],
        size=["cong-cu-chung", "--size", "{output}"],
    )
    (yc,) = derive_requirements(pack)
    assert yc.capabilities == ("compile", "size")


def test_bo_qua_cho_giu(tmp_path: Path) -> None:
    """``{python}`` là chương trình engine quyết định lúc chạy, không phải thứ phải cài."""
    pack = _pack(tmp_path, sim=["{python}", "sim_runner.py"])
    assert derive_requirements(pack) == []


def test_pack_avr_that_suy_ra_du_ba_cong_cu() -> None:
    from eaa.platform import load_manifest

    can = {r.program for r in derive_requirements(load_manifest(REPO / "packs" / "avr"))}
    assert {"avr-gcc", "avr-size", "avrdude"} <= can


# --------------------------------------------------------------------------
# TC-39b — giới hạn an toàn của nguồn cài (AIS §9.4)
# --------------------------------------------------------------------------


def _de_xuat(**thay_doi: object) -> ToolProposal:
    mac_dinh: dict[str, object] = {
        "name": "cong-cu-thu",
        "description": "Công cụ dùng để thử.",
        "min_version": "1.0",
        "check": ("cong-cu-thu", "--version"),
        "install": {"macos": ("brew", "install", "cong-cu-thu")},
        "rationale": "Pack gọi nó.",
    }
    mac_dinh.update(thay_doi)
    return ToolProposal(**mac_dinh)  # type: ignore[arg-type]


def test_de_xuat_hop_le_di_qua() -> None:
    dx = _de_xuat(
        install={
            "macos": ("brew", "install", "cong-cu-thu"),
            "linux": ("sudo", "apt-get", "install", "-y", "cong-cu-thu"),
            "windows": ("winget", "install", "-e", "--id", "Nha.CongCu"),
        }
    )
    assert validate_proposal(dx) is dx


def test_chan_trinh_quan_ly_goi_ngoai_danh_sach() -> None:
    with pytest.raises(UnsafeInstallSource, match="không nằm trong danh sách"):
        validate_proposal(_de_xuat(install={"macos": ("nguon-la", "install", "x")}))


def test_chan_lenh_khong_phai_lenh_cai() -> None:
    """Chỉ chấp nhận lệnh CÀI. ``brew`` + động từ khác là một lệnh tùy ý."""
    with pytest.raises(UnsafeInstallSource, match="động từ cài"):
        validate_proposal(_de_xuat(install={"macos": ("brew", "cleanup", "--prune=all")}))


@pytest.mark.parametrize(
    "lenh",
    [
        ("brew", "install", "x;", "rm", "-rf", "/"),
        ("brew", "install", "x", "&&", "curl", "http://xyz"),
        ("sh", "-c", "brew install x"),
        ("curl", "-fsSL", "https://xyz/i.sh"),
        ("brew", "install", "$(echo x)"),
    ],
)
def test_chan_noi_lenh_va_tai_roi_chay(lenh: tuple[str, ...]) -> None:
    """Engine chạy argv không qua shell, nhưng đề xuất chứa những thứ này
    nghĩa là mô hình đang cố làm việc khác "cài một gói" — đủ để từ chối."""
    with pytest.raises(UnsafeInstallSource):
        validate_proposal(_de_xuat(install={"macos": lenh}))


def test_sudo_khong_che_duoc_nguon_la() -> None:
    """``sudo`` chỉ là tiền tố; thứ bị kiểm là chương trình đứng sau nó."""
    with pytest.raises(UnsafeInstallSource, match="không nằm trong danh sách"):
        validate_proposal(_de_xuat(install={"linux": ("sudo", "nguon-la", "install", "x")}))


def test_tai_truc_tiep_phai_https_va_dung_mien() -> None:
    with pytest.raises(UnsafeInstallSource, match="HTTPS"):
        validate_proposal(_de_xuat(download="http://gnu.org/x.tar.gz", checksum="a" * 64))
    with pytest.raises(UnsafeInstallSource, match="ngoài danh sách"):
        validate_proposal(_de_xuat(download="https://xyz.vn/x.tar.gz", checksum="a" * 64))


def test_mien_so_theo_hau_to_khong_so_chuoi_con() -> None:
    """``gnu.org.xyz.vn`` chứa chuỗi ``gnu.org`` nhưng không phải miền của GNU."""
    with pytest.raises(UnsafeInstallSource, match="ngoài danh sách"):
        validate_proposal(
            _de_xuat(download="https://gnu.org.xyz.vn/x.tar.gz", checksum="a" * 64)
        )
    assert validate_proposal(
        _de_xuat(download="https://ftp.gnu.org/x.tar.gz", checksum="a" * 64)
    )


def test_tai_truc_tiep_bat_buoc_kem_checksum() -> None:
    with pytest.raises(UnsafeInstallSource, match="checksum"):
        validate_proposal(_de_xuat(download="https://ftp.gnu.org/x.tar.gz"))
    with pytest.raises(UnsafeInstallSource, match="checksum"):
        validate_proposal(
            _de_xuat(download="https://ftp.gnu.org/x.tar.gz", checksum="quá-ngắn")
        )


def test_thieu_lenh_kiem_tra_thi_khong_de_xuat_duoc() -> None:
    """Không có lệnh kiểm phiên bản thì doctor không xác nhận được đã cài hay chưa."""
    with pytest.raises(ToolSearchError, match="lệnh kiểm tra"):
        validate_proposal(_de_xuat(check=()))


def test_khong_co_lenh_cai_nao() -> None:
    with pytest.raises(ToolSearchError, match="không có lệnh cài"):
        validate_proposal(_de_xuat(install={}))


# --------------------------------------------------------------------------
# TC-39c — tra cứu bằng mô hình trả về *proposed fact*
# --------------------------------------------------------------------------

_JSON_TOT = """Đây là công cụ cần dùng:

```json
{
  "name": "cong-cu-thu",
  "description": "Công cụ thử.",
  "min_version": "2.1",
  "check": ["cong-cu-thu", "--version"],
  "install": {"macos": ["brew", "install", "cong-cu-thu"]},
  "smoke": ["cong-cu-thu", "--help"],
  "smoke_expect": "usage",
  "homepage": "https://example.org",
  "rationale": "Pack gọi nó để biên dịch."
}
```
"""


class _LlmGia:
    """Adapter tối thiểu — chỉ có ``complete``, đúng thứ bộ tra cứu cần."""

    provider = "gia"
    model = "mo-hinh-gia-1"

    def __init__(self, tra_ve: str) -> None:
        self.tra_ve = tra_ve
        self.prompts: list[object] = []

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def complete(self, prompt: object) -> str:
        self.prompts.append(prompt)
        return self.tra_ve


def test_tra_cuu_boc_duoc_json_lan_trong_van_xuoi() -> None:
    llm = _LlmGia(_JSON_TOT)
    yc = ToolRequirement(program="cong-cu-thu", capabilities=("compile",), pack="thu")
    dx = LlmToolResearcher(llm=llm).propose(yc, os_key="macos")

    assert dx.name == "cong-cu-thu"
    assert dx.min_version == "2.1"
    assert dx.install["macos"] == ("brew", "install", "cong-cu-thu")
    assert dx.gates == ("compile",)
    assert dx.scope == "pack:thu"
    assert dx.proposed_by == "mo-hinh-gia-1", "phải truy vết được mô hình nào đề xuất"


def test_tra_cuu_khong_dung_duong_sinh_ma() -> None:
    """Tra cứu là câu hỏi văn xuôi. Bắt nó trả khối ```file: thì mọi phản hồi
    đúng đắn đều bị tính là hỏng định dạng — chính lỗi đã gặp khi chạy thật."""
    llm = _LlmGia(_JSON_TOT)
    yc = ToolRequirement(program="cong-cu-thu", capabilities=("compile",))
    LlmToolResearcher(llm=llm).propose(yc)
    assert llm.prompts, "phải đi qua complete(), không qua generate()"


def test_khong_boc_duoc_json_thi_bo_de_xuat_chu_khong_doan() -> None:
    llm = _LlmGia("Tôi không chắc công cụ này tồn tại.")
    yc = ToolRequirement(program="cong-cu-la", capabilities=("compile",))
    with pytest.raises(ToolSearchError):
        LlmToolResearcher(llm=llm).propose(yc)


def test_json_hong_thi_bo_de_xuat() -> None:
    llm = _LlmGia('```json\n{"name": "x", }\n```')
    yc = ToolRequirement(program="x", capabilities=("compile",))
    with pytest.raises(ToolSearchError, match="JSON hỏng"):
        LlmToolResearcher(llm=llm).propose(yc)


def test_de_xuat_khong_tu_vao_manifest(tmp_path: Path) -> None:
    """TC-39c: tra cứu xong là *proposed fact*, manifest vẫn nguyên."""
    manifest = tmp_path / "tools.yaml"
    manifest.write_text("scope: engine\ntools: []\n", encoding="utf-8")

    llm = _LlmGia(_JSON_TOT)
    yc = ToolRequirement(program="cong-cu-thu", capabilities=("compile",))
    LlmToolResearcher(llm=llm).propose(yc)

    assert yaml.safe_load(manifest.read_text(encoding="utf-8"))["tools"] == []


# --------------------------------------------------------------------------
# TC-39d — duyệt rồi mới ghi manifest, append + supersede
# --------------------------------------------------------------------------


def test_ghi_manifest_mang_theo_dau_vet_nguoi_duyet(tmp_path: Path) -> None:
    manifest = tmp_path / "tools.yaml"
    append_to_manifest(manifest, _de_xuat(gates=("compile",)), actor="ky-su-a")

    du_lieu = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    (muc,) = du_lieu["tools"]
    assert muc["name"] == "cong-cu-thu"
    assert muc["approved_by"] == "ky-su-a"
    assert muc["approved_at"]
    assert muc["gates"] == ["compile"]
    assert muc["check"] == ["cong-cu-thu", "--version"]


def test_ban_cu_khong_bi_xoa_ma_bi_thay_the(tmp_path: Path) -> None:
    """AIS §8.1: append-only. Câu "hôm trước manifest ghi gì" phải tra được."""
    manifest = tmp_path / "tools.yaml"
    append_to_manifest(manifest, _de_xuat(min_version="1.0"), actor="ky-su-a")
    append_to_manifest(manifest, _de_xuat(min_version="2.0"), actor="ky-su-b")

    muc = yaml.safe_load(manifest.read_text(encoding="utf-8"))["tools"]
    assert len(muc) == 2, "bản cũ bị xóa mất"
    cu, moi = muc
    assert cu["min_version"] == "1.0"
    assert cu["superseded_by"], "bản cũ phải được đánh dấu đã bị thay"
    assert cu["level"] == "Optional", "bản cũ không còn là điều kiện bắt buộc"
    assert moi["min_version"] == "2.0"
    assert not moi.get("superseded_by")


def test_manifest_ghi_ra_nap_lai_duoc(tmp_path: Path) -> None:
    """Vòng khép kín: thứ ghi ra phải là thứ doctor đọc lại được."""
    from eaa.doctor import ToolManifest

    manifest = tmp_path / "tools.yaml"
    append_to_manifest(
        manifest,
        _de_xuat(gates=("compile",), smoke=("cong-cu-thu", "--help"), smoke_expect="usage"),
        actor="ky-su-a",
    )
    m = ToolManifest.load(manifest)
    (spec,) = m.specs
    assert spec.name == "cong-cu-thu"
    assert spec.min_version == "1.0"
    assert spec.smoke_expect == "usage"


def test_de_xuat_khoi_phuc_lai_nguyen_ven() -> None:
    """Đề xuất phải sống qua khoảng giữa lúc tra cứu và lúc người duyệt.

    Mục manifest gộp mô tả và lý do vào một dòng cho người đọc, nên không dựng
    lại được đề xuất từ nó — thứ được duyệt phải đúng thứ đã trình lên.
    """
    goc = _de_xuat(
        gates=("compile", "size"),
        smoke=("cong-cu-thu", "--help"),
        smoke_expect="usage",
        homepage="https://example.org",
        proposed_by="mo-hinh-gia-1",
    )
    lai = ToolProposal.from_dict(goc.to_dict())
    assert lai == goc


def test_bam_de_xuat_doi_khi_lenh_cai_doi() -> None:
    """Duyệt "công cụ X" là duyệt cả cách cài X.

    Nếu băm chỉ tính tên thì đổi lệnh cài sau khi trình lên vẫn khớp quyết định
    cũ — và người đã duyệt một thứ khác với thứ sắp chạy.
    """
    a = _de_xuat(install={"macos": ("brew", "install", "cong-cu-thu")})
    b = _de_xuat(install={"macos": ("brew", "install", "goi-khac")})
    assert a.digest_line != b.digest_line


def test_pack_khai_phien_ban_thi_pack_thang(tmp_path: Path) -> None:
    """``tool_requirements`` của pack đè lên phiên bản mô hình đoán.

    Pack là tài liệu thiết kế đã qua G1; đề xuất của mô hình là tri thức tra
    cứu. Khi hai bên nói khác nhau — và chúng đã nói khác nhau trong lần chạy
    thật đầu tiên: pack ghi ``avr-gcc >=12.0`` còn mô hình đề xuất 7.3 — thì
    lấy theo pack, nếu không doctor sẽ chấp nhận một toolchain mà pack không
    chạy nổi.
    """
    thu_muc = tmp_path / "packs" / "thu"
    _pack(tmp_path, compile=["cong-cu-bien-dich", "-c", "{source}"])
    du_lieu = yaml.safe_load((thu_muc / "pack.yaml").read_text(encoding="utf-8"))
    du_lieu["tool_requirements"] = {"cong-cu-bien-dich": ">=12.0"}
    (thu_muc / "pack.yaml").write_text(
        yaml.safe_dump(du_lieu, allow_unicode=True), encoding="utf-8"
    )

    from eaa.platform import load_manifest

    (yc,) = [
        r for r in derive_requirements(load_manifest(thu_muc))
        if r.program == "cong-cu-bien-dich"
    ]
    assert yc.min_version == ">=12.0"

    llm = _LlmGia(
        _JSON_TOT.replace('"name": "cong-cu-thu"', '"name": "cong-cu-bien-dich"')
    )
    dx = LlmToolResearcher(llm=llm).propose(yc)
    assert dx.min_version == "12.0", "phiên bản của pack phải thắng"
