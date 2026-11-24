"""Retained entry point for Reports AI regressions.

AI-02 replaces unrestricted text and numeric-pool assertions with shared named
fact/structured-output tests, including the original auth/privacy boundaries.
No provider or database network calls: secure_ai_suite imports the offline harness.
"""
from unittest import main
from secure_ai_suite import SecureSummaryTests,TransportTests

if __name__=='__main__':main(verbosity=2)
