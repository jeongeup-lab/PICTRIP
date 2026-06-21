"""CRS routes. Endpoints mirror API spec §10."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from app.core.auth import CurrentUserId
from app.core.db import DbSession
from app.core.schemas import ok
from app.modules.courses.schemas import (
    CourseCreate,
    CourseDetail,
    CourseItemCard,
    CourseSummary,
    DraftCourseOut,
    DraftRequest,
    DraftResponse,
)
from app.modules.courses.services import (
    CourseDetailRow,
    CourseSummaryRow,
    build_draft_courses,
    create_course,
    delete_course,
    get_course,
    list_courses,
)

router = APIRouter(tags=["CRS · course"])


def _summary_out(row: CourseSummaryRow) -> CourseSummary:
    return CourseSummary(
        id=row.id,
        name=row.name,
        courseType=row.course_type,
        durationType=row.duration_type,
        itemCount=row.item_count,
        coverImageUrl=row.cover_image_url,
        createdAt=row.created_at,
    )


def _detail_out(row: CourseDetailRow) -> CourseDetail:
    s = row.summary
    return CourseDetail(
        id=s.id,
        name=s.name,
        courseType=s.course_type,
        durationType=s.duration_type,
        itemCount=s.item_count,
        coverImageUrl=s.cover_image_url,
        createdAt=s.created_at,
        items=[
            CourseItemCard(
                position=it.position,
                contentId=it.content_id,
                title=it.title,
                firstImageUrl=it.first_image_url,
                addr1=it.addr1,
                mapx=it.mapx,
                mapy=it.mapy,
            )
            for it in row.items
        ],
    )


@router.post(
    "/courses/draft",
    status_code=status.HTTP_200_OK,
    summary="Generate 3 recommended courses (efficient / mood / calm)",
)
async def create_draft(req: DraftRequest, session: DbSession) -> dict[str, Any]:
    courses = await build_draft_courses(
        session,
        base_content_id=req.baseContentId,
        duration=req.duration,
        pace=req.pace,
        companion=req.companion,
    )
    payload = DraftResponse(
        baseContentId=req.baseContentId,
        courses=[
            DraftCourseOut(
                strategy=course.strategy,
                items=[
                    CourseItemCard(
                        position=item.position,
                        contentId=item.content_id,
                        title=item.title,
                        firstImageUrl=item.first_image_url,
                        addr1=item.addr1,
                        mapx=item.mapx,
                        mapy=item.mapy,
                    )
                    for item in course.items
                ],
            )
            for course in courses
        ],
    )
    return ok(payload)


# ---------- Saved courses (auth required) ----------


@router.post(
    "/courses",
    status_code=status.HTTP_201_CREATED,
    summary="Save course (persist the chosen draft)",
)
async def create_saved_course(
    req: CourseCreate,
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    row = await create_course(session, user_id=user_id, payload=req)
    return ok(_summary_out(row))


@router.get(
    "/courses",
    status_code=status.HTTP_200_OK,
    summary="My saved courses list",
)
async def list_saved_courses(
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    rows = await list_courses(session, user_id=user_id)
    return ok([_summary_out(r) for r in rows])


@router.get(
    "/courses/{course_id}",
    status_code=status.HTTP_200_OK,
    summary="Saved course detail (ordered spot cards)",
)
async def get_saved_course(
    course_id: int,
    user_id: CurrentUserId,
    session: DbSession,
) -> dict[str, Any]:
    row = await get_course(session, user_id=user_id, course_id=course_id)
    return ok(_detail_out(row))


@router.delete(
    "/courses/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete saved course",
)
async def delete_saved_course(
    course_id: int,
    user_id: CurrentUserId,
    session: DbSession,
) -> Response:
    await delete_course(session, user_id=user_id, course_id=course_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
