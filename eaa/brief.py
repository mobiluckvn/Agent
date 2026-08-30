"""Khởi tạo dự án bằng hội thoại — công đoạn A1/B2 do Agent dẫn dắt.

EAA-AIS-05 §6.1, quy trình P1; FR-GAP-02. Nghiệp vụ N-001..N-006.
Xem `docs/SAI_LECH_THIET_KE.md` mục SL-42.

Trước module này, ``eaa init`` đòi ``constraints.yaml`` và
``hardware_profile.yaml`` ĐÃ CÓ SẴN, và không lệnh nào giúp tạo ra chúng. Người
dùng phải tự biết cần khai những trường gì, tự tra tần số đồng hồ, tự quyết
chu kỳ điều khiển — tức là phải hiểu kiến trúc bên trong mới bắt đầu được. Đó
là rào cản ở đúng bước đầu tiên.

Thứ tự bốn bước, và thứ tự ấy là điểm chính
--------------------------------------------

1. **Dò trước khi hỏi.** Máy tự biết được gì thì không hỏi. Cắm bo vào là đã có
   VID/PID, cổng nối tiếp, ổ nạp — hỏi lại những thứ ấy là bắt người làm việc
   của máy.
2. **Nhận dạng từ dấu hiệu dò được.** Không chắc thì đưa vài ứng viên KÈM CÁCH
   PHÂN BIỆT, không chọn bừa một cái.
3. **Hỏi đúng phần máy không biết.** Chu kỳ điều khiển, đối tượng điều khiển,
   mức ưu tiên — không dấu hiệu vật lý nào cho ra được, chỉ người biết.
4. **Sinh hồ sơ ở dạng ĐỀ XUẤT**, kèm xuất xứ từng dòng, rồi để người duyệt.

Ba loại dữ kiện, không được trộn
---------------------------------

Mỗi giá trị trong hồ sơ sinh ra phải nói được nó từ đâu:

* **ĐÃ KIỂM** — máy tự đo được trên máy này (VID/PID, tên cổng, nhãn ổ nạp).
* **NGƯỜI NÓI** — người dùng trả lời. Đáng tin, nhưng vẫn là lời khai.
* **TRA CỨU** — mô hình hoặc tài liệu đề xuất. Là *proposed fact*, và phải kèm
  cách kiểm.

Trộn ba loại này vào cùng một tệp mà không phân biệt là cách kho tri thức mục
ruỗng từ bên trong: sáu tháng sau không ai biết con số nào đo được, con số nào
đoán ra. Nên mọi thứ chưa kiểm được đều xuống mục ``assumptions`` kèm cách
kiểm, chứ không nằm lẫn như sự thật.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import yaml

__all__ = [
    "BriefError",
    "ProbedDevice",
    "ProbeResult",
    "Question",
    "QUESTIONS",
    "BoardCandidate",
    "ProjectDraft",
    "probe_hardware",
    "identify_board",
    "remaining_questions",

    "DA_KIEM",
    "NGUOI_NOI",
    "TRA_CUU",
]

#: Ba loại xuất xứ của một dữ kiện. Xem phần đầu tệp.
DA_KIEM = "đã kiểm"
NGUOI_NOI = "người nói"
TRA_CUU = "tra cứu"


class BriefError(Exception):
    """Không dựng được bản nháp hồ sơ dự án."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Bước 1 — dò trước khi hỏi
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbedDevice:
    """Một thiết bị máy tự nhìn thấy."""

    port: str = ""
    vid: str = ""
    pid: str = ""
    description: str = ""
    serial_number: str = ""
    #: Ổ đĩa mà mạch nạp bày ra (kiểu thả tệp để nạp).
    volume: str = ""
    volume_label: str = ""

    @property
    def identifiable(self) -> bool:
        return bool(self.vid or self.volume_label)

    def render(self) -> str:
        phan = []
        if self.port:
            phan.append(self.port)
        if self.vid:
            phan.append(f"{self.vid}:{self.pid}")
        if self.description:
            phan.append(self.description)
        if self.volume:
            phan.append(f"ổ nạp {self.volume}")
        return "  " + "  ·  ".join(phan)


@dataclass
class ProbeResult:
    """Toàn bộ thứ máy tự dò được, và thứ nó KHÔNG dò được."""

    devices: list[ProbedDevice] = field(default_factory=list)
    #: Lý do không đọc được VID/PID, nếu có — nói ra thay vì im lặng.
    limits: list[str] = field(default_factory=list)

    def render(self) -> str:
        if not self.devices:
            dong = [
                "Không thấy thiết bị nào.",
                "  · Bo đã cắm và đã cấp nguồn chưa?",
                "  · Máy đã có trình điều khiển cho mạch nạp chưa?",
            ]
        else:
            dong = [f"Máy tự thấy {len(self.devices)} thiết bị:"]
            dong += [d.render() for d in self.devices]
        if self.limits:
            dong.append("")
            dong.append("Điều máy KHÔNG tự biết được:")
            dong += [f"  · {t}" for t in self.limits]
        return "\n".join(dong)


