"""Embedded AIDD Agent — ENGINE.

Tầng ENGINE của kiến trúc 3 tầng (ADR-09): điều phối, gate, composer, tools,
doctor. Tuyệt đối không chứa hằng số phần cứng nào — mọi đặc thù họ vi điều
khiển nằm trong ``packs/``, mọi đặc thù dự án nằm trong ``projects/``.
Bất biến này được kiểm chứng tự động bởi TC-38 trong CI mỗi commit.
"""

__version__ = "0.1.0"

# Mã thoát CLI — EAA-SDD-03 §6. Dùng để script hóa thực nghiệm A/B.
EXIT_OK = 0
EXIT_WAITING_GATE = 2
EXIT_REPAIR_LIMIT = 3
EXIT_ENV_ERROR = 4
