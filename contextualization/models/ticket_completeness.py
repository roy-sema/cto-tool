from enum import StrEnum


class StageCategory(StrEnum):
    READY_FOR_WORK = "Ready for Work"
    UNDERWAY = "Underway"
    DONE = "Done"
    BACKLOG = "Backlog"
    WILL_NOT_DO = "Will Not Do"


class TicketCategory(StrEnum):
    BUG = "Bug"
    STORY = "Story"
    INCIDENT = "Incident"
    REQUEST = "Request"
    MANUAL_TESTING = "Manual Testing"
    AUTOMATED_TESTING = "Automated Testing"
    OTHER = "Other"
