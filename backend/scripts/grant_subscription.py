"""특정 계정에 Plus/Pro 구독 권한을 수동 부여하는 관리용 일회성 스크립트.

결제 웹훅을 타지 않고, 운영자가 직접 특정 사용자에게 유료 등급을 부여(또는 회수)할 때 사용한다.
권한 판정은 subscriptions 테이블의 최신 행으로 이뤄지므로(app/services/subscription_service.py),
이 스크립트는 provider="manual" 인 구독 행을 생성하거나 갱신한다.

실행 (backend 디렉터리에서):
    python -m scripts.grant_subscription --email user@example.com --tier PRO
    python -m scripts.grant_subscription --email user@example.com --tier PLUS --days 30
    python -m scripts.grant_subscription --email user@example.com --revoke

옵션:
    --email      대상 사용자 이메일 (필수)
    --tier       PLUS 또는 PRO (부여 시 필수)
    --days       유효 기간(일). 생략하면 만료 없음(평생 부여).
    --revoke     해당 사용자의 manual 구독을 만료 처리(권한 회수).
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Subscription, User
from app.schemas import SubscriptionStatus, SubscriptionTier

MANUAL_PROVIDER = "manual"


def _provider_subscription_id(user_id: int) -> str:
    """manual provider 내에서 사용자당 1개의 구독 행을 유지하기 위한 고유 식별자."""
    return f"manual_{user_id}"


async def _find_user(db, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _find_manual_subscription(db, user_id: int) -> Subscription | None:
    result = await db.execute(
        select(Subscription)
        .where(Subscription.provider == MANUAL_PROVIDER)
        .where(Subscription.provider_subscription_id == _provider_subscription_id(user_id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def grant(email: str, tier: SubscriptionTier, days: int | None) -> None:
    now = datetime.utcnow()
    period_end = now + timedelta(days=days) if days else None

    async with AsyncSessionLocal() as db:
        user = await _find_user(db, email)
        if user is None:
            raise SystemExit(f"[실패] 이메일에 해당하는 사용자를 찾을 수 없습니다: {email}")

        subscription = await _find_manual_subscription(db, user.id)
        if subscription is None:
            subscription = Subscription(
                user_id=user.id,
                provider=MANUAL_PROVIDER,
                provider_subscription_id=_provider_subscription_id(user.id),
                created_at=now,
            )
            db.add(subscription)

        subscription.tier = tier.value
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.provider_plan_id = f"manual_{tier.value.lower()}"
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.cancel_at_period_end = False
        subscription.canceled_at = None
        subscription.ended_at = None
        subscription.updated_at = now

        await db.commit()

    expiry = period_end.isoformat() if period_end else "만료 없음"
    print(f"[성공] {email} (user_id={user.id}) → {tier.value} 부여 완료 (만료: {expiry})")


async def revoke(email: str) -> None:
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        user = await _find_user(db, email)
        if user is None:
            raise SystemExit(f"[실패] 이메일에 해당하는 사용자를 찾을 수 없습니다: {email}")

        subscription = await _find_manual_subscription(db, user.id)
        if subscription is None:
            print(f"[건너뜀] {email} 에 manual 구독이 없습니다. 변경할 내용이 없습니다.")
            return

        subscription.status = SubscriptionStatus.EXPIRED.value
        subscription.cancel_at_period_end = False
        subscription.ended_at = now
        subscription.updated_at = now
        await db.commit()

    print(f"[성공] {email} (user_id={user.id}) 의 manual 구독을 회수(EXPIRED)했습니다.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="특정 계정에 Plus/Pro 구독을 수동 부여/회수")
    parser.add_argument("--email", required=True, help="대상 사용자 이메일")
    parser.add_argument("--tier", choices=["PLUS", "PRO"], help="부여할 등급")
    parser.add_argument("--days", type=int, default=None, help="유효 기간(일). 생략 시 만료 없음")
    parser.add_argument("--revoke", action="store_true", help="manual 구독을 회수(만료 처리)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.revoke:
        asyncio.run(revoke(args.email))
        return
    if not args.tier:
        raise SystemExit("[실패] 부여하려면 --tier PLUS|PRO 가 필요합니다 (또는 --revoke 사용).")
    asyncio.run(grant(args.email, SubscriptionTier(args.tier), args.days))


if __name__ == "__main__":
    main()
