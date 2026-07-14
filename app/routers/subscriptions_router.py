from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from app.prisma_client import Json

router = APIRouter()

DEFAULT_PLANS = [
    {
        "id": "default-free",
        "name": "Free",
        "planType": "free",
        "price": 0.0,
        "billingPeriod": "forever",
        "description": "Get started with free preview lessons and limited practice questions.",
        "features": ["Access to first lesson per course", "40 practice exam questions", "Progress tracking", "Community Discord access"],
        "badge": None,
        "cta": "Start Free",
        "featured": False
    },
    {
        "id": "default-monthly",
        "name": "Premium Monthly",
        "planType": "monthly",
        "price": 15.0,
        "billingPeriod": "month",
        "description": "Full access to all Cisco courses and unlimited practice exams.",
        "features": ["All CCNA, CCNP, Cybersecurity courses", "Unlimited practice exam questions", "Download labs & PDF guides", "Priority instructor support", "Progress analytics dashboard"],
        "badge": "Most Popular",
        "cta": "Upgrade Now",
        "featured": True
    },
    {
        "id": "default-yearly",
        "name": "Premium Yearly",
        "planType": "yearly",
        "price": 120.0,
        "billingPeriod": "year",
        "description": "Best value for serious learners. Save 33% vs monthly billing.",
        "features": ["Everything in Monthly plan", "Priority email & Discord support", "Free updates to new exam versions", "Early access to new courses", "Certificate of completion"],
        "badge": "Save 33%",
        "cta": "Get Best Value",
        "featured": False
    }
]

class SubscriptionPlanCreate(BaseModel):
    name: str
    planType: str  # "free", "monthly", "yearly"
    price: float
    billingPeriod: str  # "forever", "month", "year"
    description: str
    features: List[str]
    badge: Optional[str] = None
    cta: str
    featured: Optional[bool] = False

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    planType: Optional[str] = None
    price: Optional[float] = None
    billingPeriod: Optional[str] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    badge: Optional[str] = None
    cta: Optional[str] = None
    featured: Optional[bool] = None

def verify_admin(current_user=Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@router.get("")
async def get_subscription_plans():
    """Retrieve pricing plans (public)"""
    plans = await db.subscriptionplan.find_many(order={"createdAt": "asc"})
    if not plans:
        return DEFAULT_PLANS
    return plans

@router.post("", dependencies=[Depends(verify_admin)])
async def create_subscription_plan(data: SubscriptionPlanCreate):
    """Admin: Create a new subscription plan"""
    # Ensure name uniqueness
    existing = await db.subscriptionplan.find_unique(where={"name": data.name})
    if existing:
        raise HTTPException(status_code=400, detail="Plan name already exists")

    plan = await db.subscriptionplan.create(
        data={
            "name": data.name,
            "planType": data.planType,
            "price": data.price,
            "billingPeriod": data.billingPeriod,
            "description": data.description,
            "features": Json(data.features),
            "badge": data.badge,
            "cta": data.cta,
            "featured": data.featured or False
        }
    )
    return plan

@router.put("/{plan_id}", dependencies=[Depends(verify_admin)])
async def update_subscription_plan(plan_id: str, data: SubscriptionPlanUpdate):
    """Admin: Update an existing subscription plan"""
    plan = await db.subscriptionplan.find_unique(where={"id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.planType is not None:
        update_data["planType"] = data.planType
    if data.price is not None:
        update_data["price"] = data.price
    if data.billingPeriod is not None:
        update_data["billingPeriod"] = data.billingPeriod
    if data.description is not None:
        update_data["description"] = data.description
    if data.features is not None:
        update_data["features"] = Json(data.features)
    if data.badge is not None:
        update_data["badge"] = data.badge
    if data.cta is not None:
        update_data["cta"] = data.cta
    if data.featured is not None:
        update_data["featured"] = data.featured

    updated = await db.subscriptionplan.update(
        where={"id": plan_id},
        data=update_data
    )
    return updated

@router.delete("/{plan_id}", dependencies=[Depends(verify_admin)])
async def delete_subscription_plan(plan_id: str):
    """Admin: Delete a subscription plan"""
    plan = await db.subscriptionplan.find_unique(where={"id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    await db.subscriptionplan.delete(where={"id": plan_id})
    return {"status": "deleted", "id": plan_id}
