from fastapi import APIRouter, HTTPException, Depends, status, Request
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel
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
        session = stripe.checkout.Session.create(
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-session")
async def verify_session(data: VerifyRequest):
    try:
        session = stripe.checkout.Session.retrieve(data.session_id)
        if session.payment_status == "paid":
            user_id = session.client_reference_id
            if not user_id:
                user_id = session.metadata.get("user_id")

            if user_id:
                user = await db.user.find_unique(where={"id": user_id})
                if user and user.membershipLevel != "premium":
                    plan_type = session.metadata.get("plan_type", "monthly") if session.metadata else "monthly"
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not sig_header or not webhook_secret:
        # Fallback processing if webhook is not configured with secret
        try:
            event = stripe.Event.construct_from(
                await request.json(), stripe.api_key
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
    else:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if not user_id:
            user_id = session.get("metadata", {}).get("user_id")
            
        if user_id:
            user = await db.user.find_unique(where={"id": user_id})
            if user and user.membershipLevel != "premium":
                metadata = session.get("metadata", {})
                plan_type = metadata.get("plan_type", "monthly") if metadata else "monthly"
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