#: Nơi hệ điều hành gắn ổ đĩa rời. Đây là quy ước của HỆ ĐIỀU HÀNH, không phải
#: tri thức về một họ vi điều khiển nào.
_MAU_O_DIA: tuple[str, ...] = ("/Volumes/*", "/media/*/*", "/run/media/*/*")

#: Ổ luôn có mặt nhưng không phải mạch nạp.
_O_BO_QUA = {"Macintosh HD", "Untitled", "Preboot", "Recovery", "VM", "Data"}


def probe_hardware() -> ProbeResult:
    """Bước 1: máy tự nhìn xem có gì đang cắm.

    Không hỏi người một câu nào ở bước này. Mỗi câu hỏi tiết kiệm được là một
    câu người không phải trả lời — và người dùng đánh giá một công cụ qua số
    câu nó hỏi những thứ nó lẽ ra tự biết.
    """
    from eaa.serialport import list_ports, pyserial_available

    ket_qua = ProbeResult()

    for cong in list_ports():
        ket_qua.devices.append(
            ProbedDevice(
                port=cong.device,
                vid=cong.vid,
                pid=cong.pid,
                description=cong.description,
                serial_number=cong.serial_number,
            )
        )

    if not pyserial_available():
        ket_qua.limits.append(
            "Chưa có pyserial nên KHÔNG đọc được VID/PID — chỉ thấy tên cổng. "
            "Nhận dạng bo sẽ kém chắc chắn. Khắc phục: pip install pyserial"
        )

    for o in _o_dia_roi():
        ket_qua.devices.append(ProbedDevice(volume=o, volume_label=Path(o).name))

    return ket_qua


def _o_dia_roi() -> list[str]:
    ket_qua: list[str] = []
    for mau in _MAU_O_DIA:
        for duong_dan in sorted(glob.glob(mau)):
            ten = Path(duong_dan).name
            if ten in _O_BO_QUA or not os.path.isdir(duong_dan):
                continue
            ket_qua.append(duong_dan)
    return ket_qua


# --------------------------------------------------------------------------
# Bước 2 — nhận dạng từ dấu hiệu dò được
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardCandidate:
    """Một ứng viên bo, kèm mức tin cậy và CÁCH PHÂN BIỆT."""

    name: str
    mcu: str = ""
    core: str = ""
    platform: str = ""
    clock_hz: int = 0
    flash_bytes: int = 0
    sram_bytes: int = 0
    confidence: str = "medium"
    #: Làm sao để chắc đây đúng là bo này. BẮT BUỘC khi chưa chắc.
    how_to_tell: str = ""
    note: str = ""

    def render(self) -> str:
        dong = [f"  [{self.name}] {self.mcu or '(chưa rõ MCU)'} · tin cậy {self.confidence}"]
        if self.platform:
            dong.append(f"      Platform Pack: {self.platform}")
        if self.clock_hz:
            dong.append(f"      đồng hồ mặc định: {self.clock_hz:,} Hz".replace(",", "."))
        if self.how_to_tell:
            dong.append(f"      phân biệt: {self.how_to_tell}")
        if self.note:
            dong.append(f"      {self.note}")
        return "\n".join(dong)

    @classmethod
    def from_dict(cls, d: Any) -> "BoardCandidate":
        if not isinstance(d, dict) or not d.get("name"):
            raise BriefError(f"ứng viên bo thiếu 'name': {d!r}")
        return cls(
            name=str(d["name"]),
            mcu=str(d.get("mcu", "")),
            core=str(d.get("core", "")),
            platform=str(d.get("platform", "")),
            clock_hz=int(d.get("clock_hz") or 0),
            flash_bytes=int(d.get("flash_bytes") or 0),
            sram_bytes=int(d.get("sram_bytes") or 0),
            confidence=str(d.get("confidence", "medium")),
            how_to_tell=str(d.get("how_to_tell", "")),
            note=str(d.get("note", "")),
        )


