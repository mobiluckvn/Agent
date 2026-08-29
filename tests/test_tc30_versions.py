"""TC-30, TC-31 — ba hạng chất lượng, bản known-good và quay lui.

| Mã | Yêu cầu | Kiểm ở đây |
|---|---|---|
| TC-30 | Bản mới fail nghiệm thu vật lý tại G4 | `rollback` đưa về known-good gần nhất; build ledger ghi sự kiện kèm lý do; **known_good.lock KHÔNG đổi** |
| TC-31 | "Bản tốt nhất hiện tại của toàn firmware?" | `report versions` trả commit hw-verified mới nhất kèm số đo đi kèm |

Vế in đậm của TC-30 là vế dễ làm sai nhất. Quay lui KHÔNG phải một lần nghiệm
thu — bản đang được lùi về vốn đã là bản known-good rồi. Nếu quay lui cũng cập
nhật khóa thì khóa mất nghĩa: nó sẽ ghi lại thời điểm của lần hỏng gần nhất
thay vì thời điểm của lần nghiệm thu gần nhất.

Ranh giới người–máy nằm rõ nhất ở đây: hai hạng dưới máy tự chấm được, hạng
trên cùng thì không — nó khẳng định một điều về thế giới vật lý.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaa.gates import APPROVED, REJECTED, GateDecision
from eaa.tools.compile import write_artifact
from eaa.tools.base import CodeArtifact
from eaa.vcs import GitRepo
from eaa.versions import (
    ACCEPTANCE_GATE,
    TIER_ORDER,
    Measurement,
    NoKnownGood,
    PromotionNotAuthorized,
    Tier,
    VersionError,
    VersionRegistry,
)


def _quyet_dinh(gate: str = ACCEPTANCE_GATE, decision: str = APPROVED) -> GateDecision:
    return GateDecision(
        gate_id=gate,
        decision=decision,
        actor="Vũ Trí Công",
        decided_at="2026-08-29T15:00:00+00:00",
        payload_digest="sha256:payload",
        content_digest="sha256:noi_dung",
        module="pid_controller",
        reason="" if decision == APPROVED else "dao động vượt ±1°",
    )


SO_DO = (
    Measurement("goc_nghieng_max", 0.8, "°", "3 kịch bản, 20 phút"),
    Measurement("loop_latency", 8.4, "ms"),
    Measurement("jitter", 210, "µs"),
)


@pytest.fixture()
def kho(tmp_path: Path) -> VersionRegistry:
    return VersionRegistry(
        ledger_path=tmp_path / "build_ledger.jsonl",
        lock_path=tmp_path / "known_good.lock",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> GitRepo:
    r = GitRepo(tmp_path / "firmware")
    r.init()
    return r


def _commit(repo: GitRepo, noi_dung: str) -> str:
    artifact = CodeArtifact(
        files={"src/pid_controller.c": noi_dung},
        prompt_hash="sha256:p",
        model="gemini-3.1-pro-preview",
        constraints_version="sha256:c",
    )
    write_artifact(artifact, repo.root)
    return repo.commit_artifact(artifact, module_id="pid_controller")


# --------------------------------------------------------------------------
# Phong hạng — ranh giới người/máy
# --------------------------------------------------------------------------


def test_hai_hang_duoi_may_tu_chuyen_duoc(kho: VersionRegistry) -> None:
    kho.promote(module="pid_controller", commit="aaa111", tier=Tier.BUILD_OK)
    kho.promote(module="pid_controller", commit="aaa111", tier=Tier.SIM_VERIFIED)

    assert kho.status("pid_controller")["tier"] == Tier.SIM_VERIFIED
    assert kho.known_good_of("pid_controller") == "", "chưa qua G4 thì chưa known-good"


def test_hang_cao_nhat_can_phe_duyet_tai_G4(kho: VersionRegistry) -> None:
    """Máy không nhìn thấy rung cơ khí, nhiệt độ hay sụt áp."""
    with pytest.raises(PromotionNotAuthorized, match=ACCEPTANCE_GATE):
        kho.promote(
            module="pid_controller",
            commit="aaa111",
            tier=Tier.HW_VERIFIED,
            measurements=SO_DO,
        )


@pytest.mark.parametrize("gate_khac", ["G1", "G2", "G3", "G5"])
def test_duyet_gate_khac_khong_phong_duoc_hang_cao_nhat(
    kho: VersionRegistry, gate_khac: str
) -> None:
    with pytest.raises(PromotionNotAuthorized, match="Duyệt một gate khác"):
        kho.promote(
            module="pid_controller",
            commit="aaa111",
            tier=Tier.HW_VERIFIED,
            decision=_quyet_dinh(gate=gate_khac),
            measurements=SO_DO,
        )


def test_G4_tu_choi_thi_khong_phong_duoc(kho: VersionRegistry) -> None:
    with pytest.raises(PromotionNotAuthorized, match="rejected"):
        kho.promote(
            module="pid_controller",
            commit="aaa111",
            tier=Tier.HW_VERIFIED,
            decision=_quyet_dinh(decision=REJECTED),
            measurements=SO_DO,
        )


def test_hang_cao_nhat_bat_buoc_kem_SO_DO(kho: VersionRegistry) -> None:
    """Hạng này khẳng định một điều về thiết bị thật — phải có bằng chứng đo."""
    with pytest.raises(PromotionNotAuthorized, match="không có số đo"):
        kho.promote(
            module="pid_controller",
            commit="aaa111",
            tier=Tier.HW_VERIFIED,
            decision=_quyet_dinh(),
        )


def test_phong_hang_cao_nhat_cap_nhat_known_good(kho: VersionRegistry) -> None:
    kho.promote(
        module="pid_controller",
        commit="aaa111",
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )

    assert kho.known_good_of("pid_controller") == "aaa111"
    khoa = kho.known_good()
    assert khoa["firmware"] == "aaa111"
    assert any("goc_nghieng_max" in m for m in khoa["modules"]["pid_controller"]["measurements"])


def test_hang_khong_hop_le_bi_tu_choi(kho: VersionRegistry) -> None:
    with pytest.raises(VersionError, match="Hạng không hợp lệ"):
        kho.promote(module="m", commit="a", tier="tu-nghi-ra")


def test_phong_hang_khong_neu_commit_bi_tu_choi(kho: VersionRegistry) -> None:
    with pytest.raises(VersionError, match="nêu commit"):
        kho.promote(module="m", commit="", tier=Tier.BUILD_OK)


def test_thu_tu_hang_tang_dan(kho: VersionRegistry) -> None:
    assert TIER_ORDER == (Tier.BUILD_OK, Tier.SIM_VERIFIED, Tier.HW_VERIFIED)


# --------------------------------------------------------------------------
# TC-30 — quay lui
# --------------------------------------------------------------------------


def test_tc30_ban_moi_fail_nghiem_thu_thi_quay_lui_ve_known_good(
    kho: VersionRegistry, repo: GitRepo
) -> None:
    kho.repo = repo

    tot = _commit(repo, "// bản đã nghiệm thu\nvoid pid_step(void) {}\n")
    kho.promote(
        module="pid_controller",
        commit=tot,
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )

    hong = _commit(repo, "// bản mới, robot dao động quá biên\nvoid pid_step(void) { }\n")
    kho.reject_acceptance(
        module="pid_controller",
        commit=hong,
        reason="dao động ±2,3° vượt ngưỡng ±1° ở kịch bản kháng nhiễu",
        actor="Vũ Trí Công",
    )

    ban_ghi = kho.rollback(
        "pid_controller", reason="không đạt nghiệm thu vật lý", actor="Vũ Trí Công"
    )

    assert ban_ghi.event == "rollback"
    assert ban_ghi.commit == tot
    noi_dung = (repo.root / "src" / "pid_controller.c").read_text(encoding="utf-8")
    assert "bản đã nghiệm thu" in noi_dung


def test_tc30_known_good_KHONG_doi_sau_khi_quay_lui(kho: VersionRegistry) -> None:
    """Quay lui không phải một lần nghiệm thu — bản lùi về vốn đã là known-good."""
    kho.promote(
        module="pid_controller",
        commit="tot111",
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )
    truoc = json.loads(Path(kho.lock_path).read_text(encoding="utf-8"))

    kho.promote(module="pid_controller", commit="hong222", tier=Tier.SIM_VERIFIED)
    kho.reject_acceptance(module="pid_controller", commit="hong222", reason="ngã")
    kho.rollback("pid_controller", reason="không đạt nghiệm thu")

    assert json.loads(Path(kho.lock_path).read_text(encoding="utf-8")) == truoc


def test_tc30_build_ledger_ghi_su_kien_kem_LY_DO(kho: VersionRegistry) -> None:
    """Thất bại cũng là tri thức — không lặng lẽ lùi rồi làm như chưa có gì."""
    kho.promote(
        module="pid_controller",
        commit="tot111",
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )
    kho.rollback(
        "pid_controller", reason="dao động vượt ngưỡng ở kịch bản dài hạn", actor="Vũ Trí Công"
    )

    su_kien = [r for r in kho.records("pid_controller") if r.event == "rollback"]
    assert len(su_kien) == 1
    assert "dao động vượt ngưỡng" in su_kien[0].reason
    assert su_kien[0].actor == "Vũ Trí Công"


def test_tc30_tu_choi_nghiem_thu_bat_buoc_kem_ly_do(kho: VersionRegistry) -> None:
    with pytest.raises(VersionError, match="bắt buộc kèm lý do"):
        kho.reject_acceptance(module="m", commit="a", reason="   ")


def test_chua_co_known_good_thi_khong_quay_lui_duoc(kho: VersionRegistry) -> None:
    kho.promote(module="pid_controller", commit="aaa", tier=Tier.SIM_VERIFIED)
    with pytest.raises(NoKnownGood, match=ACCEPTANCE_GATE):
        kho.rollback("pid_controller", reason="thử")


def test_quay_lui_ghi_commit_co_ly_do_trong_git(kho: VersionRegistry, repo: GitRepo) -> None:
    kho.repo = repo
    tot = _commit(repo, "// bản tốt\n")
    kho.promote(
        module="pid_controller", commit=tot, tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(), measurements=SO_DO,
    )
    _commit(repo, "// bản hỏng\n")
    kho.rollback("pid_controller", reason="ngã ở kịch bản kháng nhiễu", actor="Vũ Trí Công")

    thong_diep = repo.commit_message()
    assert "Quay lui pid_controller" in thong_diep
    assert "ngã ở kịch bản kháng nhiễu" in thong_diep


# --------------------------------------------------------------------------
# TC-31 — báo cáo phiên bản
# --------------------------------------------------------------------------


def test_tc31_bao_cao_tra_commit_hw_verified_kem_SO_DO(kho: VersionRegistry) -> None:
    kho.promote(module="drv_i2c_mpu6050", commit="bbb222", tier=Tier.SIM_VERIFIED)
    kho.promote(
        module="pid_controller",
        commit="aaa111",
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )

    van_ban = kho.report()

    assert "pid_controller" in van_ban and "aaa111"[:10] in van_ban
    assert Tier.HW_VERIFIED in van_ban
    assert "goc_nghieng_max=0.8°" in van_ban
    assert "loop_latency=8.4ms" in van_ban
    # Module chưa nghiệm thu thì hiện đúng hạng của nó, không hiện known-good.
    assert Tier.SIM_VERIFIED in van_ban


def test_tc31_tra_loi_duoc_ban_tot_nhat_cua_TOAN_FIRMWARE(kho: VersionRegistry) -> None:
    kho.promote(
        module="pid_controller",
        commit="aaa111",
        tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(),
        measurements=SO_DO,
    )
    van_ban = kho.report()
    assert "Bản known-good của toàn firmware: aaa111" in van_ban


def test_tc31_bao_cao_hien_so_lan_that_bai(kho: VersionRegistry) -> None:
    kho.promote(
        module="pid_controller", commit="aaa", tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(), measurements=SO_DO,
    )
    kho.reject_acceptance(module="pid_controller", commit="bbb", reason="ngã")
    kho.rollback("pid_controller", reason="ngã")

    van_ban = kho.report()
    assert "1 lần không đạt nghiệm thu, 1 lần quay lui" in van_ban


def test_tc31_bao_cao_noi_ro_khoa_chi_cap_nhat_tai_G4(kho: VersionRegistry) -> None:
    kho.promote(module="m", commit="a", tier=Tier.BUILD_OK)
    assert f"Chỉ cập nhật tại {ACCEPTANCE_GATE}" in kho.report()


def test_chua_co_build_nao_thi_bao_cao_noi_ro(kho: VersionRegistry) -> None:
    assert "chưa có bản build nào" in kho.report()


def test_gan_tag_git_khi_nghiem_thu(kho: VersionRegistry, repo: GitRepo) -> None:
    """AIS §8.4: tag hw-verified/<module>/vN gắn với bản ghi đo."""
    kho.repo = repo
    commit = _commit(repo, "// bản tốt\n")
    kho.promote(
        module="pid_controller", commit=commit, tier=Tier.HW_VERIFIED,
        decision=_quyet_dinh(), measurements=SO_DO,
    )
    assert "hw-verified/pid_controller/v1" in repo.tags()


def test_ban_ghi_hong_bao_loi_kem_so_dong(kho: VersionRegistry) -> None:
    kho.promote(module="m", commit="a", tier=Tier.BUILD_OK)
    with open(kho.ledger_path, "a", encoding="utf-8") as f:
        f.write("khong-phai-json\n")
    with pytest.raises(VersionError, match=":2:"):
        kho.records()


def test_known_good_hong_bao_loi(kho: VersionRegistry) -> None:
    kho.lock_path.parent.mkdir(parents=True, exist_ok=True)
    kho.lock_path.write_text("{khong phai json", encoding="utf-8")
    with pytest.raises(VersionError, match="JSON hỏng"):
        kho.known_good()
