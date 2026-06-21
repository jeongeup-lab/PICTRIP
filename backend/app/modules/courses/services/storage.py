"""CRS saved-course persistence.

A saved course is the chosen draft (or any client-built itinerary) persisted
under the user. We store every stop in a single CourseDay(day_number=1) - the
draft output is a flat list - which still satisfies the courses -> course_days
-> course_items chain. Spot data (validation + cover image + detail cards) is
resolved through the SPT service boundary; CRS never reads SPT models.
"""

from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFound, ValidationFailed
from app.modules.courses.models import Course, CourseDay, CourseItem
from app.modules.courses.schemas import CourseCreate
from app.modules.courses.services.rows import CourseDetailRow, CourseItemCard, CourseSummaryRow
from app.modules.spots.services import load_active_spot_cards_by_ids


async def create_course(
    session: AsyncSession,
    *,
    user_id: int,
    payload: CourseCreate,
) -> CourseSummaryRow:
    """Persist a course owned by `user_id`.

    Every referenced content_id (items + optional base) must be an *active*
    spot, validated up front via the SPT service boundary - `course_items.content_id`
    is a RESTRICT FK, so an unknown id would otherwise surface as a 500 instead
    of a clean ValidationFailed. Items are renumbered to a dense 0-based
    position in the client's given order. One transaction; the service owns the
    commit.
    """
    item_ids = [it.contentId for it in payload.items]
    ids_to_check = list(
        dict.fromkeys(item_ids + ([payload.baseContentId] if payload.baseContentId else []))
    )
    cards = await load_active_spot_cards_by_ids(session, ids_to_check)
    missing = [cid for cid in ids_to_check if cid not in cards]
    if missing:
        raise ValidationFailed(f"존재하지 않거나 비공개된 관광지가 포함되어 있습니다: {missing[0]}")

    course = Course(
        user_id=user_id,
        name=payload.name,
        base_content_id=payload.baseContentId,
        duration_type=payload.durationType,
        pace_type=payload.paceType,
        companion_type=payload.companionType,
        course_type=payload.courseType,
    )
    session.add(course)
    await session.flush()
    await session.refresh(course)  # load server-default created_at
    course_id = course.id
    created_at = course.created_at

    day = CourseDay(course_id=course_id, day_number=1)
    session.add(day)
    await session.flush()
    day_id = day.id

    ordered = sorted(payload.items, key=lambda it: it.position)
    for pos, it in enumerate(ordered):
        session.add(CourseItem(course_day_id=day_id, content_id=it.contentId, position=pos))
    await session.commit()

    # Cover = first stop that actually has an image - matches list_courses so the
    # create response and the subsequent list agree.
    cover_image_url: str | None = None
    for it in ordered:
        card = cards.get(it.contentId)
        if card and card.first_image_url:
            cover_image_url = card.first_image_url
            break
    return CourseSummaryRow(
        id=course_id,
        name=payload.name,
        course_type=payload.courseType,
        duration_type=payload.durationType,
        item_count=len(ordered),
        cover_image_url=cover_image_url,
        created_at=created_at,
    )


async def _course_item_ids(session: AsyncSession, course_ids: list[int]) -> dict[int, list[str]]:
    """content_ids per course, in itinerary order (day, then position)."""
    if not course_ids:
        return {}
    rows = (
        await session.execute(
            select(CourseItem.content_id, CourseDay.course_id)
            .join(CourseDay, CourseDay.id == CourseItem.course_day_id)
            .where(CourseDay.course_id.in_(course_ids))
            .order_by(CourseDay.course_id, CourseDay.day_number, CourseItem.position)
        )
    ).all()
    by_course: dict[int, list[str]] = {}
    for r in rows:
        by_course.setdefault(r.course_id, []).append(r.content_id)
    return by_course


async def list_courses(session: AsyncSession, *, user_id: int) -> list[CourseSummaryRow]:
    """The user's saved courses, most-recently-updated first."""
    courses = list(
        (
            await session.execute(
                select(Course)
                .where(Course.user_id == user_id)
                # id DESC is a stable tiebreaker when two courses share an
                # updated_at (e.g. created in the same transaction / second).
                .order_by(Course.updated_at.desc(), Course.id.desc())
            )
        )
        .scalars()
        .all()
    )
    if not courses:
        return []

    items_by_course = await _course_item_ids(session, [c.id for c in courses])
    all_ids = list({cid for ids in items_by_course.values() for cid in ids})
    cards = await load_active_spot_cards_by_ids(session, all_ids)

    summaries: list[CourseSummaryRow] = []
    for c in courses:
        ids = items_by_course.get(c.id, [])
        cover: str | None = None
        for cid in ids:
            card = cards.get(cid)
            if card and card.first_image_url:
                cover = card.first_image_url
                break
        summaries.append(
            CourseSummaryRow(
                id=c.id,
                name=c.name,
                course_type=c.course_type,
                duration_type=c.duration_type,
                item_count=len(ids),
                cover_image_url=cover,
                created_at=c.created_at,
            )
        )
    return summaries


async def get_course(session: AsyncSession, *, user_id: int, course_id: int) -> CourseDetailRow:
    """A saved course with hydrated, ordered spot cards. Scoped by user_id so a
    course that isn't the caller's reads as 404 (don't leak existence)."""
    course = await session.scalar(
        select(Course).where(Course.id == course_id, Course.user_id == user_id)
    )
    if course is None:
        raise ResourceNotFound("코스를 찾을 수 없습니다.")

    items_by_course = await _course_item_ids(session, [course_id])
    ordered_ids = items_by_course.get(course_id, [])
    cards = await load_active_spot_cards_by_ids(session, ordered_ids)

    items: list[CourseItemCard] = []
    for cid in ordered_ids:
        card = cards.get(cid)
        if card is None:
            continue  # spot hidden since the course was saved - drop from detail
        items.append(
            CourseItemCard(
                position=len(items),
                content_id=card.content_id,
                title=card.title,
                first_image_url=card.first_image_url,
                addr1=card.addr1,
                mapx=card.mapx,
                mapy=card.mapy,
            )
        )

    summary = CourseSummaryRow(
        id=course.id,
        name=course.name,
        course_type=course.course_type,
        duration_type=course.duration_type,
        item_count=len(items),
        cover_image_url=items[0].first_image_url if items else None,
        created_at=course.created_at,
    )
    return CourseDetailRow(summary=summary, items=items)


async def delete_course(session: AsyncSession, *, user_id: int, course_id: int) -> None:
    """Delete the caller's course (cascade removes its days + items). 404 if it
    isn't the caller's (or doesn't exist)."""
    removed = await session.scalar(
        sa_delete(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .returning(Course.id)
    )
    await session.commit()
    if removed is None:
        raise ResourceNotFound("코스를 찾을 수 없습니다.")
