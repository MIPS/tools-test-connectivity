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

from metrics.metric import Metric
from utils import job
from utils import shell


class NetworkMetric(Metric):
    """Determines if test server is connected to network by passed in ip's.

    The dev servers pinged is determined by the cli arguments.
    """

    HOSTNAME_COMMAND = 'hostname | cut -d- -f1'
    PING_COMMAND = 'ping -c 1 -W 1 {}'

    def __init__(self, ip_list=['8.8.8.8'], shell=shell.ShellCommand(job)):
        Metric.__init__(self, shell=shell)
        self.ips = ip_list

    def get_prefix_hostname(self):
        """Gets the hostname prefix of the test station.

        Example, on android-test-server-14, it would return, android

        Returns:
            The prefix of the hostname.
        """
        return self._shell.run('hostname | cut -d- -f1').stdout

    def check_connected(self, ip_list=None):
        """Determines if a network connection can be established to a dev server

        Args:
            ip_list: The list of ip's to ping.
        Returns:
            A dictionary of ip addresses as keys, and whether they're connected
            as values.
        """

        if ip_list is None:
            ip_list = self.ips

        ip_dict = {}
        for ip in ip_list:
            # -c 1, ping once, -W 1, set timeout 1 second.
            stat = self._shell.run(
                self.PING_COMMAND.format(ip), ignore_status=True).exit_status
            ip_dict[ip] = stat == 0
        return ip_dict

    def get_speed(self):
        # TODO(cjmoberg) need to determine specifics before continuing.
        raise NotImplementedError

    def gather_metric(self):
        is_connected = self.check_connected(self.ips)
        return {'connected': is_connected, 'speed': float('inf')}
