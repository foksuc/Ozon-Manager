from .models import OperationStatus

_ALLOWED = {
    OperationStatus.DRAFT: {OperationStatus.PREVIEWED, OperationStatus.CANCELLED},
    OperationStatus.PREVIEWED: {OperationStatus.FRESH_CHECKED, OperationStatus.DRAFT, OperationStatus.CANCELLED},
    OperationStatus.FRESH_CHECKED: {OperationStatus.SNAPSHOTTED, OperationStatus.DRAFT, OperationStatus.CANCELLED},
    OperationStatus.SNAPSHOTTED: {OperationStatus.CONFIRMED, OperationStatus.CANCELLED},
    OperationStatus.CONFIRMED: {OperationStatus.RUNNING, OperationStatus.CANCELLED},
    OperationStatus.RUNNING: {
        OperationStatus.SUCCESS,
        OperationStatus.PARTIAL,
        OperationStatus.FAILED,
        OperationStatus.VERIFICATION_FAILED,
    },
    OperationStatus.PARTIAL: set(),
    OperationStatus.SUCCESS: set(),
    OperationStatus.FAILED: set(),
    OperationStatus.VERIFICATION_FAILED: {OperationStatus.SUCCESS, OperationStatus.PARTIAL, OperationStatus.FAILED, OperationStatus.VERIFICATION_FAILED},
    OperationStatus.CANCELLED: set(),
}


def transition(current: OperationStatus, target: OperationStatus) -> OperationStatus:
    if target not in _ALLOWED[current]:
        raise ValueError(f"Invalid operation transition: {current.value} -> {target.value}")
    return target
