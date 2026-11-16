"""Database-free QR-join structure and validation checks."""
import unittest

from pydantic import ValidationError

from app.core.database import Base
from app.main import app
from app.schemas.customer_join import JoinDecision, JoinSubmission


class CustomerJoinStaticTests(unittest.TestCase):
    def test_models_and_constraints(self):
        for table in ("business_join_links", "customer_join_requests", "customer_profiles"):
            self.assertIn(table, Base.metadata.tables)
        profiles = Base.metadata.tables["customer_profiles"]
        self.assertTrue(any(c.name == "uq_customer_profile_business_user" for c in profiles.constraints))
        requests = Base.metadata.tables["customer_join_requests"]
        self.assertTrue(any(c.name == "uq_customer_join_business_user" for c in requests.constraints))

    def test_route_roles(self):
        routes = app.openapi()["paths"]
        self.assertIn("get", routes["/api/v1/business-join/{public_code}"])
        self.assertIn("post", routes["/api/v1/customer/join-requests"])
        self.assertIn("post", routes["/api/v1/shop-owner/businesses/{business_id}/join-requests/{request_id}/decision"])

    def test_input_restriction(self):
        with self.assertRaises(ValidationError):
            JoinSubmission(public_code="abc")
        with self.assertRaises(ValidationError):
            JoinSubmission(public_code="A" * 32, customer_user_id=1)
        with self.assertRaises(ValidationError):
            JoinDecision(decision="link")


if __name__ == "__main__":
    unittest.main()
