#!/usr/bin/env python
#
#   Copyright 2017 - The Android Open Source Project
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

import unittest

from main import RunnerFactory
from metrics.usb_metric import UsbMetric


class RunnerFactoryTestCase(unittest.TestCase):
    def test_create_with_reporter(self):
        self.assertEqual(
            RunnerFactory.create({
                'reporter': ['proto']
            }).reporter_list, ['proto'])

    def test_create_without_reporter(self):
        self.assertEqual(
            RunnerFactory.create({
                'reporter': None
            }).reporter_list, ['logger'])

    def test_metric_none(self):
        self.assertEqual(
            RunnerFactory.create({
                'disk': None,
                'reporter': None
            }).metric_list, [])

    def test_metric_true(self):
        self.assertIsInstance(
            RunnerFactory.create({
                'usb_io': True,
                'reporter': None
            }).metric_list[0], UsbMetric)


if __name__ == '__main__':
    unittest.main()
