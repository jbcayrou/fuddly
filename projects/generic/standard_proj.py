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

from fuzzfmk.project import *
from fuzzfmk.monitor import *
from fuzzfmk.operator_helpers import *
from fuzzfmk.plumbing import *
import fuzzfmk.global_resources as gr

project = Project()
project.default_dm = ['mydf','zip']
# If you only want one default DM, provide its name directly as follows:
# project.default_dm = 'mydf'

logger = Logger('standard', export_data=False, explicit_data_recording=True, export_orig=False,
                enable_file_logging=False)

printer1_tg = PrinterTarget(tmpfile_ext='.png')
printer1_tg.set_target_ip('127.0.0.1')
printer1_tg.set_printer_name('PDF')

local_tg = LocalTarget(tmpfile_ext='.png')
local_tg.set_target_path('display')

local2_tg = LocalTarget(tmpfile_ext='.pdf')
local2_tg.set_target_path('okular')

local3_tg = LocalTarget(tmpfile_ext='.zip')
local3_tg.set_target_path('unzip')
local3_tg.set_post_args('-d ' + gr.workspace_folder)

net_tg = NetworkTarget(host='localhost', port=12345, data_semantics='TG1', hold_connection=True)
net_tg.register_new_interface('localhost', 54321, (socket.AF_INET, socket.SOCK_STREAM), 'TG2', server_mode=True)
net_tg.add_additional_feedback_interface('localhost', 7777, (socket.AF_INET, socket.SOCK_STREAM),
                                     fbk_id='My Feedback Source', server_mode=True)
net_tg.set_timeout(fbk_timeout=5, sending_delay=3)


@blocking_probe(project)
class health_check(Probe):

    def start(self, target, logger):
        self.status = ProbeStatus(0)

    def stop(self, target, logger):
        pass

    def main(self, target, logger):
        fb = target.get_feedback()
        if fb is not None:
            byte_string = fb.get_bytes()
            self.status.set_private_info(byte_string)
        self.status.set_status(0)

        if target.is_damaged():
            self.status.set_status(-1)

        if not target.is_alive():
            self.status.set_status(-2)

        return self.status


targets = [(local_tg, health_check),
           (local2_tg, health_check),
           (local3_tg, health_check),
           printer1_tg, net_tg]


@operator(project,
          gen_args={'init': ('make the model walker ignore all the steps until the provided one', 1, int),
                    'max_steps': ("number of test cases to run", 20, int)},
          args={'mode': ('strategy mode (0 or 1)', 0, int),
                'path': ("path of the target application (for LocalTarget's only)", '/usr/bin/display', str)})
class Op1(Operator):

    def start(self, fmk_ops, dm, monitor, target, logger, user_input):

        if isinstance(target, LocalTarget):
            target.set_target_path(self.path)
            self._last_feedback = []

        self.nb_gen_val_cpt = 0
        if self.mode == 1:
            self.nb_gen_val_cpt = self.max_steps // 2
            self.max_steps = self.max_steps - self.nb_gen_val_cpt

        self.gen_ids = []
        for gid in fmk_ops.dynamic_generator_ids():
            self.gen_ids.append(gid)
        print('\n*** Data IDs found: ', self.gen_ids)
        self.init_gen_len = len(self.gen_ids)
        self.current_gen_id = self.gen_ids.pop(0)

        # fmk_ops.set_fuzz_delay(5)
        return True

    def stop(self, fmk_ops, dm, monitor, target, logger):
        if isinstance(target, LocalTarget):
            self._last_feedback = None

    def plan_next_operation(self, fmk_ops, dm, monitor, target, logger, fmk_feedback):

        op = Operation()

        if self.max_steps > 0:
            
            if fmk_feedback.is_flag_set(FmkFeedback.NeedChange):
                try:
                    self.current_gen_id = self.gen_ids.pop(0)
                    op.set_flag(Operation.CleanupDMakers)
                except IndexError:
                    op.set_flag(Operation.Stop)
                    return op

                change_list = fmk_feedback.get_flag_context(FmkFeedback.NeedChange)
                for dmaker, idx in change_list:
                    logger.log_fmk_info('Exhausted data maker [#{:d}]: {:s} ({:s})'.format(idx, dmaker['dmaker_type'], dmaker['dmaker_name']),
                                        nl_before=True, nl_after=False)

            clone_tag = "#{:d}".format(len(self.gen_ids) + 1)

            actions = [(self.current_gen_id + clone_tag, UI(finite=True)), ('tTYPE' + clone_tag, UI(init=self.init))]

            self.max_steps -= 1

        elif self.mode == 1 and self.nb_gen_val_cpt > 0:

            clone_tag2 = "#{:d}".format(self.init_gen_len + len(self.gen_ids) + 1)

            actions = [(self.current_gen_id + clone_tag2, UI(finite=True)), ('tALT' + clone_tag2, UI(init=self.init))]

            self.nb_gen_val_cpt -= 1

        else:
            actions = None

        if actions:
            op.add_instruction(actions)
        else:
            op.set_flag(Operation.Stop)

        return op


    def do_after_all(self, fmk_ops, dm, monitor, target, logger):
        linst = LastInstruction()

        if isinstance(target, LocalTarget):
            health_status = monitor.get_probe_status('health_check')
            info = health_status.get_private_info()

            export = True
            if info in self._last_feedback:
                export = False
            else:
                self._last_feedback.append(info)

            err_code = health_status.get_status()
            if  err_code == -1:
                if export:
                    linst.set_instruction(LastInstruction.ExportData)
                linst.set_operator_feedback('This input has triggered an error, but not a crash!')
                linst.set_operator_status(-err_code) # does not prevent operator to continue so
                                                     # provide a value > 0
            elif err_code == -2:
                linst.set_instruction(LastInstruction.ExportData)
                linst.set_operator_feedback('This input has crashed the target!')
                linst.set_operator_status(-err_code) # does not prevent operator to continue so
                                                     # provide a value > 0
        else:
            linst.set_instruction(LastInstruction.ExportData)
        
        return linst