_LUOC_DO_BO = """{
  "candidates": [
    {
      "name": "<tên bo đầy đủ>",
      "mcu": "<mã vi điều khiển>",
      "core": "<lõi, ví dụ avr8 hoặc cortex-m4f>",
      "platform": "<chọn MỘT trong các Platform Pack đã cài, liệt kê bên dưới>",
      "clock_hz": <tần số đồng hồ SAU KHI RESET, chưa dựng PLL>,
      "flash_bytes": <dung lượng flash>,
      "sram_bytes": <dung lượng RAM dùng được>,
      "confidence": "high|medium|low",
      "how_to_tell": "<làm sao để chắc đúng bo này — BẮT BUỘC khi chưa chắc>",
      "note": "<điều đáng lưu ý>"
    }
  ]
}"""


def identify_board(
    probe: ProbeResult, llm: Any = None, platforms: Sequence[str] = ()
) -> list[BoardCandidate]:
    """Bước 2: từ dấu hiệu dò được, đưa ra ứng viên bo.

    KHÔNG chọn hộ. Trả về danh sách để người quyết — và mỗi ứng viên chưa chắc
    thì phải kèm cách phân biệt, vì một danh sách không có cách phân biệt thì
    người cũng chỉ chọn bừa như máy.

    ``platforms`` là danh sách Platform Pack ĐANG CÓ, truyền từ ngoài vào chứ
    không ghi cứng: engine không được biết tên một họ vi điều khiển nào. Nó còn
    giúp mô hình không đề xuất một nền tảng mà dự án chưa có pack để dùng.
    """
    dau_hieu = [d for d in probe.devices if d.identifiable]
    if not dau_hieu:
        return []
    if llm is None:
        return []

    from eaa.llm.base import LLMError, Prompt, PromptLayer

    mo_ta = "\n".join(
        f"- cổng {d.port or '(không)'}, VID:PID {d.vid or '?'}:{d.pid or '?'}, "
        f"mô tả {d.description or '(không)'}, ổ nạp {d.volume_label or '(không)'}"
        for d in dau_hieu
    )
    danh_sach = ", ".join(platforms) if platforms else "(chưa có pack nào)"
    prompt = Prompt(
        system_instruction=(
            "Bạn nhận dạng bo phát triển vi điều khiển từ dấu hiệu USB. Chỉ nêu "
            "bo CÓ THẬT. Không chắc thì nêu vài ứng viên và BẮT BUỘC kèm cách "
            "phân biệt (đọc mã in trên chip, nhãn trên bo, tệp mô tả trong ổ "
            "nạp). Không bịa dung lượng bộ nhớ; không biết thì để 0."
        ),
        layers=[
            PromptLayer(
                "task",
                f"Máy thấy các thiết bị sau:\n{mo_ta}\n\n"
                f"Platform Pack đang có: {danh_sach}\n\n"
                "Đây là bo nào? Trả về ĐÚNG một khối JSON theo lược đồ:\n\n"
                f"```json\n{_LUOC_DO_BO}\n```",
                budget=2000,
                required=True,
            )
        ],
        module="nhận dạng bo",
        budget=2800,
    )

    try:
        van_ban = (
            llm.complete(prompt) if hasattr(llm, "complete") else llm.generate(prompt).raw_response
        )
    except LLMError as exc:
        raise BriefError(f"Không nhận dạng được bo: {exc}") from exc

    from eaa.options import boc_json  # dùng chung bộ bóc JSON

    du_lieu = boc_json(van_ban, BriefError)
    return [BoardCandidate.from_dict(c) for c in (du_lieu.get("candidates") or [])]


# --------------------------------------------------------------------------
# Bước 3 — hỏi đúng phần máy không biết
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    """Một câu hỏi trong danh mục khai thác yêu cầu."""

    key: str
    topic: str
    prompt: str
    why: str
    example: str = ""
    required: bool = True

    def render(self) -> str:
        dong = [f"  [{self.key}] {self.prompt}"]
        if self.example:
            dong.append(f"      ví dụ: {self.example}")
        dong.append(f"      vì sao hỏi: {self.why}")
        return "\n".join(dong)


