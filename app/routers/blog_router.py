from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from pydantic import BaseModel
import re
import datetime

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


def verify_admin(current_user=Depends(get_current_user)):
    if current_user.email != "admin@gordon.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# ── Pydantic Schemas ───────────────────────────────────────────
class BlogPostCreate(BaseModel):
    title: str
    excerpt: str
    content: str
    category: str
    coverImage: Optional[str] = None
    readTime: Optional[str] = "5 min read"
    published: Optional[bool] = False


class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    coverImage: Optional[str] = None
    readTime: Optional[str] = None
    published: Optional[bool] = None


# ── PUBLIC ENDPOINTS ───────────────────────────────────────────

@router.get("")
async def list_published_posts(
    category: Optional[str] = Query(None),
    limit: int = Query(10, le=50),
    skip: int = Query(0)
):
    """List all published blog posts (public)"""
    where = {"published": True}
    if category:
        where["category"] = category

    posts = await db.blogpost.find_many(
        where=where,
        order={"createdAt": "desc"},
        skip=skip,
        take=limit
    )
    return posts


@router.get("/categories")
async def list_categories():
    """Get all unique blog categories (public)"""
    posts = await db.blogpost.find_many(
        where={"published": True},
        distinct=["category"]
    )
    categories = list(set(p.category for p in posts))
    return {"categories": categories}


@router.get("/{slug}")
async def get_post_by_slug(slug: str):
    """Get a single blog post by slug (public)"""
    post = await db.blogpost.find_unique(where={"slug": slug})
    if not post or not post.published:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


# ── ADMIN ENDPOINTS ────────────────────────────────────────────

@router.get("/admin/all", dependencies=[Depends(verify_admin)])
async def admin_list_all_posts(
    category: Optional[str] = Query(None),
    published: Optional[bool] = Query(None)
):
    """Admin: List ALL posts (published + drafts)"""
    where = {}
    if category:
        where["category"] = category
    if published is not None:
        where["published"] = published

    posts = await db.blogpost.find_many(
        where=where,
        order={"createdAt": "desc"}
    )
    return posts


@router.post("", dependencies=[Depends(verify_admin)])
async def create_post(data: BlogPostCreate):
    """Admin: Create a new blog post"""
    slug = slugify(data.title)

    # Ensure slug is unique
    existing = await db.blogpost.find_unique(where={"slug": slug})
    if existing:
        slug = f"{slug}-{int(datetime.datetime.now().timestamp())}"

    post = await db.blogpost.create(
        data={
            "title": data.title,
            "slug": slug,
            "excerpt": data.excerpt,
            "content": data.content,
            "category": data.category,
            "coverImage": data.coverImage,
            "readTime": data.readTime or "5 min read",
            "published": data.published or False,
        }
    )
    return post


@router.put("/{post_id}", dependencies=[Depends(verify_admin)])
async def update_post(post_id: str, data: BlogPostUpdate):
    """Admin: Update a blog post"""
    post = await db.blogpost.find_unique(where={"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    update_data = {}
    if data.title is not None:
        update_data["title"] = data.title
        update_data["slug"] = slugify(data.title)
    if data.excerpt is not None:
        update_data["excerpt"] = data.excerpt
    if data.content is not None:
        update_data["content"] = data.content
    if data.category is not None:
        update_data["category"] = data.category
    if data.coverImage is not None:
        update_data["coverImage"] = data.coverImage
    if data.readTime is not None:
        update_data["readTime"] = data.readTime
    if data.published is not None:
        update_data["published"] = data.published

    updated = await db.blogpost.update(
        where={"id": post_id},
        data=update_data
    )
    return updated


@router.patch("/{post_id}/publish", dependencies=[Depends(verify_admin)])
async def toggle_publish(post_id: str):
    """Admin: Toggle published/draft status"""
    post = await db.blogpost.find_unique(where={"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    updated = await db.blogpost.update(
        where={"id": post_id},
        data={"published": not post.published}
    )
    return {"id": post_id, "published": updated.published, "status": "published" if updated.published else "draft"}


@router.delete("/{post_id}", dependencies=[Depends(verify_admin)])
async def delete_post(post_id: str):
    """Admin: Delete a blog post"""
    post = await db.blogpost.find_unique(where={"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    await db.blogpost.delete(where={"id": post_id})
    return {"status": "deleted", "id": post_id}
