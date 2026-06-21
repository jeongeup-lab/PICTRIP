"""CRS service facade.

Keep the public import path stable (`app.modules.courses.services`) while the
draft-generation and saved-course persistence implementations live in focused
modules.
"""

from app.modules.courses.services.draft import STRATEGIES, DraftCourse, build_draft_courses
from app.modules.courses.services.rows import CourseDetailRow, CourseItemCard, CourseSummaryRow
from app.modules.courses.services.storage import (
    create_course,
    delete_course,
    get_course,
    list_courses,
)

__all__ = [
    "STRATEGIES",
    "CourseDetailRow",
    "CourseItemCard",
    "CourseSummaryRow",
    "DraftCourse",
    "build_draft_courses",
    "create_course",
    "delete_course",
    "get_course",
    "list_courses",
]