#: Danh mục câu hỏi. Cố ý NGẮN: mỗi câu phải là thứ không dò được và không suy
#: được, và trả lời nó phải làm thay đổi một quyết định cụ thể về sau.
QUESTIONS: tuple[Question, ...] = (
    Question(
        "muc_tieu", "Mục tiêu",
        "Thiết bị này phải làm được gì?",
        "Không có câu này thì không có tiêu chí nghiệm thu, và mọi thứ sau đều "
        "đúng quy trình mà sai mục đích.",
        "giữ thăng bằng xe hai bánh; đo nhiệt độ rồi hiện lên màn hình",
    ),
    Question(
        "doi_tuong", "Đối tượng",
        "Điều khiển hoặc đo cái gì? Cảm biến và cơ cấu chấp hành nào?",
        "Quyết định ngoại vi phải dùng, và do đó quyết định tri thức phải nạp.",
        "cảm biến gia tốc+con quay trên bus I2C, hai động cơ bước",
    ),
    Question(
        "chu_ky_ms", "Thời gian thực",
        "Chu kỳ điều khiển tối đa là bao nhiêu mili giây?",
        "Là quyết định VẬT LÝ, đến từ động lực học của đối tượng. Máy đọc được "
        "tên hàm, không đọc được rằng con lắc cần 10 ms.",
        "10",
    ),
    Question(
        "an_toan", "An toàn",
        "Mất điều khiển thì đưa thiết bị về trạng thái nào?",
        "Không có chế độ an toàn thì lỗi phần mềm thành hỏng cơ khí.",
        "cắt nguồn động cơ và giữ nguyên vị trí",
    ),
    Question(
        "nguon", "Nguồn",
        "Cấp nguồn thế nào? Nguồn động lực và nguồn điều khiển có tách không?",
        "Sụt áp khi động cơ tăng tốc là nguyên nhân reset ngẫu nhiên hay bị bỏ sót.",
        "pin 3S cho động cơ, LDO 5V cho điều khiển, có tách",
        required=False,
    ),
    Question(
        "tai_lieu", "Tài liệu",
        "Đã có datasheet, sơ đồ nguyên lý, errata chưa? Rev silicon của chip là gì?",
        "Errata là tài liệu hay bị quên nhất: mã đúng theo datasheet vẫn chạy "
        "sai nếu chip có lỗi đã công bố.",
        "có datasheet và schematic; chưa xem errata",
        required=False,
    ),
    Question(
        "uu_tien", "Ưu tiên",
        "Nếu phải chọn: chính xác hơn hay đáp ứng nhanh hơn?",
        "Định hướng mọi đánh đổi thiết kế về sau.",
        "đáp ứng nhanh, sai số 1 độ chấp nhận được",
        required=False,
    ),
)


def remaining_questions(
    answers: dict[str, Any], *, skip: Iterable[str] = ()
) -> list[Question]:
    """Câu nào còn phải hỏi — đã trả lời hoặc đã dò được thì bỏ qua."""
    da_biet = set(skip) | {k for k, v in (answers or {}).items() if str(v).strip()}
    return [q for q in QUESTIONS if q.key not in da_biet]


# --------------------------------------------------------------------------
# Bước 4 — sinh hồ sơ ở dạng đề xuất
# --------------------------------------------------------------------------


