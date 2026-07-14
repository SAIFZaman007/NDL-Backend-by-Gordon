from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Dict, Any
from app.db import db
from app.routers.auth_router import get_current_user
from app.prisma_client import Json

router = APIRouter()

# Default fallback values for about page
DEFAULT_ABOUT = {
    "title": "About Network Design Labs",
    "subTitle": "About",
    "paragraphs": [
        "Network Design Labs was founded by a team of CCIE-certified Cisco networking professionals to deliver structured, practical, and exam-focused IT training.",
        "Unlike generic e-learning platforms, every course on this platform is hand-crafted by our own instructors. The focus is entirely on Cisco certifications: CCNA, CCNP, and Cybersecurity — because that's what IT professionals need to advance in their careers.",
        "The platform features high-quality video lectures, downloadable lab exercises, and a comprehensive practice exam engine. Everything you need to pass your Cisco exam on the first try."
    ],
    "stats": [
        {"icon": "Award", "label": "Cisco CCIE Certified", "sub": "Enterprise Infrastructure"},
        {"icon": "Users", "label": "5,000+ Students Trained", "sub": "Across 50+ countries"},
        {"icon": "Target", "label": "95% First-Attempt Pass Rate", "sub": "CCNA & CCNP combined"},
        {"icon": "BookOpen", "label": "40+ Video Courses", "sub": "With hands-on labs"}
    ]
}

class AboutContentUpdate(BaseModel):
    title: str
    subTitle: str
    paragraphs: List[str]
    stats: List[Dict[str, str]]

def verify_admin(current_user=Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@router.get("")
async def get_about_content():
    """Retrieve about section content (public)"""
    content = await db.aboutcontent.find_first()
    if not content:
        # Return default content directly
        return DEFAULT_ABOUT
    return content

@router.post("", dependencies=[Depends(verify_admin)])
async def update_about_content(data: AboutContentUpdate):
    """Admin: Upsert/Update the single about section config"""
    existing = await db.aboutcontent.find_first()
    if existing:
        updated = await db.aboutcontent.update(
            where={"id": existing.id},
            data={
                "title": data.title,
                "subTitle": data.subTitle,
                "paragraphs": Json(data.paragraphs),
                "stats": Json(data.stats)
            }
        )
        return updated
    else:
        new_content = await db.aboutcontent.create(
            data={
                "title": data.title,
                "subTitle": data.subTitle,
                "paragraphs": Json(data.paragraphs),
                "stats": Json(data.stats)
            }
        )
        return new_content
