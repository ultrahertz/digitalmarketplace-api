from flask import json
from nose.tools import assert_equal, assert_not_equal, assert_in
from app import db, encryption, formats
from app.models import User, Supplier
from datetime import datetime
from .helpers import BaseApplicationTest, JSONUpdateTestMixin


class TestUsersAuth(BaseApplicationTest):
    def test_should_validate_credentials(self):
        with self.app.app_context():
            response = self.client.post(
                '/users',
                data=json.dumps({
                    'users': {
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890',
                        'role': 'buyer',
                        'name': 'joe bloggs'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['emailAddress'], 'joeblogs@email.com')

    def test_should_validate_mixedcase_credentials(self):
        with self.app.app_context():
            response = self.client.post(
                '/users',
                data=json.dumps({
                    'users': {
                        'emailAddress': 'joEblogS@EMAIL.com',
                        'password': '1234567890',
                        'role': 'buyer',
                        'name': 'joe bloggs'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'JOEbloGS@email.com',
                        'password': '1234567890'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['emailAddress'], 'joeblogs@email.com')

    def test_should_return_404_for_no_user(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890'}}),
                content_type='application/json')

            assert_equal(response.status_code, 404)
            data = json.loads(response.get_data())
            assert_equal(data['authorization'], False)

    def test_should_return_403_for_bad_password(self):
        with self.app.app_context():
            response = self.client.post(
                '/users',
                data=json.dumps({
                    'users': {
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890',
                        'role': 'buyer',
                        'name': 'joe bloggs'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'joeblogs@email.com',
                        'password': 'this is not right'}}),
                content_type='application/json')

            assert_equal(response.status_code, 403)
            data = json.loads(response.get_data())
            assert_equal(data['authorization'], False)


class TestUsersPost(BaseApplicationTest, JSONUpdateTestMixin):
    method = "post"
    endpoint = "/users"

    def test_can_post_a_user(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'role': 'buyer',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 200)
        data = json.loads(response.get_data())["users"]
        assert_equal(data["emailAddress"], "joeblogs@email.com")

    def test_can_post_an_admin_user(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'role': 'admin',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 200)
        data = json.loads(response.get_data())["users"]
        assert_equal(data["emailAddress"], "joeblogs@email.com")

    def test_can_post_a_supplier_user(self):
        with self.app.app_context():
            db.session.add(
                Supplier(supplier_id=1, name=u"Supplier 1")
            )
            db.session.commit()

        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'supplierId': 1,
                    'role': 'supplier',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 200)
        data = json.loads(response.get_data())["users"]
        assert_equal(data["emailAddress"], "joeblogs@email.com")
        assert_equal(data["supplier"]["name"], "Supplier 1")
        assert_equal(data["supplier"]["supplierId"], 1)

    def test_should_reject_a_supplier_user_with_invalid_supplier_id(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'supplierId': 999,
                    'role': 'supplier',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        data = json.loads(response.get_data())["error"]
        assert_equal(response.status_code, 400)
        assert_equal(data, "Invalid supplier id")

    def test_should_reject_a_supplier_user_with_no_supplier_id(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'role': 'supplier',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        data = json.loads(response.get_data())["error"]
        assert_equal(response.status_code, 400)
        assert_equal(data, "No supplier id provided for supplier user")

    def test_can_post_a_user_with_hashed_password(self):
        with self.app.app_context():
            response = self.client.post(
                '/users',
                data=json.dumps({
                    'users': {
                        'hashpw': True,
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890',
                        'role': 'buyer',
                        'name': 'joe bloggs'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            user = User.query.filter(
                User.email_address == 'joeblogs@email.com') \
                .first()
            assert_not_equal(user.password, '1234567890')

    def test_can_post_a_user_without_hashed_password(self):
        with self.app.app_context():
            response = self.client.post(
                '/users',
                data=json.dumps({
                    'users': {
                        'hashpw': False,
                        'emailAddress': 'joeblogs@email.com',
                        'password': '1234567890',
                        'role': 'buyer',
                        'name': 'joe bloggs'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            user = User.query.filter(
                User.email_address == 'joeblogs@email.com') \
                .first()
            assert_equal(user.password, '1234567890')

    def test_posting_same_email_twice_is_an_error(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'role': 'buyer',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 200)

        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '1234567890',
                    'role': 'buyer',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 409)

    def test_return_400_for_invalid_user_json(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '',
                    'role': 'buyer',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 400)
        data = json.loads(response.get_data())["error"]
        assert_equal(data, "JSON was not a valid format")

    def test_return_400_for_invalid_user_role(self):
        response = self.client.post(
            '/users',
            data=json.dumps({
                'users': {
                    'emailAddress': 'joeblogs@email.com',
                    'password': '0000000000',
                    'role': 'invalid',
                    'name': 'joe bloggs'}}),
            content_type='application/json')

        assert_equal(response.status_code, 400)
        data = json.loads(response.get_data())["error"]
        assert_equal(data, "JSON was not a valid format")


class TestUsersUpdate(BaseApplicationTest):
    def setup(self):
        now = datetime.now()
        super(TestUsersUpdate, self).setup()
        with self.app.app_context():
            user = User(
                id=123,
                email_address="test@test.com",
                name="my name",
                password=encryption.hashpw("my long password"),
                active=True,
                locked=False,
                role='buyer',
                created_at=now,
                updated_at=now,
                password_changed_at=now
            )
            db.session.add(user)

            supplier = Supplier(
                supplier_id=456,
                name="A test supplier"
            )
            db.session.add(supplier)
            db.session.commit()

    def test_can_update_password(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'password': '1234567890'
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'test@test.com',
                        'password': '1234567890'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['emailAddress'], 'test@test.com')

    def test_can_update_active(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'active': False
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'test@test.com',
                        'password': 'my long password'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['active'], False)

    def test_can_update_locked(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'locked': True
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'test@test.com',
                        'password': 'my long password'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['locked'], True)

    def test_can_update_name(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'name': 'I Just Got Married'
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'test@test.com',
                        'password': 'my long password'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['name'], 'I Just Got Married')

    def test_can_update_role_and_suppler_id(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'role': 'supplier',
                        'supplierId': 456
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'test@test.com',
                        'password': 'my long password'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['role'], 'supplier')

    def test_can_not_update_role_to_invalid_value(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'role': 'shopkeeper'
                    }}),
                content_type='application/json')

            data = json.loads(response.get_data())["error"]
            assert_equal(response.status_code, 400)
            assert_in("Could not update user", data)

    def test_can_update_email_address(self):
        with self.app.app_context():
            response = self.client.post(
                '/users/123',
                data=json.dumps({
                    'users': {
                        'emailAddress': 'myshinynew@email.address'
                    }}),
                content_type='application/json')

            assert_equal(response.status_code, 200)

            response = self.client.post(
                '/users/auth',
                data=json.dumps({
                    'authUsers': {
                        'emailAddress': 'myshinynew@email.address',
                        'password': 'my long password'}}),
                content_type='application/json')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())['users']
            assert_equal(data['emailAddress'], 'myshinynew@email.address')


class TestUsersGet(BaseApplicationTest):
    def setup(self):
        self.now = datetime.now()
        super(TestUsersGet, self).setup()
        with self.app.app_context():
            user = User(
                id=123,
                email_address="test@test.com",
                name="my name",
                password=encryption.hashpw("my long password"),
                active=True,
                locked=False,
                role='buyer',
                created_at=self.now,
                updated_at=self.now,
                password_changed_at=self.now
            )
            db.session.add(user)
            db.session.commit()

    def test_can_get_a_user_by_id(self):
        with self.app.app_context():
            now_as_text = self.now.strftime("%Y-%m-%dT%H:%M:%S%Z")
            response = self.client.get("/users/123")
            data = json.loads(response.get_data())["users"]
            assert_equal(data['emailAddress'], "test@test.com")
            assert_equal(data['name'], "my name")
            assert_equal(data['role'], "buyer")
            assert_equal(data['active'], True)
            assert_equal(data['locked'], False)
            assert_equal(data['createdAt'], now_as_text)
            assert_equal(data['updatedAt'], now_as_text)
            assert_equal('password' in data, False)
            assert_equal(response.status_code, 200)

    def test_can_get_a_user_by_email(self):
        with self.app.app_context():
            response = self.client.get("/users?email=test@test.com")
            data = json.loads(response.get_data())["users"]
            assert_equal(data['emailAddress'], "test@test.com")
            assert_equal(data['name'], "my name")
            assert_equal(data['role'], "buyer")
            assert_equal(data['active'], True)
            assert_equal(data['locked'], False)
            assert_equal('password' in data, False)
            assert_equal(response.status_code, 200)

    def test_returns_404_for_non_int_id(self):
        response = self.client.get("/users/bogus")
        assert_equal(response.status_code, 404)

    def test_returns_404_for_no_email_supplied(self):
        response = self.client.get("/users?notemail=test@test.com")
        data = json.loads(response.get_data())["error"]
        assert_equal(response.status_code, 404)
        assert_equal(data, "'email' is a required parameter")
