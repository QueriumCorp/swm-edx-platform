"""
Tests of API module.
"""
from unittest.mock import patch

from datetime import datetime, timezone
import ddt
from django.conf import settings
from django.core import mail
from django.test import TestCase

from common.djangoapps.student.tests.factories import UserFactory
from lms.djangoapps.verify_student.api import (
    create_verification_attempt,
    send_approval_email,
    update_verification_attempt_status,
)
from lms.djangoapps.verify_student.exceptions import VerificationAttemptInvalidStatus
from lms.djangoapps.verify_student.models import SoftwareSecurePhotoVerification, VerificationAttempt
from lms.djangoapps.verify_student.statuses import VerificationAttemptStatus


@ddt.ddt
class TestSendApprovalEmail(TestCase):
    """
    Test cases for the send_approval_email API method.
    """

    def setUp(self):
        super().setUp()

        self.user = UserFactory.create()
        self.attempt = SoftwareSecurePhotoVerification(
            status = "submitted",
            user = self.user
        )
        self.attempt.save()

    def _assert_verification_approved_email(self, expiration_date):
        """Check that a verification approved email was sent."""
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.subject == 'Your édX ID verification was approved!'
        assert 'Your édX ID verification photos have been approved' in email.body
        assert expiration_date.strftime("%m/%d/%Y") in email.body

    @ddt.data(True, False)
    def test_send_approval(self, use_ace):
        with patch.dict(settings.VERIFY_STUDENT, {'USE_DJANGO_MAIL': use_ace}):
            send_approval_email(self.attempt)
            self._assert_verification_approved_email(self.attempt.expiration_datetime)


@ddt.ddt
class CreateVerificationAttempt(TestCase):
    """
    Test cases for the create_verification_attempt API method.
    """

    def setUp(self):
        super().setUp()

        self.user = UserFactory.create()
        self.attempt = VerificationAttempt(
            user = self.user,
            name = 'Tester McTest',
            status = VerificationAttemptStatus.created,
            expiration_datetime = datetime(2024, 12, 31, tzinfo = timezone.utc)
        )
        self.attempt.save()

    def test_create_verification_attempt(self):
        expected_id = 2
        self.assertEqual(
            create_verification_attempt(
                user = self.user,
                name = 'Tester McTest',
                status = VerificationAttemptStatus.created,
                expiration_datetime = datetime(2024, 12, 31, tzinfo = timezone.utc)
            ),
            expected_id
        )
        verification_attempt = VerificationAttempt.objects.get(id = expected_id)

        self.assertEqual(verification_attempt.user, self.user)
        self.assertEqual(verification_attempt.name, 'Tester McTest')
        self.assertEqual(verification_attempt.status, VerificationAttemptStatus.created)
        self.assertEqual(verification_attempt.expiration_datetime, datetime(2024, 12, 31, tzinfo = timezone.utc))

    def test_create_verification_attempt_no_expiration_datetime(self):
        expected_id = 2
        self.assertEqual(
            create_verification_attempt(
                user = self.user,
                name = 'Tester McTest',
                status = VerificationAttemptStatus.created,
            ),
            expected_id
        )
        verification_attempt = VerificationAttempt.objects.get(id = expected_id)

        self.assertEqual(verification_attempt.user, self.user)
        self.assertEqual(verification_attempt.name, 'Tester McTest')
        self.assertEqual(verification_attempt.status, VerificationAttemptStatus.created)
        self.assertEqual(verification_attempt.expiration_datetime, None)


@ddt.ddt
class UpdateVerificationAttemptStatus(TestCase):
    """
    Test cases for the update_verification_attempt_status API method.
    """

    def setUp(self):
        super().setUp()

        self.user = UserFactory.create()
        self.attempt = VerificationAttempt(
            user = self.user,
            name = 'Tester McTest',
            status = VerificationAttemptStatus.created,
            expiration_datetime = datetime(2024, 12, 31, tzinfo = timezone.utc)
        )
        self.attempt.save()

    @ddt.data(
        VerificationAttemptStatus.pending,
        VerificationAttemptStatus.approved,
        VerificationAttemptStatus.denied,
    )
    def test_update_verification_attempt_status(self, to_status):
        update_verification_attempt_status(attempt_id = self.attempt.id, status = to_status)

        verification_attempt = VerificationAttempt.objects.get(id = self.attempt.id)

        # These are fields whose values should not change as a result of this update.
        self.assertEqual(verification_attempt.user, self.user)
        self.assertEqual(verification_attempt.name, 'Tester McTest')
        self.assertEqual(verification_attempt.expiration_datetime, datetime(2024, 12, 31, tzinfo = timezone.utc))

        # This field's value should change as a result of this update.
        self.assertEqual(verification_attempt.status, to_status)

    # These are statuses used in edx-name-affirmation's VerifiedName model and persona-integration's unique
    # VerificationAttempt model, and not by verify_student's VerificationAttempt model.
    @ddt.data(
        'completed',
        'failed',
        'submitted',
        'expired',
    )
    def test_update_verification_attempt_status_invalid(self, to_status):
        self.assertRaises(
            VerificationAttemptInvalidStatus,
            update_verification_attempt_status,
            attempt_id = self.attempt.id,
            status = to_status,
        )

    def test_update_verification_attempt_status_not_found(self):
        self.assertRaises(
            VerificationAttempt.DoesNotExist,
            update_verification_attempt_status,
            attempt_id = 999999,
            status = VerificationAttemptStatus.approved,
        )
