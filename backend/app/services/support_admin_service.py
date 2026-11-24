"""Admin facade. Financial commands are deliberately not exposed here."""
from app.services.support_service import list_cases,detail,command

def cases(db,user,filters):return list_cases(db,user,filters,admin=True)
def case(db,user,reference):return detail(db,user,reference,admin=True)
def update(db,user,reference,payload):return command(db,user,reference,payload,admin=True)
