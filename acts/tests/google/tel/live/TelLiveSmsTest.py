#!/usr/bin/env python3.4
#
#   Copyright 2016 - Google
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""
    Test Script for Telephony Pre Check In Sanity
"""

import time
from queue import Empty
from acts.test_utils.tel.TelephonyBaseTest import TelephonyBaseTest
from acts.test_utils.tel.tel_defines import GEN_3G
from acts.test_utils.tel.tel_defines import GEN_4G
from acts.test_utils.tel.tel_defines import PHONE_TYPE_CDMA
from acts.test_utils.tel.tel_defines import PHONE_TYPE_GSM
from acts.test_utils.tel.tel_defines import RAT_3G
from acts.test_utils.tel.tel_defines import VT_STATE_BIDIRECTIONAL
from acts.test_utils.tel.tel_defines import WAIT_TIME_ANDROID_STATE_SETTLING
from acts.test_utils.tel.tel_defines import WFC_MODE_WIFI_PREFERRED
from acts.test_utils.tel.tel_test_utils import call_setup_teardown
from acts.test_utils.tel.tel_test_utils import \
    ensure_network_generation_for_subscription
from acts.test_utils.tel.tel_test_utils import ensure_network_generation
from acts.test_utils.tel.tel_test_utils import ensure_phones_idle
from acts.test_utils.tel.tel_test_utils import ensure_wifi_connected
from acts.test_utils.tel.tel_test_utils import mms_send_receive_verify
from acts.test_utils.tel.tel_test_utils import mms_receive_verify_after_call_hangup
from acts.test_utils.tel.tel_test_utils import multithread_func
from acts.test_utils.tel.tel_test_utils import set_call_state_listen_level
from acts.test_utils.tel.tel_test_utils import setup_sim
from acts.test_utils.tel.tel_test_utils import sms_send_receive_verify
from acts.test_utils.tel.tel_video_utils import phone_setup_video
from acts.test_utils.tel.tel_video_utils import is_phone_in_call_video_bidirectional
from acts.test_utils.tel.tel_video_utils import video_call_setup_teardown
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_1x
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_2g
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_3g
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_csfb
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_iwlan
from acts.test_utils.tel.tel_voice_utils import is_phone_in_call_volte
from acts.test_utils.tel.tel_voice_utils import phone_setup_3g
from acts.test_utils.tel.tel_voice_utils import phone_setup_csfb
from acts.test_utils.tel.tel_voice_utils import phone_setup_data_general
from acts.test_utils.tel.tel_voice_utils import phone_setup_iwlan
from acts.test_utils.tel.tel_voice_utils import phone_setup_voice_2g
from acts.test_utils.tel.tel_voice_utils import phone_setup_voice_3g
from acts.test_utils.tel.tel_voice_utils import phone_setup_volte
from acts.test_utils.tel.tel_voice_utils import phone_setup_voice_general
from acts.utils import rand_ascii_str


class TelLiveSmsTest(TelephonyBaseTest):
    def __init__(self, controllers):
        TelephonyBaseTest.__init__(self, controllers)

        # The path for "sim config file" should be set
        # in "testbed.config" entry "sim_conf_file".
        self.wifi_network_ssid = self.user_params["wifi_network_ssid"]
        self.wifi_network_pass = self.user_params.get("wifi_network_pass")
        # Try to put SMS and call on different help device
        # If it is a three phone test bed, use the first one as dut,
        # use the second one as sms/mms help device, use the third one
        # as the active call help device.
        self.caller = self.android_devices[0]
        if len(self.android_devices) > 2:
            self.callee = self.android_devices[2]
        else:
            self.callee = self.android_devices[1]
        self.message_lengths = (50, 160, 180)

    def setup_class(self):
        TelephonyBaseTest.setup_class(self)
        is_roaming = False
        for ad in self.android_devices:
            #verizon supports sms over wifi. will add more carriers later
            if "vzw" in [
                    sub["operator"] for sub in ad.cfg["subscription"].values()
            ]:
                ad.sms_over_wifi = True
            else:
                ad.sms_over_wifi = False
            ad.adb.shell("su root setenforce 0")
            #not needed for now. might need for image attachment later
            #ad.adb.shell("pm grant com.google.android.apps.messaging "
            #             "android.permission.READ_EXTERNAL_STORAGE")
            if getattr(ad, 'data_roaming', False):
                is_roaming = True
        if is_roaming:
            # roaming device does not allow message of length 180
            self.message_lengths = (50, 160)

    def teardown_test(self):
        ensure_phones_idle(self.log, self.android_devices)

    def _sms_test(self, ads):
        """Test SMS between two phones.

        Returns:
            True if success.
            False if failed.
        """
        for length in self.message_lengths:
            message_array = [rand_ascii_str(length)]
            if not sms_send_receive_verify(self.log, ads[0], ads[1],
                                           message_array):
                ads[0].log.warning("SMS of length %s test failed", length)
                return False
            else:
                ads[0].log.info("SMS of length %s test succeeded", length)
        self.log.info("SMS test of length %s characters succeeded.",
                      self.message_lengths)
        return True

    def _mms_test(self, ads):
        """Test MMS between two phones.

        Returns:
            True if success.
            False if failed.
        """
        for length in self.message_lengths:
            message_array = [("Test Message", rand_ascii_str(length), None)]
            if not mms_send_receive_verify(self.log, ads[0], ads[1],
                                           message_array):
                self.log.warning("MMS of body length %s test failed", length)
                return False
            else:
                self.log.info("MMS of body length %s test succeeded", length)
        self.log.info("MMS test of body lengths %s succeeded",
                      self.message_lengths)
        return True

    def _mms_test_after_call_hangup(self, ads):
        """Test MMS send out after call hang up.

        Returns:
            True if success.
            False if failed.
        """
        args = [
            self.log, ads[0], ads[1],
            [("Test Message", "Basic Message Body", None)]
        ]
        if not mms_send_receive_verify(*args):
            self.log.info("MMS send in call is suspended.")
            if not mms_receive_verify_after_call_hangup(*args):
                self.log.error(
                    "MMS is not send and received after call release.")
                return False
            else:
                self.log.info("MMS is send and received after call release.")
                return True
        else:
            self.log.info("MMS is send and received successfully in call.")
            return True

    def _sms_test_mo(self, ads):
        return self._sms_test([ads[0], ads[1]])

    def _sms_test_mt(self, ads):
        return self._sms_test([ads[1], ads[0]])

    def _mms_test_mo(self, ads):
        return self._mms_test([ads[0], ads[1]])

    def _mms_test_mt(self, ads):
        return self._mms_test([ads[1], ads[0]])

    def _mms_test_mo_after_call_hangup(self, ads):
        return self._mms_test_after_call_hangup([ads[0], ads[1]])

    def _mms_test_mt_after_call_hangup(self, ads):
        return self._mms_test_after_call_hangup([ads[1], ads[0]])

    def _mo_sms_in_3g_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_3g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mt_sms_in_3g_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_3g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mo_mms_in_3g_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_3g,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mo(ads)
        else:
            return self._mms_test_mo_after_call_hangup(ads)

    def _mt_mms_in_3g_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_3g,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mt(ads)
        else:
            return self._mms_test_mt_after_call_hangup(ads)

    def _mo_sms_in_2g_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mt_sms_in_2g_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mo_mms_in_2g_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mo(ads)
        else:
            return self._mms_test_mo_after_call_hangup(ads)

    def _mt_mms_in_2g_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mt(ads)
        else:
            return self._mms_test_mt_after_call_hangup(ads)

    def _mo_sms_in_1x_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_1x,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mt_sms_in_1x_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_1x,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mo_mms_in_1x_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_1x,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mo(ads)
        else:
            return self._mms_test_mo_after_call_hangup(ads)

    def _mt_mms_in_1x_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_1x,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mt(ads)
        else:
            return self._mms_test_mt_after_call_hangup(ads)

    def _mo_sms_in_1x_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_1x,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mt_sms_in_csfb_call(self, ads):
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_csfb,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    def _mo_mms_in_csfb_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_csfb,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mo(ads)
        else:
            return self._mms_test_mo_after_call_hangup(ads)

    def _mt_mms_in_csfb_call(self, ads, wifi=False):
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                self.caller,
                self.callee,
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_csfb,
                verify_callee_func=None):
            return False

        if ads[0].sms_over_wifi and wifi:
            return self._mms_test_mt(ads)
        else:
            return self._mms_test_mt_after_call_hangup(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_general(self):
        """Test SMS basic function between two phone. Phones in any network.

        Airplane mode is off.
        Send SMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_general, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_general(self):
        """Test SMS basic function between two phone. Phones in any network.

        Airplane mode is off.
        Send SMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_general, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_general(self):
        """Test MMS basic function between two phone. Phones in any network.

        Airplane mode is off.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_general, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_general(self):
        """Test MMS basic function between two phone. Phones in any network.

        Airplane mode is off.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_general, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_2g(self):
        """Test SMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send SMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_2g(self):
        """Test SMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send SMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_2g(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_2g(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_2g_wifi(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 2G.
        Connect to Wifi.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_2g_wifi(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 2G.
        Connect to Wifi.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """
        ads = self.android_devices

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_3g(self):
        """Test SMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send SMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_3g(self):
        """Test SMS basic function between two phone. Phones in 3g network.

        Airplane mode is off.
        Send SMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_3g(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 3G.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_3g(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 3G.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_3g_wifi(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 3G.
        Connect to Wifi.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_3g_wifi(self):
        """Test MMS basic function between two phone. Phones in 3g network.

        Airplane mode is off. Phone in 3G.
        Connect to Wifi.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_4g(self):
        """Test SMS basic function between two phone. Phones in LTE network.

        Airplane mode is off.
        Send SMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices
        if (not phone_setup_data_general(self.log, ads[1]) and
                not phone_setup_voice_general(self.log, ads[1])):
            self.log.error("Failed to setup PhoneB.")
            return False
        if not ensure_network_generation(self.log, ads[0], GEN_4G):
            self.log.error("DUT Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_4g(self):
        """Test SMS basic function between two phone. Phones in LTE network.

        Airplane mode is off.
        Send SMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        if (not phone_setup_data_general(self.log, ads[1]) and
                not phone_setup_voice_general(self.log, ads[1])):
            self.log.error("Failed to setup PhoneB.")
            return False
        if not ensure_network_generation(self.log, ads[0], GEN_4G):
            self.log.error("DUT Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_4g(self):
        """Test MMS text function between two phone. Phones in LTE network.

        Airplane mode is off.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_4g(self):
        """Test MMS text function between two phone. Phones in LTE network.

        Airplane mode is off. Phone in 4G.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_4g_wifi(self):
        """Test MMS text function between two phone. Phones in LTE network.

        Airplane mode is off. Phone in 4G.
        Connect to Wifi.
        Send MMS from PhoneA to PhoneB.
        Verify received message on PhoneB is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)
        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_4g_wifi(self):
        """Test MMS text function between two phone. Phones in LTE network.

        Airplane mode is off. Phone in 4G.
        Connect to Wifi.
        Send MMS from PhoneB to PhoneA.
        Verify received message on PhoneA is correct.

        Returns:
            True if success.
            False if failed.
        """

        ads = self.android_devices

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_volte(self):
        """ Test MO SMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_volte(self):
        """ Test MT SMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_volte(self):
        """ Test MO MMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._mms_test_mo(ads):
            self.log.error("MMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_volte(self):
        """ Test MT MMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._mms_test_mt(ads):
            self.log.error("MMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_volte_wifi(self):
        """ Test MO MMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)
        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._mms_test_mo(ads):
            self.log.error("MMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_volte_wifi(self):
        """ Test MT MMS during a MO VoLTE call.

        Make sure PhoneA is in LTE mode (with VoLTE).
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_volte, (self.log, ads[0])), (phone_setup_volte,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)
        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_volte,
                verify_callee_func=None):
            return False

        if not self._mms_test_mt(ads):
            self.log.error("MMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_wcdma(self):
        """ Test MO SMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma SMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_sms_in_3g_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_wcdma(self):
        """ Test MT SMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma SMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_sms_in_3g_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_wcdma(self):
        """ Test MO MMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_mms_in_3g_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_wcdma(self):
        """ Test MT MMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_mms_in_3g_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_wcdma_wifi(self):
        """ Test MO MMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mo_mms_in_3g_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_wcdma_wifi(self):
        """ Test MT MMS during a MO wcdma call.

        Make sure PhoneA is in wcdma mode.
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this wcdma MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)
        return self._mt_mms_in_3g_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_csfb(self):
        """ Test MO SMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_sms_in_csfb_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_csfb(self):
        """ Test MT SMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive receive on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_sms_in_csfb_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_csfb(self):
        """ Test MO MMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_mms_in_csfb_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_csfb(self):
        """ Test MT MMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive receive on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma MMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_mms_in_csfb_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_csfb_wifi(self):
        """ Test MO MMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mo_mms_in_csfb_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_csfb_wifi(self):
        """ Test MT MMS during a MO csfb wcdma/gsm call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Connect PhoneA to Wifi.
        Call from PhoneA to PhoneB, accept on PhoneB, receive receive on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this csfb wcdma MMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mt_mms_in_csfb_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_1x(self):
        """ Test MO SMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x SMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_sms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_1x(self):
        """ Test MT SMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x SMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_sms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_1x(self):
        """ Test MO MMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Send MMS on PhoneA during the call, MMS is send out after call is released.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_mms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_1x(self):
        """ Test MT MMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_mms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_1x_wifi(self):
        """ Test MO MMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Send MMS on PhoneA during the call, MMS is send out after call is released.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mo_mms_in_1x_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_1x_wifi(self):
        """ Test MT MMS during a MO 1x call.

        Make sure PhoneA is in 1x mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this 1x MMS test.")
            return False

        tasks = [(phone_setup_3g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mt_mms_in_1x_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_csfb_1x(self):
        """ Test MO SMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_sms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_csfb_1x(self):
        """ Test MT SMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_sms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_csfb_1x(self):
        """ Test MO MMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_mms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_csfb_1x(self):
        """ Test MT MMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x MMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_mms_in_1x_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_csfb_1x_wifi(self):
        """ Test MO MMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x SMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mo_mms_in_1x_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_csfb_1x_wifi(self):
        """ Test MT MMS during a MO csfb 1x call.

        Make sure PhoneA is in LTE mode (no VoLTE).
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is CDMA phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_CDMA):
            self.log.error("Not CDMA phone, abort this csfb 1x MMS test.")
            return False

        tasks = [(phone_setup_csfb, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mt_mms_in_1x_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_iwlan(self):
        """ Test MO SMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_iwlan(self):
        """ Test MT SMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_iwlan(self):
        """ Test MO MMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_iwlan(self):
        """ Test MT MMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_apm_wifi_wfc_off(self):
        """ Test MO SMS, Phone in APM, WiFi connected, WFC off.

        Make sure PhoneA APM, WiFi connected, WFC off.
        Make sure PhoneB is able to make/receive call/sms.
        Send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices
        phone_setup_voice_general(self.log, ads[0])
        tasks = [(ensure_wifi_connected, (
            self.log, ads[0], self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_apm_wifi_wfc_off(self):
        """ Test MT SMS, Phone in APM, WiFi connected, WFC off.

        Make sure PhoneA APM, WiFi connected, WFC off.
        Make sure PhoneB is able to make/receive call/sms.
        Receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices
        phone_setup_voice_general(self.log, ads[0])
        tasks = [(ensure_wifi_connected, (
            self.log, ads[0], self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_apm_wifi_wfc_off(self):
        """ Test MO MMS, Phone in APM, WiFi connected, WFC off.

        Make sure PhoneA APM, WiFi connected, WFC off.
        Make sure PhoneB is able to make/receive call/sms.
        Send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices
        phone_setup_voice_general(self.log, ads[0])
        tasks = [(ensure_wifi_connected, (
            self.log, ads[0], self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_apm_wifi_wfc_off(self):
        """ Test MT MMS, Phone in APM, WiFi connected, WFC off.

        Make sure PhoneA APM, WiFi connected, WFC off.
        Make sure PhoneB is able to make/receive call/sms.
        Receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices
        phone_setup_voice_general(self.log, ads[0])
        tasks = [(ensure_wifi_connected, (
            self.log, ads[0], self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_iwlan(self):
        """ Test MO SMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_iwlan,
                verify_callee_func=None):
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_iwlan(self):
        """ Test MT SMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_iwlan,
                verify_callee_func=None):
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_iwlan(self):
        """ Test MO MMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_iwlan,
                verify_callee_func=None):
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_iwlan(self):
        """ Test MT MMS, Phone in APM, WiFi connected, WFC WiFi Preferred mode.

        Make sure PhoneA APM, WiFi connected, WFC WiFi preferred mode.
        Make sure PhoneA report iwlan as data rat.
        Make sure PhoneB is able to make/receive call/sms.
        Call from PhoneA to PhoneB, accept on PhoneB.
        Receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """

        ads = self.android_devices

        tasks = [(phone_setup_iwlan,
                  (self.log, ads[0], True, WFC_MODE_WIFI_PREFERRED,
                   self.wifi_network_ssid, self.wifi_network_pass)),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call MMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_iwlan,
                verify_callee_func=None):
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_vt(self):
        """ Test MO SMS, Phone in ongoing VT call.

        Make sure PhoneA and PhoneB in LTE and can make VT call.
        Make Video Call from PhoneA to PhoneB, accept on PhoneB as Video Call.
        Send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_video, (self.log, ads[0])), (phone_setup_video,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        if not video_call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                None,
                video_state=VT_STATE_BIDIRECTIONAL,
                verify_caller_func=is_phone_in_call_video_bidirectional,
                verify_callee_func=is_phone_in_call_video_bidirectional):
            self.log.error("Failed to setup a call")
            return False

        return self._sms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_vt(self):
        """ Test MT SMS, Phone in ongoing VT call.

        Make sure PhoneA and PhoneB in LTE and can make VT call.
        Make Video Call from PhoneA to PhoneB, accept on PhoneB as Video Call.
        Receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_video, (self.log, ads[0])), (phone_setup_video,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        if not video_call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                None,
                video_state=VT_STATE_BIDIRECTIONAL,
                verify_caller_func=is_phone_in_call_video_bidirectional,
                verify_callee_func=is_phone_in_call_video_bidirectional):
            self.log.error("Failed to setup a call")
            return False

        return self._sms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_vt(self):
        """ Test MO MMS, Phone in ongoing VT call.

        Make sure PhoneA and PhoneB in LTE and can make VT call.
        Make Video Call from PhoneA to PhoneB, accept on PhoneB as Video Call.
        Send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_video, (self.log, ads[0])), (phone_setup_video,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        if not video_call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                None,
                video_state=VT_STATE_BIDIRECTIONAL,
                verify_caller_func=is_phone_in_call_video_bidirectional,
                verify_callee_func=is_phone_in_call_video_bidirectional):
            self.log.error("Failed to setup a call")
            return False

        return self._mms_test_mo(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_vt(self):
        """ Test MT MMS, Phone in ongoing VT call.

        Make sure PhoneA and PhoneB in LTE and can make VT call.
        Make Video Call from PhoneA to PhoneB, accept on PhoneB as Video Call.
        Receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices

        tasks = [(phone_setup_video, (self.log, ads[0])), (phone_setup_video,
                                                           (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        if not video_call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                None,
                video_state=VT_STATE_BIDIRECTIONAL,
                verify_caller_func=is_phone_in_call_video_bidirectional,
                verify_callee_func=is_phone_in_call_video_bidirectional):
            self.log.error("Failed to setup a call")
            return False

        return self._mms_test_mt(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mo_in_call_gsm(self):
        """ Test MO SMS during a MO gsm call.

        Make sure PhoneA is in gsm mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm SMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mo(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_sms_mt_in_call_gsm(self):
        """ Test MT SMS during a MO gsm call.

        Make sure PhoneA is in gsm mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive SMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm SMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        self.log.info("Begin In Call SMS Test.")
        if not call_setup_teardown(
                self.log,
                ads[0],
                ads[1],
                ad_hangup=None,
                verify_caller_func=is_phone_in_call_2g,
                verify_callee_func=None):
            return False

        if not self._sms_test_mt(ads):
            self.log.error("SMS test fail.")
            return False

        return True

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mo_in_call_gsm(self):
        """ Test MO MMS during a MO gsm call.

        Make sure PhoneA is in gsm mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm MMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mo_mms_in_2g_call(ads)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_gsm(self):
        """ Test MT MMS during a MO gsm call.

        Make sure PhoneA is in gsm mode.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm MMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False

        return self._mt_mms_in_2g_call(ads)

    def test_mms_mo_in_call_gsm_wifi(self):
        """ Test MO MMS during a MO gsm call.

        Make sure PhoneA is in gsm mode with Wifi connected.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, send MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm MMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mo_mms_in_2g_call(ads, wifi=True)

    @TelephonyBaseTest.tel_test_wrap
    def test_mms_mt_in_call_gsm_wifi(self):
        """ Test MT MMS during a MO gsm call.

        Make sure PhoneA is in gsm mode with wifi connected.
        Make sure PhoneB is able to make/receive call.
        Call from PhoneA to PhoneB, accept on PhoneB, receive MMS on PhoneA.

        Returns:
            True if pass; False if fail.
        """
        ads = self.android_devices
        # Make sure PhoneA is GSM phone before proceed.
        if (ads[0].droid.telephonyGetPhoneType() != PHONE_TYPE_GSM):
            self.log.error("Not GSM phone, abort this gsm MMS test.")
            return False

        tasks = [(phone_setup_voice_2g, (self.log, ads[0])),
                 (phone_setup_voice_general, (self.log, ads[1]))]
        if not multithread_func(self.log, tasks):
            self.log.error("Phone Failed to Set Up Properly.")
            return False
        ensure_wifi_connected(self.log, ads[0], self.wifi_network_ssid,
                              self.wifi_network_pass)

        return self._mt_mms_in_2g_call(ads, wifi=True)
