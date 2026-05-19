"""Create the six Space Goose Stripe prices (starter/pro/max × monthly/yearly).

Idempotent-ish: each product is keyed by ``lookup_key`` so re-running the
script reuses existing products. Stripe prices themselves are immutable,
so this script will only create new price rows on the first successful
run; subsequent runs print the existing IDs it finds via search.

Usage:
    STRIPE_SECRET_KEY=sk_test_... python backend/scripts/seed_stripe_prices.py
    STRIPE_SECRET_KEY=sk_live_... python backend/scripts/seed_stripe_prices.py --live

Output is a copy-pasteable block of env vars for Render / .env.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import stripe


@dataclass(frozen=True)
class TierSpec:
    tier: str
    product_name: str
    description: str
    monthly_cents: int
    yearly_cents: int  # full annual total, 20% off monthly * 12


TIERS: list[TierSpec] = [
    TierSpec(
        tier="starter",
        product_name="Space Goose Starter",
        description="For solo brokers kicking the tires",
        monthly_cents=2_000,
        yearly_cents=19_200,
    ),
    TierSpec(
        tier="pro",
        product_name="Space Goose Pro",
        description="For active CRE pros who chat all day",
        monthly_cents=10_000,
        yearly_cents=96_000,
    ),
    TierSpec(
        tier="max",
        product_name="Space Goose Max",
        description="For high-volume teams who live in chat",
        monthly_cents=20_000,
        yearly_cents=192_000,
    ),
]


def _find_or_create_product(spec: TierSpec) -> stripe.Product:
    lookup = f"spacegoose_{spec.tier}"
    existing = stripe.Product.search(query=f'metadata["lookup"]:"{lookup}"').data
    if existing:
        print(f"  product reused: {existing[0].id}")
        return existing[0]
    product = stripe.Product.create(
        name=spec.product_name,
        description=spec.description,
        metadata={"lookup": lookup, "tier": spec.tier},
    )
    print(f"  product created: {product.id}")
    return product


def _find_or_create_price(
    product_id: str, tier: str, interval: str, amount_cents: int
) -> stripe.Price:
    lookup_key = f"spacegoose_{tier}_{interval}"
    existing = stripe.Price.list(
        lookup_keys=[lookup_key], active=True, limit=1
    ).data
    if existing:
        price = existing[0]
        if price.unit_amount != amount_cents:
            print(
                f"  WARN: existing price {price.id} amount {price.unit_amount} "
                f"!= desired {amount_cents}. Stripe prices are immutable; "
                f"archive the old one in dashboard and re-run.",
                file=sys.stderr,
            )
        print(f"  price reused ({interval}): {price.id}")
        return price
    price = stripe.Price.create(
        product=product_id,
        unit_amount=amount_cents,
        currency="usd",
        recurring={
            "interval": "month" if interval == "monthly" else "year",
        },
        lookup_key=lookup_key,
        metadata={"tier": tier, "interval": interval},
    )
    print(f"  price created ({interval}): {price.id}")
    return price


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Confirm you intend to write to a LIVE Stripe account",
    )
    args = parser.parse_args()

    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        print(
            "ERROR: STRIPE_SECRET_KEY env var required.",
            file=sys.stderr,
        )
        return 1
    is_live = api_key.startswith("sk_live_")
    if is_live and not args.live:
        print(
            "Refusing to run against a LIVE key without --live. Re-run with "
            "STRIPE_SECRET_KEY=sk_live_... and --live to confirm.",
            file=sys.stderr,
        )
        return 1
    if not is_live and args.live:
        print(
            "--live passed but STRIPE_SECRET_KEY isn't a live key. Aborting.",
            file=sys.stderr,
        )
        return 1

    stripe.api_key = api_key
    mode = "LIVE" if is_live else "TEST"
    print(f"Seeding Space Goose prices into {mode} Stripe account...\n")

    env_lines: list[str] = []
    for spec in TIERS:
        print(f"[{spec.tier}]")
        product = _find_or_create_product(spec)
        monthly = _find_or_create_price(
            product.id, spec.tier, "monthly", spec.monthly_cents
        )
        yearly = _find_or_create_price(
            product.id, spec.tier, "yearly", spec.yearly_cents
        )
        env_lines.append(
            f"STRIPE_{spec.tier.upper()}_MONTHLY_PRICE_ID={monthly.id}"
        )
        env_lines.append(
            f"STRIPE_{spec.tier.upper()}_YEARLY_PRICE_ID={yearly.id}"
        )
        print()

    print("=" * 60)
    print("Paste into backend/.env (local) or Render env vars (prod):")
    print("=" * 60)
    for line in env_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
