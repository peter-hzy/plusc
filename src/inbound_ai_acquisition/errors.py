"""项目内可预期错误。"""


class AcquisitionError(Exception):
    """可向 CLI 用户直接说明的业务错误。"""


class ValidationError(AcquisitionError):
    """输入不符合合同。"""


class StateError(AcquisitionError):
    """状态迁移或业务门禁不允许当前操作。"""


class IdempotencyConflict(AcquisitionError):
    """同一幂等键被用于不同输入。"""
