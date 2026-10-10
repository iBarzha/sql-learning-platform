import uuid

from django.test import SimpleTestCase

from sandbox.session_manager import owned_by


class _Session:
    def __init__(self, user_id):
        self.user_id = user_id


class SessionOwnerTests(SimpleTestCase):
    """The owner id is a UUID in the worker that created the session and a string after
    another worker rebuilt it from the session store; both must match the same user."""

    def test_uuid_owner_matches_same_uuid(self):
        uid = uuid.uuid4()
        self.assertTrue(owned_by(_Session(uid), uid))

    def test_recovered_string_owner_matches_uuid(self):
        uid = uuid.uuid4()
        self.assertTrue(owned_by(_Session(str(uid)), uid))

    def test_other_user_is_rejected(self):
        self.assertFalse(owned_by(_Session(str(uuid.uuid4())), uuid.uuid4()))

    def test_anonymous_request_cannot_use_owned_session(self):
        self.assertFalse(owned_by(_Session(uuid.uuid4()), None))

    def test_unowned_session_is_open(self):
        self.assertTrue(owned_by(_Session(None), uuid.uuid4()))
        self.assertTrue(owned_by(_Session(None), None))
