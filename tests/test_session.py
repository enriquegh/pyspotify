from __future__ import unicode_literals

import gc
import mock
import tempfile
import unittest

import spotify


class SessionCallbacksTest(unittest.TestCase):
    def setUp(self):
        self.callbacks = spotify.SessionCallbacks()
        self.sp_session = spotify.ffi.NULL
        self.sp_error = 1

    def test_logged_in_callback(self):
        self.callbacks.logged_in = mock.Mock()

        self.callbacks._logged_in(self.sp_session, self.sp_error)

        self.callbacks.logged_in.assert_called_once_with(
            spotify.Session(self.sp_session), spotify.Error(self.sp_error))

    def test_logged_out_callback(self):
        self.callbacks.logged_out = mock.Mock()

        self.callbacks._logged_out(self.sp_session)

        self.callbacks.logged_out.assert_called_once_with(
            spotify.Session(self.sp_session))

    def test_metadata_updated_callback(self):
        self.callbacks.metadata_updated = mock.Mock()

        self.callbacks._metadata_updated(self.sp_session)

        self.callbacks.metadata_updated.assert_called_once_with(
            spotify.Session(self.sp_session))

    def test_connection_error_callback(self):
        self.callbacks.connection_error = mock.Mock()

        self.callbacks._connection_error(self.sp_session, self.sp_error)

        self.callbacks.connection_error.assert_called_once_with(
            spotify.Session(self.sp_session), spotify.Error(self.sp_error))

    def test_notify_main_thread_callback(self):
        self.callbacks.notify_main_thread = mock.Mock()

        self.callbacks._notify_main_thread(self.sp_session)

        self.callbacks.notify_main_thread.assert_called_once_with(
            spotify.Session(self.sp_session))

    def test_log_message_callback(self):
        self.callbacks.log_message = mock.Mock()
        data = spotify.ffi.new('char[]', b'a log message\n')

        self.callbacks._log_message(self.sp_session, data)

        self.callbacks.log_message.assert_called_once_with(
            spotify.Session(self.sp_session), u'a log message')

    def test_offline_status_updated_callback(self):
        self.callbacks.offline_status_updated = mock.Mock()

        self.callbacks._offline_status_updated(self.sp_session)

        self.callbacks.offline_status_updated.assert_called_once_with(
            spotify.Session(self.sp_session))

    def test_credentials_blob_updated_callback(self):
        self.callbacks.credentials_blob_updated = mock.Mock()
        data = spotify.ffi.new('char[]', b'a credentials blob')

        self.callbacks._credentials_blob_updated(self.sp_session, data)

        self.callbacks.credentials_blob_updated.assert_called_once_with(
            spotify.Session(self.sp_session), b'a credentials blob')


class SessionConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = spotify.SessionConfig()

    def test_api_version_defaults_to_current_lib_version(self):
        self.assertEqual(
            self.config.api_version, spotify.lib.SPOTIFY_API_VERSION)

    def test_cache_location_defaults_to_tmp_in_cwd(self):
        self.assertEqual(self.config.cache_location, b'tmp')

    def test_settings_location_defaults_to_tmp_in_cwd(self):
        self.assertEqual(self.config.settings_location, b'tmp')

    def test_application_key_is_unknown(self):
        self.assertIsNone(self.config.application_key)

    def test_application_key_filename_defaults_to_a_file_in_cwd(self):
        self.assertEqual(
            self.config.application_key_filename, b'spotify_appkey.key')

    def test_user_agent_defaults_to_pyspotify(self):
        self.assertEqual(self.config.user_agent, b'pyspotify')

    def test_callbacks_defaults_to_none(self):
        self.assertIsNone(self.config.callbacks)

    def test_get_application_key_prefers_the_key_attr(self):
        self.config.application_key = b'secret key from attr'

        self.assertEqual(
            self.config.get_application_key(), b'secret key from attr')

    def test_get_application_key_can_load_key_from_file(self):
        self.config.application_key = None
        self.config.application_key_filename = tempfile.mkstemp()[1]

        with open(self.config.application_key_filename, 'wb') as f:
            f.write(b'secret key from file')

        self.assertEqual(
            self.config.get_application_key(), b'secret key from file')

    def test_get_application_key_fails_if_no_key_found(self):
        self.config.application_key_filename = '/nonexistant'

        self.assertRaises(EnvironmentError, self.config.get_application_key)

    def test_get_callbacks_prefers_the_key_attr(self):
        self.config.callbacks = mock.sentinel.my_callbacks

        self.assertEqual(
            self.config.get_callbacks(), mock.sentinel.my_callbacks)

    @mock.patch.object(spotify.session, 'SessionCallbacks')
    def test_get_callbacks_creates_new_callbacks_object_if_needed(self, mock):
        self.config.callbacks = None

        self.config.get_callbacks()

        mock.assert_called_once_with()

    def test_make_sp_session_config_returns_a_c_object(self):
        self.config.application_key = b''

        self.assertIsInstance(
            self.config.make_sp_session_config(), spotify.ffi.CData)

    def test_application_key_size_is_calculated_correctly(self):
        self.config.application_key = b'123'

        sp_session_config = self.config.make_sp_session_config()

        self.assertEqual(sp_session_config.application_key_size, 3)

    def test_global_weakrefs_keeps_struct_parts_alive(self):
        self.config.application_key = b''

        sp_session_config = self.config.make_sp_session_config()

        self.assertIn(sp_session_config, spotify.global_weakrefs)
        self.assertEqual(len(spotify.global_weakrefs[sp_session_config]), 5)


