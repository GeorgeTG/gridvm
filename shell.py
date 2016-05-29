#!/usr/bin/env python3
import sys
import subprocess
import argparse
import time

from collections import OrderedDict
from threading import Thread

import logging
#logging.disable(logging.ERROR)

from gridvm.simplescript.runtime.runtime import Runtime, LocalRequest
#                      YO DWAG, WE HEARD YOU LIKE RUNTIMES

import blessings

term = blessings.Terminal()
VERSION = 0.3

CHECK = term.green('✓')
CROSS = term.red('✘')

PROMPT = '{}|{}~>{}'.format(term.green, term.red, term.normal)

REQUIRED = '1-3-3-7'

COMMANDS = OrderedDict()
COMMANDS['list_runtimes'] = [ ]
COMMANDS['list_programs'] = [ ]
COMMANDS['shutdown'] = [ ]
COMMANDS['auto_balance'] = [ ]
COMMANDS['migrate'] = [ ('program_id', REQUIRED), ('thread_id', REQUIRED), ('runtime_id', REQUIRED) ]
COMMANDS['clear'] = []
COMMANDS['help'] = [ ('command', None) ]
COMMANDS['version'] = []
COMMANDS['exit'] = []


DESCRIPTIONS = {
    'list_runtimes': 'List all runtimes',
    'list_programs': 'List programs for this runtime',
    'migrate': 'Migrate a thread to another runtime',
    'auto_balance': 'Autopmatic thread balancing',
    'shutdown': 'Shut this runtime down',
    'version': "Display version information",
    'exit': "Exit",
    'clear': "Clear the screen",
    'help': "Call me when you need me"
}

client = None
last_len = 0
lines = 1

programs = []
threads = []


def list_programs():
    global runtime, programs, threads
    runtime.add_local_request(LocalRequest.LIST_PROGRAMS)
    (programs, threads) = runtime.get_local_result()
    for i, program in enumerate(programs):
        print('{}: Program {}:'.format(i, program))
        print('Index | Real ID')
        for j, thread in enumerate(threads[i]):
            print('     {}:{}'.format(j, thread))

    return True

def command_ok():
    global last_len
    sys.stdout.write( ((term.move_up() * lines)
        + term.move_x(last_len + 6)
        + CHECK + (term.move_down() * lines)) )

def command_failed():
    global last_len
    sys.stdout.write( ((term.move_up() * lines)
        +term.move_x(last_len + 6)
        + CROSS + (term.move_down()*lines)) )

def shutdown():
    global runtime
    runtime.shutdown()

def version():
    print("{}hermes shell {}v{}{}{}".format(
        term.cyan, term.red, term.green, VERSION, term.normal))

def clear():
    try:
        subprocess.call("clear")
    except:
        pass
    version()
    pinfo("Try 'help' for commands")

def exit():
    shutdown()
    sys.exit(0)

def pinfo(dim):
    global lines
    lines += 1
    print(term.yellow(dim))

def perror(err):
    command_failed()
    if isinstance(err, Exception):
        print(term.red('{}. \n{} Reason:{}'.
            format(err.message, term.underline, err.cause)))
    else:
        print(term.red_underline(err))

def parse_command(command):
    parts = command.split(' ')

    command = parts.pop(0)
    args = parts

    if command in COMMANDS:
        req_args = COMMANDS[command]
    else:
        perror('Bad command: "{}". Try "help"'.format(command))
        return

    la = len(args)
    lra = len(req_args)
    if la > lra:
        perror('Too many arguments')
        return
    elif la < lra:
        # check if missing args are required
        left_args = req_args[la:]
        for arg in left_args:
            if arg[1] is REQUIRED:
                perror('~arg {} is required for command {}'.\
                        format(arg[0], command))
                return
            else:
                # add default
                args.append(arg[1])
    try:
        ret = globals()[command](*args)
    except ValueError:
        perror('Bad arguments: ' + str(args))
        return False
    if ret:
        command_ok()
    else:
        command_failed()
    return ret

def help(command=None):
    if command:
        try:
            command_help(command)
        except KeyError:
            perror('Bad command: ' + command)
        return

    version()
    print("A command argument in brackets is optional and it's default")
    print("value is shown in parenthesis next to it. E.g. [arg](default)")
    for command in COMMANDS.keys():
        command_help(command)

def command_help(command):
    args = COMMANDS[command]
    print(term.green(command.ljust(11)), end=': ')

    args_str=''
    for arg, default in args:
        if default is REQUIRED:
            args_str += arg + ' '
        else:
            if default is None:
                default = 'None'
            args_str += "[{}]({}) ".format(arg, default)

    if len(args) == 0:
        args_str='~'
    print(args_str.ljust(24), '-', end=' ')
    print(DESCRIPTIONS[command])

def main():
    global runtime, last_len, lines

    parser = argparse.ArgumentParser()
    parser.add_argument('--interface', '-i',
            action='store', metavar='interface')

    interface = sys.argv[1]
    programs = sys.argv[2:]

    runtime = Runtime(interface=interface)
    for program in programs:
        runtime.load_program(program)

    # Create thread for runtime
    runtime_thread = Thread(target=runtime.run)
    runtime_thread.start()


    clear()

    try:
        while True:
            print(PROMPT, end=' ')
            command = input()

            last_len = len(command)
            lines = 1

            parse_command(command)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('')
        if runtime:
            runtime.shutdown()
            runtime_thread.join()

if __name__ == '__main__':
    main()
