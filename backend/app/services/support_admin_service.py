# Purpose: Provide administrator support views and commands while preserving the case service access and history rules.
"""Admin facade. Financial commands are deliberately not exposed here."""
from app.services.support_service import list_cases,detail,command

# List support cases through the shared service with explicit administrator access.
def cases(db,user,filters):return list_cases(db,user,filters,admin=True)
# Read support case details through the shared service with explicit administrator access.
def case(db,user,reference):return detail(db,user,reference,admin=True)
# Apply a support command through the shared service with explicit administrator access.
def update(db,user,reference,payload):return command(db,user,reference,payload,admin=True)
