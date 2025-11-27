"""
Stripe Payment Integration for Premier Voice Assistant
Handles subscription payments and webhooks.
"""
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Stripe price IDs (set these in .env - get from Stripe Dashboard > Products > Pricing)
STRIPE_PRICE_IDS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}


def validate_stripe_config():
    """Check if Stripe is properly configured."""
    issues = []
    if not os.getenv("STRIPE_SECRET_KEY"):
        issues.append("STRIPE_SECRET_KEY not set")
    if not os.getenv("STRIPE_WEBHOOK_SECRET"):
        issues.append("STRIPE_WEBHOOK_SECRET not set")
    if not STRIPE_PRICE_IDS.get("starter"):
        issues.append("STRIPE_PRICE_STARTER not set")
    if not STRIPE_PRICE_IDS.get("pro"):
        issues.append("STRIPE_PRICE_PRO not set")
    return issues


class StripePayments:
    """
    Stripe payment handler for subscription management.
    """

    def __init__(self):
        import stripe
        self.stripe = stripe
        self.stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

        if not self.stripe.api_key:
            logger.warning("STRIPE_SECRET_KEY not set - payments disabled")

    def create_customer(self, user_id: str, email: str, name: str = None) -> Optional[str]:
        """
        Create a Stripe customer for a user.

        Args:
            user_id: Internal user ID
            email: Customer email
            name: Customer name

        Returns:
            Stripe customer ID or None
        """
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id}
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            return None

    def create_checkout_session(
        self,
        user_id: str,
        customer_id: str,
        plan_name: str,
        success_url: str,
        cancel_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            user_id: Internal user ID
            customer_id: Stripe customer ID
            plan_name: Plan to subscribe to
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel

        Returns:
            Session data with URL or None
        """
        try:
            price_id = STRIPE_PRICE_IDS.get(plan_name)
            if not price_id:
                logger.error(f"No price ID for plan: {plan_name}")
                return None

            session = self.stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": user_id,
                    "plan_name": plan_name
                }
            )

            logger.info(f"Created checkout session {session.id} for {plan_name}")
            return {
                "session_id": session.id,
                "url": session.url
            }

        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return None

    def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> Optional[str]:
        """
        Create a Stripe Customer Portal session for managing subscription.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal

        Returns:
            Portal URL or None
        """
        try:
            session = self.stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return session.url
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            return None

    def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription details from Stripe.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription data or None
        """
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": datetime.fromtimestamp(subscription.current_period_start),
                "current_period_end": datetime.fromtimestamp(subscription.current_period_end),
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "plan_id": subscription.items.data[0].price.id if subscription.items.data else None
            }
        except Exception as e:
            logger.error(f"Error getting subscription: {e}")
            return None

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of period; if False, cancel immediately

        Returns:
            Success status
        """
        try:
            if at_period_end:
                self.stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                self.stripe.Subscription.delete(subscription_id)

            logger.info(f"Cancelled subscription {subscription_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            return False


def handle_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Handle Stripe webhook events.

    Args:
        payload: Raw request body
        sig_header: Stripe signature header

    Returns:
        Event handling result
    """
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return {"error": "Invalid signature"}

    # Handle specific events
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        # Payment successful, activate subscription
        user_id = data["metadata"].get("user_id")
        plan_name = data["metadata"].get("plan_name")
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        logger.info(f"Checkout completed: user={user_id}, plan={plan_name}")

        return {
            "event": "checkout_completed",
            "user_id": user_id,
            "plan_name": plan_name,
            "subscription_id": subscription_id,
            "customer_id": customer_id
        }

    elif event_type == "customer.subscription.updated":
        # Subscription updated (upgraded, downgraded, etc.)
        subscription_id = data["id"]
        status = data["status"]
        customer_id = data["customer"]

        logger.info(f"Subscription updated: {subscription_id}, status={status}")

        return {
            "event": "subscription_updated",
            "subscription_id": subscription_id,
            "status": status,
            "customer_id": customer_id
        }

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        subscription_id = data["id"]
        customer_id = data["customer"]

        logger.info(f"Subscription cancelled: {subscription_id}")

        return {
            "event": "subscription_cancelled",
            "subscription_id": subscription_id,
            "customer_id": customer_id
        }

    elif event_type == "invoice.payment_succeeded":
        # Payment successful - update billing period
        subscription_id = data.get("subscription")
        customer_id = data["customer"]
        period_start = datetime.fromtimestamp(data["period_start"])
        period_end = datetime.fromtimestamp(data["period_end"])

        logger.info(f"Payment succeeded for subscription {subscription_id}")

        return {
            "event": "payment_succeeded",
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat()
        }

    elif event_type == "invoice.payment_failed":
        # Payment failed
        subscription_id = data.get("subscription")
        customer_id = data["customer"]

        logger.warning(f"Payment failed for subscription {subscription_id}")

        return {
            "event": "payment_failed",
            "subscription_id": subscription_id,
            "customer_id": customer_id
        }

    else:
        logger.debug(f"Unhandled webhook event: {event_type}")
        return {"event": event_type, "handled": False}


# Singleton instance
_stripe_payments: Optional[StripePayments] = None


def get_stripe_payments() -> StripePayments:
    """Get or create StripePayments singleton."""
    global _stripe_payments
    if _stripe_payments is None:
        _stripe_payments = StripePayments()
    return _stripe_payments
