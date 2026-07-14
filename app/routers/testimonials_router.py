from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user

router = APIRouter()

DEFAULT_TESTIMONIALS = [
    {
        "id": "default-1",
        "name": "Alex van den Berg",
        "role": "Network Engineer",
        "company": "KPN Netherlands",
        "rating": 5,
        "text": "Passed my CCNA on the first attempt after just 6 weeks of studying on this platform. The practice exam engine is unbeatable."
    },
    {
        "id": "default-2",
        "name": "Sarah Mitchell",
        "role": "IT Administrator",
        "company": "Accenture",
        "rating": 5,
        "text": "The CCNP modules are incredibly detailed. The instructors explain complex routing protocols in a way that actually makes sense."
    },
    {
        "id": "default-3",
        "name": "Michael Okafor",
        "role": "Network Architect",
        "company": "Vodafone",
        "rating": 5,
        "text": "Went from CCNA to CCNP in 8 months. The structured learning path and constant updates make this the best Cisco platform out there."
    }
]

class TestimonialCreate(BaseModel):
    name: str
    role: str
    company: str
    rating: int = Field(5, ge=1, le=5)
    text: str

class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    text: Optional[str] = None

def verify_admin(current_user=Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@router.get("")
async def get_testimonials():
    """Retrieve dynamic testimonials (public)"""
    reviews = await db.testimonial.find_many(order={"createdAt": "desc"})
    if not reviews:
        return DEFAULT_TESTIMONIALS
    return reviews

@router.post("", dependencies=[Depends(verify_admin)])
async def create_testimonial(data: TestimonialCreate):
    """Admin: Add a new student success review"""
    review = await db.testimonial.create(
        data={
            "name": data.name,
            "role": data.role,
            "company": data.company,
            "rating": data.rating,
            "text": data.text
        }
    )
    return review

@router.put("/{review_id}", dependencies=[Depends(verify_admin)])
async def update_testimonial(review_id: str, data: TestimonialUpdate):
    """Admin: Update an existing student success review"""
    review = await db.testimonial.find_unique(where={"id": review_id})
    if not review:
        raise HTTPException(status_code=404, detail="Testimonial not found")

    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.role is not None:
        update_data["role"] = data.role
    if data.company is not None:
        update_data["company"] = data.company
    if data.rating is not None:
        update_data["rating"] = data.rating
    if data.text is not None:
        update_data["text"] = data.text

    updated = await db.testimonial.update(
        where={"id": review_id},
        data=update_data
    )
    return updated

@router.delete("/{review_id}", dependencies=[Depends(verify_admin)])
async def delete_testimonial(review_id: str):
    """Admin: Remove a student success review"""
    review = await db.testimonial.find_unique(where={"id": review_id})
    if not review:
        raise HTTPException(status_code=404, detail="Testimonial not found")

    await db.testimonial.delete(where={"id": review_id})
    return {"status": "deleted", "id": review_id}
