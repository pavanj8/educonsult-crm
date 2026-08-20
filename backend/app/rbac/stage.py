from enum import StrEnum


class Stage(StrEnum):
    """Application pipeline stages (Requirements §5, Journey J18, Epic E25).

    Non-terminal stages form a forward progression path:
      REGISTERED → COUNSELING → UNIVERSITY_SHORTLISTING → APPLICATION_SUBMITTED →
      DOCUMENT_VERIFICATION → OFFER_LETTER → VISA_PROCESSING → ENROLLED

    The LOAN_PROCESSING stage is optional and only entered after VISA_PROCESSING
    when the student opts for loan tracking (E36/E37), then returns to VISA_PROCESSING.

    Terminal stages are final and cannot transition to any other stage:
      ENROLLED, REJECTED, WITHDRAWN
    """

    REGISTERED = "registered"
    COUNSELING = "counseling"
    UNIVERSITY_SHORTLISTING = "university_shortlisting"
    APPLICATION_SUBMITTED = "application_submitted"
    DOCUMENT_VERIFICATION = "document_verification"
    OFFER_LETTER = "offer_letter"
    VISA_PROCESSING = "visa_processing"
    LOAN_PROCESSING = "loan_processing"
    ENROLLED = "enrolled"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"

    @classmethod
    def terminal_stages(cls) -> set["Stage"]:
        """Return the set of terminal stages (no outgoing transitions)."""
        return {cls.ENROLLED, cls.REJECTED, cls.WITHDRAWN}

    @classmethod
    def non_terminal_stages(cls) -> set["Stage"]:
        """Return the set of non-terminal stages."""
        all_stages = set(cls)
        return all_stages - cls.terminal_stages()

    @property
    def is_terminal(self) -> bool:
        """Return True if this stage is terminal."""
        return self in self.terminal_stages()