@mock.patch('spotify.session.lib')
class SessionTest(unittest.TestCase):

    @mock.patch.object(spotify.session, 'SessionConfig')
    def test_creates_config_if_none_provided(self, config_cls_mock, lib_mock):
        lib_mock.sp_session_create.return_value = spotify.Error.OK

        spotify.Session()

        config_cls_mock.assert_called_once_with()
        config_obj_mock = config_cls_mock.return_value
        config_obj_mock.make_sp_session_config.assert_called_once_with()

    def test_raises_error_if_not_ok(self, lib_mock):
        lib_mock.sp_session_create.return_value = spotify.Error.BAD_API_VERSION
        config = spotify.SessionConfig()
        config.application_key = b'secret'

        self.assertRaises(spotify.Error, spotify.Session, config=config)

    def test_releases_sp_session_when_session_dies(self, lib_mock):
        sp_session = spotify.ffi.NULL

        def func(sp_session_config, sp_session_ptr):
            sp_session_ptr[0] = sp_session
            return spotify.Error.OK

        lib_mock.sp_session_create.side_effect = func
        config = spotify.SessionConfig()
        config.application_key = b'secret'

        session = spotify.Session(config=config)
        session = None  # noqa
        gc.collect()  # Needed for PyPy

        lib_mock.sp_session_release.assert_called_with(sp_session)

    def test_global_weakrefs_keeps_config_alive(self, lib_mock):
        lib_mock.sp_session_create.return_value = spotify.Error.OK
        config = spotify.SessionConfig()
        config.application_key = b'secret'

        session = spotify.Session(config=config)

        self.assertIn(session.sp_session, spotify.global_weakrefs)
        self.assertEqual(len(spotify.global_weakrefs[session.sp_session]), 1)

    def test_is_equal_if_same_sp_session(self, lib_mock):
        sp_session = mock.sentinel.sp_session

        self.assertEqual(
            spotify.Session(sp_session), spotify.Session(sp_session))

    def test_login_raises_error_if_no_password_and_no_blob(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(AttributeError, session.login, 'alice')

    def test_login_with_password(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.login('alice', 'secret')

        lib_mock.sp_session_login.assert_called_once_with(
            mock.sentinel.sp_session, mock.ANY, mock.ANY,
            False, spotify.ffi.NULL)
        self.assertEqual(
            spotify.ffi.string(lib_mock.sp_session_login.call_args[0][1]),
            b'alice')
        self.assertEqual(
            spotify.ffi.string(lib_mock.sp_session_login.call_args[0][2]),
            b'secret')

    def test_login_with_blob(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.login('alice', blob='secret blob')

        lib_mock.sp_session_login.assert_called_once_with(
            mock.sentinel.sp_session, mock.ANY, spotify.ffi.NULL,
            False, mock.ANY)
        self.assertEqual(
            spotify.ffi.string(lib_mock.sp_session_login.call_args[0][1]),
            b'alice')
        self.assertEqual(
            spotify.ffi.string(lib_mock.sp_session_login.call_args[0][4]),
            b'secret blob')

    def test_login_with_remember_me_flag(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.login('alice', 'secret', remember_me='anything truish')

        lib_mock.sp_session_login.assert_called_once_with(
            mock.sentinel.sp_session, mock.ANY, mock.ANY,
            True, spotify.ffi.NULL)

    def test_login_fail_raises_error(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.NO_SUCH_USER
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(spotify.Error, session.login, 'alice', 'secret')

    def test_relogin(self, lib_mock):
        lib_mock.sp_session_relogin.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.relogin()

        lib_mock.sp_session_relogin.assert_called_once_with(
            mock.sentinel.sp_session)

    def test_relogin_fail_raises_error(self, lib_mock):
        lib_mock.sp_session_relogin.return_value = spotify.Error.NO_CREDENTIALS
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(spotify.Error, session.relogin)

    def test_remembered_user_grows_buffer_to_fit_username(self, lib_mock):
        username = b'alice' * 100

        def func(sp_session, buffer_, buffer_size):
            length = min(len(username), buffer_size - 1)
            buffer_[0:length] = username[:length]
            return len(username)

        lib_mock.sp_session_remembered_user.side_effect = func
        session = spotify.Session(mock.sentinel.sp_session)

        result = session.remembered_user

        lib_mock.sp_session_remembered_user.assert_called_with(
            mock.sentinel.sp_session, mock.ANY, mock.ANY)
        self.assertEqual(result, username)

    def test_remembered_user_is_none_if_not_remembered(self, lib_mock):
        lib_mock.sp_session_remembered_user.return_value = -1
        session = spotify.Session(mock.sentinel.sp_session)

        result = session.remembered_user

        lib_mock.sp_session_remembered_user.assert_called_with(
            mock.sentinel.sp_session, mock.ANY, mock.ANY)
        self.assertIsNone(result)

    def test_user_name(self, lib_mock):
        lib_mock.sp_session_user_name.return_value = spotify.ffi.new(
            'char[]', b'alice')
        session = spotify.Session(mock.sentinel.sp_session)

        result = session.user_name

        lib_mock.sp_session_user_name.assert_called_with(
            mock.sentinel.sp_session)
        self.assertEqual(result, 'alice')

    def test_forget_me(self, lib_mock):
        lib_mock.sp_session_forget_me.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.forget_me()

        lib_mock.sp_session_forget_me.assert_called_with(
            mock.sentinel.sp_session)

    def test_forget_me_fail_raises_error(self, lib_mock):
        lib_mock.sp_session_forget_me.return_value = (
            spotify.Error.BAD_API_VERSION)
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(spotify.Error, session.forget_me)

    @mock.patch('spotify.user.lib')
    def test_user(self, user_lib_mock, lib_mock):
        lib_mock.sp_session_user.return_value = (
            spotify.ffi.new('sp_user **'))
        session = spotify.Session(mock.sentinel.sp_session)

        result = session.user

        lib_mock.sp_session_user.assert_called_with(mock.sentinel.sp_session)
        self.assertIsInstance(result, spotify.User)

    def test_user_if_not_logged_in(self, lib_mock):
        lib_mock.sp_session_user.return_value = spotify.ffi.NULL
        session = spotify.Session(mock.sentinel.sp_session)

        result = session.user

        lib_mock.sp_session_user.assert_called_with(mock.sentinel.sp_session)
        self.assertIsNone(result)

    def test_logout(self, lib_mock):
        lib_mock.sp_session_logout.return_value = spotify.Error.OK
        session = spotify.Session(mock.sentinel.sp_session)

        session.logout()

        lib_mock.sp_session_logout.assert_called_once_with(
            mock.sentinel.sp_session)

    def test_logout_fail_raises_error(self, lib_mock):
        lib_mock.sp_session_login.return_value = spotify.Error.BAD_API_VERSION
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(spotify.Error, session.logout)

    def test_process_events_returns_next_timeout(self, lib_mock):
        def func(sp_session, int_ptr):
            int_ptr[0] = 500
            return spotify.Error.OK

        lib_mock.sp_session_process_events.side_effect = func
        session = spotify.Session(mock.sentinel.sp_session)

        timeout = session.process_events()

        self.assertEqual(timeout, 500)

    def test_process_events_fail_raises_error(self, lib_mock):
        lib_mock.sp_session_process_events.return_value = (
            spotify.Error.BAD_API_VERSION)
        session = spotify.Session(mock.sentinel.sp_session)

        self.assertRaises(spotify.Error, session.process_events)
