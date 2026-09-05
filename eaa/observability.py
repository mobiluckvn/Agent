"""Làm cho lỗi KÊU LÊN ĐƯỢC — N-912.

Xem `docs/SAI_LECH_THIET_KE.md` mục SL-175.

Ca thật
-------

Ba lượt nạp đầu tiên, robot chỉ **im** hoặc **ngã**. Hai trạng thái ấy không
phân biệt được với chip chết, với nguồn tụt, hay với mã chạy sai — và cũng
không phân biệt được với nhau. Mỗi lần gỡ phải bắt đầu bằng câu hỏi *"nó có
chạy không"*, thứ lẽ ra mạch tự trả lời được.

Mọi đường báo hiệu về sau — nhịp bíp khởi động, nút thoát, cảnh báo mất mẫu —
đều do **người** nghĩ ra và thêm vào. Không bản phân rã nào tự đề nghị lấy một
cái.

Bộ này hỏi cái gì
-----------------

Đúng hai câu, cho mỗi module:

* **dấu hiệu sống** — người nhận ra module này đang chạy bằng cách nào, không
  cần máy đo?
* **dấu hiệu hỏng** — khi nó hỏng, người nhận ra bằng cách nào?

Thiếu câu trả lời không phải là lỗi mã; nó là một khoảng trống trong THIẾT KẾ,
và chỗ rẻ nhất để lấp là lúc phân rã, không phải lúc đứng trước một con robot
im lìm.

Ranh giới engine — và nó chặt ở đây
------------------------------------

Engine **không biết** thứ gì trên đời phát ra tiếng, thứ gì sáng lên, thứ gì
người nghe được. Nó chỉ đọc một cờ ``observable`` mà hồ sơ phần cứng của dự án
gắn cho linh kiện, và coi giá trị của cờ ấy là **chuỗi mờ** — đúng cách nó đối
xử với ``uses`` (EAA-SDD-03 §3.2). Dự án nói cái gì quan sát được; engine chỉ
biết đếm xem có cái nào không.

Nếu engine biết "còi thì kêu" thì nó đã thành công cụ cho đúng một cái bo, và
TC-38 quét đúng chuyện ấy ở mỗi commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

__all__ = [
    "Kenh",
    "ThieuDauHieu",
    "BaoCaoQuanSat",
    "kenh_quan_sat",
    "soi_quan_sat",
]

#: Tên trường mà hồ sơ phần cứng dùng để đánh dấu một linh kiện là quan sát
#: được. Engine không diễn giải GIÁ TRỊ của nó.
TRUONG_QUAN_SAT = "observable"


@dataclass(frozen=True)
class Kenh:
    """Một đường mà người nhận biết được, do hồ sơ dự án khai."""

    id: str
    cach: str

    def __str__(self) -> str:
        return f"{self.id} ({self.cach})" if self.cach else self.id


@dataclass(frozen=True)
class ThieuDauHieu:
    """Một module chưa khai được người nhận ra nó bằng cách nào."""

    module_id: str
    thieu: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.module_id}: thiếu {', '.join(self.thieu)}"


@dataclass(frozen=True)
class BaoCaoQuanSat:
    """Kết quả soi khả quan sát của cả bản phân rã."""

    kenh: tuple[Kenh, ...] = ()
    thieu: tuple[ThieuDauHieu, ...] = ()
    so_module: int = 0

    @property
    def khong_co_kenh_nao(self) -> bool:
        """Bo không có đường nào người nhận biết được.

        Đây là phát hiện to hơn hẳn mọi phát hiện khác trong báo cáo: thiếu
        dấu hiệu ở một module thì còn sửa được bằng cách khai thêm; không có
        kênh nào thì **không module nào khai được gì**, và mọi lần gỡ lỗi về
        sau đều bắt đầu từ con số không.
        """
        return not self.kenh

    @property
    def dat(self) -> bool:
        return not self.khong_co_kenh_nao and not self.thieu

    def render(self) -> str:
        dong: list[str] = []
        if self.khong_co_kenh_nao:
            dong += [
                "KHÔNG CÓ KÊNH QUAN SÁT NÀO trong hồ sơ phần cứng.",
                "",
                "  Nghĩa là khi mạch hỏng, nó không có cách nào nói ra. Mọi lần gỡ",
                "  lỗi sẽ bắt đầu bằng câu 'nó có chạy không' — thứ lẽ ra mạch tự",
                "  trả lời được.",
                "",
                f"  Đánh dấu linh kiện nào người nhận biết được bằng trường",
                f"  '{TRUONG_QUAN_SAT}: <người nhận ra bằng cách nào>' trong",
                "  hardware_profile.yaml, rồi duyệt lại G1.",
                "",
            ]
        else:
            dong.append(
                f"Kênh quan sát được ({len(self.kenh)}): "
                + ", ".join(str(k) for k in self.kenh)
            )
            dong.append("")

        if not self.thieu:
            dong.append(
                f"Cả {self.so_module} module đều khai được dấu hiệu sống và dấu hiệu hỏng."
            )
            return "\n".join(dong)

        dong.append(f"{len(self.thieu)}/{self.so_module} module chưa khai:")
        dong += [f"  • {t}" for t in self.thieu]
        dong += [
            "",
            "Hai câu phải trả lời cho mỗi module, và cả hai là câu của người:",
            "  1. Người nhận ra module này ĐANG CHẠY bằng cách nào, không cần máy đo?",
            "  2. Khi nó HỎNG, người nhận ra bằng cách nào?",
            "",
            "Trả lời được thì khai vào bản phân rã. Chỗ rẻ nhất để lấp khoảng",
            "trống này là lúc phân rã, không phải lúc đứng trước một mạch im lìm.",
        ]
        return "\n".join(dong)


def kenh_quan_sat(hardware: Any) -> list[Kenh]:
    """Linh kiện được hồ sơ đánh dấu là người nhận biết được.

    Đọc cả ``components`` lẫn ``peripherals``: một dự án có thể khai đường báo
    hiệu ở chỗ nào cũng được, và engine không có lý do gì bắt nó chọn một chỗ.
    """
    if hardware is None:
        return []
    ra: list[Kenh] = []
    for ten in ("components", "peripherals"):
        try:
            muc = getattr(hardware, ten)
        except Exception:  # noqa: BLE001 - hồ sơ hỏng không làm hỏng phép soi
            continue
        for m in muc or []:
            if not isinstance(m, dict):
                continue
            cach = m.get(TRUONG_QUAN_SAT)
            if not cach:
                continue
            ra.append(Kenh(id=str(m.get("id") or m.get("part") or "?"), cach=str(cach)))
    return sorted(ra, key=lambda k: k.id)


def soi_quan_sat(modules: Iterable[Any], hardware: Any = None) -> BaoCaoQuanSat:
    """Module nào chưa nói được nó sống hay chết.

    Chỉ soi module còn ĐANG LÀM. Module đã bỏ hoặc chưa tới lượt thì hỏi câu
    này là hỏi sớm, và một báo cáo dài vì những dòng chưa tới lượt là một báo
    cáo không ai đọc hết.
    """
    danh_sach = [m for m in modules if getattr(m, "status", "") != "dropped"]
    thieu: list[ThieuDauHieu] = []
    for m in danh_sach:
        con: list[str] = []
        if not str(getattr(m, "dau_hieu_song", "") or "").strip():
            con.append("dấu hiệu sống")
        if not str(getattr(m, "dau_hieu_hong", "") or "").strip():
            con.append("dấu hiệu hỏng")
        if con:
            thieu.append(ThieuDauHieu(module_id=str(m.id), thieu=tuple(con)))
    return BaoCaoQuanSat(
        kenh=tuple(kenh_quan_sat(hardware)),
        thieu=tuple(thieu),
        so_module=len(danh_sach),
    )
