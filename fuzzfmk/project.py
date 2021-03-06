################################################################################
#
#  Copyright 2014-2015 Eric Lacombe <eric.lacombe@security-labs.org>
#
################################################################################
#
#  This file is part of fuddly.
#
#  fuddly is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  fuddly is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with fuddly. If not, see <http://www.gnu.org/licenses/>
#
################################################################################

from __future__ import print_function

import sys
import threading
from fuzzfmk.monitor import ProbeStatus

class Project(object):

    name = None
    default_dm = None

    def __init__(self):
        self.probes = {}
        self.operators = {}

    #####################
    ### Configuration ###
    #####################

    def set_logger(self, logger):
        self.logger = logger

    def set_target(self, target):
        self.target = target

    def set_monitor(self, monitor):
        self.monitor = monitor


    def register_new_operator(self, name, obj):

        if name in self.operators:
            print("\n*** /!\\ ERROR: The operator name '%s' is already used\n" % name)
            raise ValueError

        self.operators[name] = {
            'obj': obj
            }

    def register_new_probe(self, name, func, obj=None, blocking=False):

        if name in self.probes:
            print("\n*** /!\\ ERROR: The probe name '%s' is already used\n" % name)
            raise ValueError

        self.probes[name] = {
            'func': func,
            'obj': obj,
            'lock': threading.Lock(),
            'status': ProbeStatus(0),
            'delay': 1.0,
            'stop': threading.Event(),
            'started': False,
            'blocking': blocking
            }


    ##########################
    ### Runtime Operations ###
    ##########################

    def start(self):
        pass

    def stop(self):
        pass

    def get_operator_obj(self, name):
        try:
            ret = self.operators[name]['obj']
        except KeyError:
            return None

        return ret

    def get_operators(self):
        return self.operators

    def is_probe_launched(self, name):
        try:
            self.probes[name]['lock'].acquire()
            ret = self.probes[name]['started']
            self.probes[name]['lock'].release()
        except KeyError:
            return False

        return ret

    def launch_probe(self, name):

        lck = self.probes[name]['lock']

        lck.acquire()
        if self.probes[name]['started']:
            lck.release()
            return False
        lck.release()

        func = self.get_probe_func(name)
        if not func:
            return False

        stop_event = self.probes[name]['stop']

        if self.probes[name]['blocking']:
            evts = self.monitor.get_evts(name)
        else:
            evts = None

        th = threading.Thread(None, func, 'probe.' + name,
                              args=(stop_event, evts, self.target, self.logger))
        th.start()

        lck.acquire()
        self.probes[name]['started'] = True
        lck.release()

        return True


    def quick_reset_probe(self, name, *args):
        try:
            with self.probes[name]['lock']:
                self.probes[name]['obj'].quick_reset(*args)
            return True
        except KeyError:
            return False

    def get_probe_func(self, name):
        try:
            ret = self.probes[name]['func']
        except KeyError:
            return None

        return ret

    def get_probe_lock(self, name):
        try:
            ret = self.probes[name]['lock']
        except KeyError:
            return None

        return ret

    def stop_probe(self, name):
        try:
            self.probes[name]['lock'].acquire()
            if self.probes[name]['started']:
                self.probes[name]['stop'].set()
            self.probes[name]['lock'].release()
        except KeyError:
            return False

        return True

    def reset_probe(self, name):
        try:
            self.probes[name]['lock'].acquire()
            self.probes[name]['status'] = ProbeStatus(0)
            self.probes[name]['started'] = False
            self.probes[name]['stop'].clear()
            self.probes[name]['lock'].release()
        except KeyError:
            return False

        return True


    def set_probe_delay(self, name, delay):
        try:
            self.probes[name]['lock'].acquire()
            self.probes[name]['delay'] = delay
            self.probes[name]['lock'].release()
        except KeyError:
            return False

        return True

    def get_probe_delay(self, name):
        try:
            self.probes[name]['lock'].acquire()
            ret = self.probes[name]['delay']
            self.probes[name]['lock'].release()
        except KeyError:
            return None

        return ret

    def set_probe_status(self, name, status):
        try:
            self.probes[name]['lock'].acquire()
            self.probes[name]['status'] = status
            self.probes[name]['lock'].release()
        except KeyError:
            return False

        return True

    def get_probe_status(self, name):
        try:
            self.probes[name]['lock'].acquire()
            ret = self.probes[name]['status']
            self.probes[name]['lock'].release()
        except KeyError:
            return None

        return ret

    def get_probes(self):
        return self.probes

