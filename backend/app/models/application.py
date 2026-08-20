from sqlalchemy import Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage


class Application(TenantScopedBase):
    """Student university/program application (E18; Journey J11).

    ``university_id`` and ``program_id`` reference master data tables added in E14.
    """

    __tablename__ = "applications"

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=PipelineStage.REGISTERED,
    )
