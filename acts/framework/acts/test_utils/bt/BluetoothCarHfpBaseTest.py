#/usr/bin/env python3.4
#
# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""
This is base class for tests that exercises different GATT procedures between two connected devices.
Setup/Teardown methods take care of establishing connection, and doing GATT DB initialization/discovery.
"""

import os
from queue import Empty

from acts.test_utils.bt.BluetoothBaseTest import BluetoothBaseTest
from acts.test_utils.bt.bt_test_utils import pair_pri_to_sec
from acts.test_utils.tel.tel_test_utils import ensure_phones_default_state
from acts.test_utils.tel.tel_test_utils import get_phone_number
from acts.test_utils.tel.tel_test_utils import setup_droid_properties
from acts.test_utils.tel.tel_test_utils import toggle_airplane_mode


class BluetoothCarHfpBaseTest(BluetoothBaseTest):
    DEFAULT_TIMEOUT = 15
    ag_phone_number = ""
    re_phone_number = ""

    def __init__(self, controllers):
        BluetoothBaseTest.__init__(self, controllers)
        # HF : HandsFree (CarKitt role)
        self.hf = self.android_devices[0]
        # AG : Audio Gateway (Phone role)
        self.ag = self.android_devices[1]
        # RE : Remote Device (Phone being talked to role)
        if len(self.android_devices) > 2:
            self.re = self.android_devices[2]
        else:
            self.re = None
        if len(self.android_devices) > 3:
            self.re2 = self.android_devices[3]
        else:
            self.re2 = None

    def setup_class(self):
        super(BluetoothCarHfpBaseTest, self).setup_class()
        if not "sim_conf_file" in self.user_params.keys():
            self.log.error("Missing mandatory user config \"sim_conf_file\"!")
            return False
        sim_conf_file = self.user_params["sim_conf_file"]
        if not os.path.isfile(sim_conf_file):
            sim_conf_file = os.path.join(
                self.user_params[Config.key_config_path], sim_conf_file)
            if not os.path.isfile(sim_conf_file):
                self.log.error("Unable to load user config " + sim_conf_file +
                               " from test config file.")
                return False
        setup_droid_properties(self.log, self.ag, sim_conf_file)
        self.ag_phone_number = get_phone_number(self.log, self.ag)
        self.log.info("ag tel: {}".format(self.ag_phone_number))
        if self.re:
            setup_droid_properties(self.log, self.re, sim_conf_file)
            self.re_phone_number = get_phone_number(self.log, self.re)
            self.log.info("re tel: {}".format(self.re_phone_number))
        if self.re2:
            setup_droid_properties(self.log, self.re2, sim_conf_file)
            self.re2_phone_number = get_phone_number(self.log, self.re2)
            self.log.info("re2 tel: {}".format(self.re2_phone_number))
        # Pair and connect the devices.
        if not pair_pri_to_sec(self.hf.droid, self.ag.droid):
            self.log.error("Failed to pair")
            return False
        return True

    def setup_test(self):
        if not super(BluetoothCarHfpBaseTest, self).setup_test():
            return False
        return ensure_phones_default_state(self.log, self.android_devices[1:])

    def teardown_test(self):
        if not super(BluetoothCarHfpBaseTest, self).teardown_test():
            return False
        return ensure_phones_default_state(self.log, self.android_devices[1:])

    def on_fail(self, test_name, begin_time):
        result = True
        if not super(BluetoothCarHfpBaseTest, self).on_fail(test_name,
                                                            begin_time):
            result = False
        ensure_phones_default_state(self.log, self.android_devices[1:])
        return result
