from __future__ import annotations

from decimal import Decimal

from app.domain.models import OperationStatus, ProductState, OperationItem, utc_now
from app.domain.state_machine import transition
from app.services.workflow import OperationFactory
from app.services.membership import candidate_to_product
from app.services.price_engine import calculate_candidate_elastic_price


class SafeRollbackService:
    """Rollback is a new action_price mutation derived only from an immutable snapshot."""

    def __init__(self, repository, participant_service, preview_service, fresh_check_service, snapshot_service, mutation_service, verification_service, promotion_service):
        self.repository = repository
        self.participant_service = participant_service
        self.promotion_service = promotion_service
        self.preview_service = preview_service
        self.fresh_check_service = fresh_check_service
        self.snapshot_service = snapshot_service
        self.mutation_service = mutation_service
        self.verification_service = verification_service

    def prepare(self, snapshot_id: str, user: str):
        rows = self.repository.get_snapshot(snapshot_id)
        if not rows:
            raise ValueError("Snapshot not found")
        source_operation = self.repository.get_operation(str(rows[0]["operation_id"]))
        if source_operation is None:
            raise ValueError("Source operation not found")
        action_id = str(rows[0]["action_id"])
        source_type = str(source_operation["operation_type"])

        # ADD rollback is a membership reversal: the product must currently be
        # a participant and rollback must DEACTIVATE it.  A candidate snapshot
        # has no meaningful old action_price (historically serialized as 0), so
        # it must never be sent back through ActivateProduct with zero price.
        if source_type == "ADD_PRODUCTS":
            current = self.participant_service.current_state(action_id, {str(r["product_id"]) for r in rows})
            missing = [str(r["product_id"]) for r in rows if str(r["product_id"]) not in current]
            if missing:
                raise ValueError(f"ADD rollback Fresh Check failed: товары уже отсутствуют в акции: {missing}")
            op = OperationFactory.create(action_id, user, created_by="rollback", operation_type="ROLLBACK_ADD_REMOVE")
            op.source_snapshot_id = snapshot_id
            op.items = [OperationItem(
                operation_id=op.operation_id,
                product_id=p.product_id,
                old_action_price=p.action_price,
                requested_action_price=p.action_price,
                old_current_boost=p.current_boost,
            ) for p in current.values()]
            op.request_fingerprint = OperationFactory.fingerprint(
                op.action_id,
                [(i.product_id, i.requested_action_price) for i in op.items],
                op.operation_type,
            )
            op.status = transition(op.status, OperationStatus.PREVIEWED)
            # This is a read-only Fresh Check. The actual REMOVE service repeats
            # its own mandatory pre-mutation Fresh Check immediately before the mutation.
            op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
            self.repository.save_operation(op)
            return op

        # REMOVE rollback is the inverse: the product must now be absent from
        # participants and present in candidates, then ADD it back at the exact
        # action_price recorded in the source snapshot.
        if source_type == "REMOVE_PRODUCTS":
            product_ids = {str(r["product_id"]) for r in rows}
            current = self.participant_service.current_state(action_id, product_ids)
            still_present = sorted(current)
            if still_present:
                raise ValueError(f"REMOVE rollback Fresh Check failed: товары всё ещё участвуют в акции: {still_present}")
            candidates = {str(r.get("id", r.get("product_id"))): r for r in self.participant_service.adapter.list_all_candidates(action_id)}
            missing = sorted(product_ids - set(candidates))
            if missing:
                raise ValueError(f"REMOVE rollback Fresh Check failed: товары недоступны среди кандидатов: {missing}")

            op = OperationFactory.create(action_id, user, created_by="rollback", operation_type="ROLLBACK_REMOVE_ADD")
            op.source_snapshot_id = snapshot_id
            products = []
            requested = {}
            for r in rows:
                pid = str(r["product_id"])
                product = candidate_to_product(action_id, candidates[pid])
                target_price = Decimal(str(r["action_price"]))
                if target_price <= 0:
                    raise ValueError(f"REMOVE rollback заблокирован: snapshot action_price для SKU {pid} неположительный")
                try:
                    # Validate the snapshot price against the current candidate
                    # thresholds without changing it. This is only a safety gate.
                    discount = (product.price - target_price) / product.price * Decimal("100")
                    calculate_candidate_elastic_price(
                        product.price, discount,
                        product.price_min_elastic, product.price_max_elastic,
                    )
                except Exception as exc:
                    raise ValueError(f"REMOVE rollback Fresh Check failed for SKU {pid}: {exc}") from exc
                products.append(product)
                requested[pid] = target_price
            op.items = [OperationItem(
                operation_id=op.operation_id,
                product_id=p.product_id,
                old_action_price=Decimal("0"),
                requested_action_price=requested[p.product_id],
                old_current_boost=None,
            ) for p in products]
            op.request_fingerprint = OperationFactory.fingerprint(
                op.action_id,
                [(i.product_id, i.requested_action_price) for i in op.items],
                op.operation_type,
            )
            op.status = transition(op.status, OperationStatus.PREVIEWED)
            op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
            self.repository.save_operation(op)
            return op

        # Standard UPDATE_PRICE rollback: participant must still exist and the
        # snapshot action_price is a valid positive target.
        promotion = self.promotion_service.get_promotion(action_id)
        current = self.participant_service.current_state(action_id, {str(r["product_id"]) for r in rows})
        targets = []
        for r in rows:
            p = current.get(str(r["product_id"]))
            if p is None:
                raise ValueError(f"SKU {r['product_id']} is unavailable for rollback Fresh Check")
            target_price = Decimal(str(r["action_price"]))
            if target_price <= 0:
                raise ValueError(f"Rollback заблокирован: snapshot action_price для SKU {r['product_id']} неположительный")
            targets.append(p)
        op = OperationFactory.create(action_id, user, created_by="rollback")
        op.source_snapshot_id = snapshot_id
        requested = {str(r["product_id"]): Decimal(r["action_price"]) for r in rows}
        op.items = [OperationItem(
            operation_id=op.operation_id,
            product_id=p.product_id,
            old_action_price=p.action_price,
            requested_action_price=requested[p.product_id],
            old_current_boost=p.current_boost,
        ) for p in targets]
        op.request_fingerprint = OperationFactory.fingerprint(op.action_id, [(i.product_id, i.requested_action_price) for i in op.items])
        op.status = transition(op.status, OperationStatus.PREVIEWED)
        fresh_errors = self.fresh_check_service.check(op, current, promotion)
        if fresh_errors:
            raise ValueError("Rollback Fresh Check failed: " + "; ".join(fresh_errors))
        op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
        self.snapshot_service.create(op, current)
        return op

    def execute_membership_inverse(self, operation):
        """Execute ADD/REMOVE rollback through the proven membership service."""
        from app.services.membership import AddProductsService, RemoveProductsService

        if operation.operation_type == "ROLLBACK_ADD_REMOVE":
            selected = [item.product_id for item in operation.items]
            RemoveProductsService(self.mutation_service.adapter, self.repository).execute(
                operation.action_id, selected, "streamlit-session", confirmed=True
            )
        elif operation.operation_type == "ROLLBACK_REMOVE_ADD":
            prices = {item.product_id: item.requested_action_price for item in operation.items}
            candidates = {str(r.get("id", r.get("product_id"))): r for r in self.mutation_service.adapter.list_all_candidates(operation.action_id)}
            AddProductsService(self.mutation_service.adapter, self.repository).execute(
                operation.action_id, [item.product_id for item in operation.items], prices, candidates,
                "streamlit-session", confirmed=True
            )
        else:
            raise ValueError("Membership inverse rollback is not applicable to this operation")
        operation.status = OperationStatus.SUCCESS
        operation.completed_at = utc_now()
        self.repository.save_operation(operation)

