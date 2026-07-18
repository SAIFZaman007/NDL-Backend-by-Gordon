from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File, Form
from typing import List, Optional
from app.db import db
from app.routers.auth_router import get_current_user
from app.services import cloudinary_service
from pydantic import BaseModel
import re
import datetime

router = APIRouter()


# ── Upload configuration ───────────────────────────────────────
# Cover images are uploaded straight to Cloudinary (see
# app/services/cloudinary_service.py) — only the resulting secure_url is
# ever stored in BlogPost.coverImage. save_cover_image/delete_cover_image
# keep their original names and signatures below; only their internals
# changed, so create_post/update_post/delete_post needed no further changes
# beyond awaiting them.
async def save_cover_image(coverImage: UploadFile) -> str:
    """
    Validate an uploaded cover image and upload it to Cloudinary.
    Returns the secure_url stored in BlogPost.coverImage.
    """
    return await cloudinary_service.upload_image(coverImage, folder=cloudinary_service.BLOG_FOLDER)


async def delete_cover_image(cover_image_url: Optional[str]) -> None:
    """
    Best-effort removal of a Cloudinary-hosted cover image. External URLs
    (e.g. legacy local "/uploads/..." paths, or any other http/https URL)
    are ignored silently — deleting a post must never fail because of
    remote storage state.
    """
    await cloudinary_service.delete_image(cover_image_url)


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
async def create_post(
    title: str = Form(...),
    excerpt: str = Form(...),
    content: str = Form(...),
    category: str = Form(...),
    readTime: Optional[str] = Form("5 min read"),
    published: Optional[bool] = Form(False),
    coverImage: Optional[UploadFile] = File(None),
):
    """Admin: Create a new blog post (multipart/form-data — coverImage is an uploaded file, stored on Cloudinary)"""
    slug = slugify(title)

    # Ensure slug is unique
    existing = await db.blogpost.find_unique(where={"slug": slug})
    if existing:
        slug = f"{slug}-{int(datetime.datetime.now().timestamp())}"

    # Swagger's "Send empty value" checkbox (and some HTTP clients) submit
    # coverImage as an empty part with no filename — treat that as "no image".
    cover_image_url = None
    if coverImage is not None and coverImage.filename:
        cover_image_url = await save_cover_image(coverImage)

    post = await db.blogpost.create(
        data={
            "title": title,
            "slug": slug,
            "excerpt": excerpt,
            "content": content,
            "category": category,
            "coverImage": cover_image_url,
            "readTime": readTime or "5 min read",
            "published": published or False,
        }
    )
    return post


@router.put("/{post_id}", dependencies=[Depends(verify_admin)])
async def update_post(
    post_id: str,
    title: Optional[str] = Form(None),
    excerpt: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    readTime: Optional[str] = Form(None),
    published: Optional[bool] = Form(None),
    coverImage: Optional[UploadFile] = File(None),
):
    """Admin: Update a blog post (multipart/form-data — send coverImage only to replace the current image)"""
    post = await db.blogpost.find_unique(where={"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    update_data = {}
    if title is not None:
        update_data["title"] = title
        update_data["slug"] = slugify(title)
    if excerpt is not None:
        update_data["excerpt"] = excerpt
    if content is not None:
        update_data["content"] = content
    if category is not None:
        update_data["category"] = category
    if readTime is not None:
        update_data["readTime"] = readTime
    if published is not None:
        update_data["published"] = published

    # Only replace the stored image when an actual file was uploaded.
    # Omitting coverImage keeps the existing image untouched.
    if coverImage is not None and coverImage.filename:
        new_cover_url = await save_cover_image(coverImage)
        await delete_cover_image(post.coverImage)  # reclaim the old Cloudinary asset
        update_data["coverImage"] = new_cover_url

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
    await delete_cover_image(post.coverImage)  # remove the orphaned Cloudinary asset
    return {"status": "deleted", "id": post_id}
