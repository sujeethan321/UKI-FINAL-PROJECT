
"""Offline regression: MySQL BOOL reflection must not fail valid schema gates."""

import sys

from pathlib import Path
from unittest import TestCase, main

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from sqlalchemy import Boolean, Integer

from sqlalchemy.dialects.mysql import (
    TINYINT,
    BIGINT,
    dialect,
)

from app.services.schema_integrity import reviewed_boolean_storage


class BooleanReflectionTests(TestCase):

    def test_mysql_boolean_compiles_as_bool(self):

        self.assertIn(
            str(
                Boolean().compile(dialect=dialect())
            ).upper(),
            ('BOOL', 'BOOLEAN'),
        )

        self.assertNotEqual(
            Boolean()._type_affinity,
            TINYINT(1)._type_affinity,
        )

        self.assertTrue(
            reviewed_boolean_storage(
                Boolean(),
                TINYINT(1),
                'mysql',
            )
        )

    def test_reject_other_storage(self):

        for reflected in (
            TINYINT(),
            TINYINT(2),
            TINYINT(1, unsigned=True),
            TINYINT(1, zerofill=True),
            BIGINT(),
            Integer(),
        ):
            self.assertFalse(
                reviewed_boolean_storage(
                    Boolean(),
                    reflected,
                    'mysql',
                )
            )

        self.assertFalse(
            reviewed_boolean_storage(
                Integer(),
                TINYINT(1),
                'mysql',
            )
        )

        self.assertFalse(
            reviewed_boolean_storage(
                Boolean(),
                TINYINT(1),
                'sqlite',
            )
        )


if __name__ == '__main__':
    main()
