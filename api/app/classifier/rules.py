"""The prefilter's lists. Adding a job board or a keyword is a one-line change here."""

# Mail from these domains, or any subdomain of them, is always a candidate.
JOB_BOARD_DOMAINS = (
    "onlinejobs.ph",
    "indeed.com",
    "jobstreet.com",
    "linkedin.com",
    "greenhouse.io",
    "lever.co",
    "workable.com",
)

# A subject with a word that starts with one of these is a candidate.
SUBJECT_KEYWORDS = (
    "application",
    "applied",
    "interview",
    "candidate",
    "position",
    "unfortunately",
)