@dataclass
class ProjectDraft:
    """Bản nháp hồ sơ dự án, kèm xuất xứ từng dữ kiện."""

    project_dir: Path
    board: BoardCandidate | None = None
    answers: dict[str, Any] = field(default_factory=dict)
    probe: ProbeResult | None = None
    assumptions: list[dict[str, Any]] = field(default_factory=list)

    def gia_dinh(self, ma: str, phat_bieu: str, cach_kiem: str, chan: Sequence[str] = ()) -> None:
        self.assumptions.append(
            {
                "id": ma,
                "statement": phat_bieu,
                "status": "proposed",
                "how_to_verify": cach_kiem,
                "blocks": list(chan),
            }
        )

    # -- constraints.yaml --------------------------------------------------

    def constraints(self) -> str:
        if self.board is None:
            raise BriefError("Chưa chọn bo — không dựng được ràng buộc.")

        chu_ky = self.answers.get("chu_ky_ms")
        limits: dict[str, Any] = {}
        if chu_ky:
            limits["control_loop_ms"] = int(chu_ky)
        limits["max_module_lines"] = 300

        du_lieu = {
            "version": 1,
            "changelog": [
                {
                    "version": 1,
                    "date": _now()[:10],
                    "author": "eaa brief",
                    "note": "Bản NHÁP do Agent dựng — phải duyệt tại G1 trước khi dùng.",
                }
            ],
            "platform": self.board.platform,
            "mcu": self.board.mcu,
            "clock_hz": self.board.clock_hz or 0,
            "limits": limits,
            "forbidden": ["delay()", "malloc/new", "float_in_isr", "blocking_io"],
            "style": {
                "arithmetic": "integer",
                "io": "direct_port",
                "naming": "snake_case",
            },
            "acceptance": {"scenarios": [], "measurements": []},
        }
        return _BAN_NHAP_RANG_BUOC + yaml.safe_dump(
            du_lieu, allow_unicode=True, sort_keys=False
        )

    # -- hardware_profile.yaml --------------------------------------------

    def hardware_profile(self) -> str:
        if self.board is None:
            raise BriefError("Chưa chọn bo — không dựng được hồ sơ phần cứng.")

        thiet_bi = [d for d in (self.probe.devices if self.probe else []) if d.identifiable]
        usb = [
            {"vid": d.vid, "pid": d.pid, "note": d.description or "dò được trên máy này"}
            for d in thiet_bi
            if d.vid
        ]
        o_nap = next((d.volume for d in thiet_bi if d.volume), "")

        programmer: dict[str, Any] = {}
        if usb:
            programmer["usb"] = usb
        cong = next((d.port for d in thiet_bi if d.port), "")
        if cong:
            # Gợi ý tên cổng lấy từ CHÍNH cổng dò được, không đoán.
            programmer["port_hint"] = _goi_y_ten_cong(cong)
        if o_nap:
            programmer["mass_storage"] = o_nap

        du_lieu: dict[str, Any] = {
            "version": 1,
            "project": self.project_dir.name,
            "description": f"{self.board.name} — hồ sơ NHÁP do Agent dựng.",
            "mcu": {
                k: v
                for k, v in {
                    "part": self.board.mcu,
                    "core": self.board.core,
                    "clock_hz": self.board.clock_hz or None,
                    "flash_bytes": self.board.flash_bytes or None,
                    "sram_bytes": self.board.sram_bytes or None,
                }.items()
                if v
            },
        }
        if programmer:
            du_lieu["programmer"] = programmer
        du_lieu["peripherals"] = []
        du_lieu["pin_map"] = {}
        if self.assumptions:
            du_lieu["assumptions"] = self.assumptions

        return _BAN_NHAP_PHAN_CUNG + yaml.safe_dump(
            du_lieu, allow_unicode=True, sort_keys=False
        )

    # -- ghi ra ------------------------------------------------------------

    def write(self) -> list[Path]:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        da_ghi: list[Path] = []
        for ten, noi_dung in (
            ("constraints.yaml", self.constraints()),
            ("hardware_profile.yaml", self.hardware_profile()),
        ):
            duong_dan = self.project_dir / ten
            if duong_dan.is_file():
                raise BriefError(
                    f"{duong_dan} đã có. Agent KHÔNG ghi đè hồ sơ dự án: bản cũ "
                    "có thể đã qua G1 và đang được mã sinh ra dựa vào.\n"
                    "    Xem lại rồi tự xóa nếu thật sự muốn dựng lại."
                )
            duong_dan.write_text(noi_dung, encoding="utf-8")
            da_ghi.append(duong_dan)
        return da_ghi


def _goi_y_ten_cong(port: str) -> str:
    """Rút phần ổn định của tên cổng để làm gợi ý khớp.

    ``/dev/cu.usbserial-143420`` → ``usbserial``. Lấy phần trước dấu gạch/số vì
    phần đuôi đổi theo lần cắm, còn phần đầu là tên trình điều khiển.
    """
    ten = Path(port).name
    for tach in (".", "-"):
        if tach in ten:
            ten = ten.split(tach)[1] if tach == "." and ten.count(".") else ten.split(tach)[0]
    return "".join(c for c in ten if not c.isdigit()) or ten


_BAN_NHAP_RANG_BUOC = """\
# Hard Constraints Spec — BẢN NHÁP do `eaa brief` dựng.
#
# ĐÂY LÀ ĐỀ XUẤT, CHƯA PHẢI QUYẾT ĐỊNH. Đọc kỹ từng dòng rồi duyệt tại G1;
# tệp này được nạp vào 100% lần gọi mô hình, nên một dòng sai ở đây đi theo
# toàn bộ mã sinh ra về sau.
#
# Chỗ còn trống (acceptance, peripherals) là chỗ Agent KHÔNG đoán:
# tiêu chí nghiệm thu phải đo được và phải do người chốt trước khi có số đo.

"""

_BAN_NHAP_PHAN_CUNG = """\
# Hardware Profile — BẢN NHÁP do `eaa brief` dựng.
#
# Phân biệt ba loại dữ kiện, và đừng trộn chúng khi sửa tệp này:
#   · mục `programmer` — ĐÃ KIỂM trên máy này bằng cách dò cổng USB
#   · mục `mcu`        — TRA CỨU, cần đối chiếu datasheet trước khi tin
#   · mục `assumptions`— CHƯA KIỂM, kèm cách kiểm từng mục
#
# Sáu tháng sau không ai nhớ con số nào đo được, con số nào đoán ra — nên thứ
# chưa kiểm phải nằm ở `assumptions`, không nằm lẫn như sự thật.

"""
