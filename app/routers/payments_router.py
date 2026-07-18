from fastapi import APIRouter, HTTPException, Depends, status, Request
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
import stripe
import os

router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class CheckoutRequest(BaseModel):
    plan_type: str  # "monthly" or "yearly"
    success_url: str
    cancel_url: str

class VerifyRequest(BaseModel):
    session_id: str

@router.post("/create-checkout-session")
async def create_checkout_session(data: CheckoutRequest, current_user = Depends(get_current_user)):
    # Determine pricing based on plan_type
    if data.plan_type == "monthly":
        price_name = "Premium Monthly Membership"
        price_amount = 1500  # $15.00
    elif data.plan_type == "yearly":
        price_name = "Premium Yearly Membership"
        price_amount = 12000  # $120.00
    else:
        raise HTTPException(status_code=400, detail="Invalid plan type")

    try:
        session = await run_in_threadpool(
            stripe.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": price_name,
                        "description": "Full access to all courses and practice exam questions.",
                    },
                    "unit_amount": price_amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=data.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=data.cancel_url,
            customer_email=current_user.email,
            client_reference_id=current_user.id,
            metadata={
                "user_id": current_user.id,
                "plan_type": data.plan_type
            }
        )
        return {"session_id": session.id, "checkout_url": session.url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-session")
async def verify_session(data: VerifyRequest):
    try:
        # Blocking network call — see the comment in create_checkout_session.
        session_obj = await run_in_threadpool(stripe.checkout.Session.retrieve, data.session_id)


        session = session_obj.to_dict()

        if session.get("payment_status") == "paid":
            user_id = session.get("client_reference_id")
            if not user_id:
                user_id = (session.get("metadata") or {}).get("user_id")

            if user_id:
                user = await db.user.find_unique(where={"id": user_id})
                if user and user.membershipLevel != "premium":
                    metadata = session.get("metadata") or {}
                    plan_type = metadata.get("plan_type", "monthly")
                    amount = 15.00 if plan_type == "monthly" else 120.00
                    await db.payment.create(
                        data={
                            "userId": user_id,
                            "amount": amount,
                            "planType": plan_type
                        }
                    )
                    user = await db.user.update(
                        where={"id": user_id},
                        data={"membershipLevel": "premium"}
                    )
                return {"status": "success", "membership_level": user.membershipLevel if user else "free", "email": user.email if user else ""}
            else:
                raise HTTPException(status_code=400, detail="User ID not found in session metadata")
        else:
            raise HTTPException(status_code=400, detail="Payment not completed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook is not configured.")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        # Blocking call — see the comment in create_checkout_session.
        event_obj = await run_in_threadpool(stripe.Webhook.construct_event, payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = event_obj.to_dict()

    # Handle the checkout.session.completed event
    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        user_id = session.get("client_reference_id")
        if not user_id:
            user_id = (session.get("metadata") or {}).get("user_id")

        if user_id:
            user = await db.user.find_unique(where={"id": user_id})
            if user and user.membershipLevel != "premium":
                metadata = session.get("metadata") or {}
                plan_type = metadata.get("plan_type", "monthly")
                amount = 15.00 if plan_type == "monthly" else 120.00
                await db.payment.create(
                    data={
                        "userId": user_id,
                        "amount": amount,
                        "planType": plan_type
                    }
                )
                await db.user.update(
                    where={"id": user_id},
                    data={"membershipLevel": "premium"}
                )
                print(f"User {user_id} upgraded to premium via Stripe Webhook.")

    return {"status": "success"}
