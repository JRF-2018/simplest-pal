# simplest_pal.py
__version__ = '0.0.1' # Time-stamp: <2025-06-13T07:59:25Z>

import sys
import threading
import time
import os
import io
import argparse
import runpy
import pdb
import bdb
import traceback

DEFAULT_LOG_FILE = "pdb_session.log"
IO_POLL_INTERVAL = 0.01

class PdbAutomation:
    """
    Handles PDB automation by hooking sys.stdin/stdout/stderr.
    This implementation uses the original script's stable execution model
    while replacing the threaded input reader with a direct, thread-less
    approach for improved Ctrl-C stability.
    """
    def __init__(self, original_stdin, original_stdout, original_stderr, log_file, quit_on_stop):
        self.original_stdin = original_stdin
        self.original_stdout = original_stdout
        self.original_stderr = original_stderr
        self.log_file = log_file
        self.quit_on_stop = quit_on_stop
        self.output_buffer = io.StringIO()
        self.is_debugging = threading.Event() # Event to indicate if the debugger is active

        sys.stdout = self # Hook standard output
        sys.stderr = self # Hook standard error output
        # Create a new log file and record the session start time
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"--- PDB Session Log Started: {time.ctime()} ---\n")

    def _log_to_file(self, s):
        """
        Appends a string to the log file.
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(s)
        except Exception as e:
            self.original_stdout.write(f"PDB Automation: File logging error: {e}\n")

    def _print_to_console(self, s):
        """
        Writes a string directly to the original standard output.
        """
        self.original_stdout.write(s)
        self.original_stdout.flush()

    def write(self, s):
        """
        Overrides sys.stdout/stderr's write method to write to the output buffer and log file.
        """
        self.output_buffer.write(s)
        self._log_to_file(s)

    def flush(self):
        """
        Overrides sys.stdout/stderr's flush method to flush the original streams.
        """
        self.original_stdout.flush()
        self.original_stderr.flush()

    def readline(self):
        """
        Processes output from PDB, determines automatic commands, or waits for user input.
        """
        # Get all buffered output and clear the buffer
        current_buffered_output = self.output_buffer.getvalue()
        self.output_buffer.truncate(0)
        self.output_buffer.seek(0)

        # Display the captured output to the console
        self._print_to_console(current_buffered_output)

        # --- PDB Automation Logic ---
        ai_interaction_point_present = "AI Interaction Point" in current_buffered_output
        current_code_context_present = "Current Code Context (for AI reference)" in current_buffered_output
        human_consultation_present = "Human Consultation Requested" in current_buffered_output
        pdb_prompt_present = '(Pdb)' in current_buffered_output

        # Auto 'c' (continue) logic when AI interaction point is detected
        if ai_interaction_point_present and current_code_context_present:
            log_msg = "PDB Automation (readline): Auto-continuing (AI interaction context detected).\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "c\n"

        # Auto 'q' (quit) logic when PDB prompt is present and quit_on_stop is enabled
        if pdb_prompt_present and self.quit_on_stop:
            log_msg = "PDB Automation (readline): Auto-quitting as 'quit_on_stop' is enabled.\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "q\n"

        # Auto 'u' (up a frame) logic for internal frames
        is_internal_frame = False
        if pdb_prompt_present:
            # Check if the current output contains a frame within simplest_pal.py
            for line in current_buffered_output.splitlines():
                if line.strip().startswith('>') and os.path.basename(__file__) in line:
                    is_internal_frame = True
                    break
        
        # If in an internal frame without AI interaction context, send 'u 2' to move further up
        if is_internal_frame and (ai_interaction_point_present or human_consultation_present) and not current_code_context_present:
            log_msg = "PDB Automation (readline): In internal frame without context. Auto-sending 'u 2'.\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "u 2\n"
        # If in an internal frame and neither AI interaction nor human consultation is requested, send 'u'
        elif is_internal_frame and not ai_interaction_point_present and not human_consultation_present:
            log_msg = "PDB Automation (readline): Detected unexpected internal frame. Auto-sending 'u'.\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "u\n" # Move up one frame

        # --- Manual Input Logic ---
        # If PDB is showing a prompt, wait for manual user input
        if pdb_prompt_present:
            log_msg = "PDB Automation (readline): Waiting for manual user input.\n"
            self._log_to_file(log_msg)
            # Read directly from original stdin (blocking read, Ctrl-C safe)
            user_command = self.original_stdin.readline()
            if not user_command:
                # If EOF, send quit command
                self._log_to_file("PDB Automation (readline): EOF detected, sending 'q'.\n")
                return "q\n"
            self._log_to_file(f"PDB Automation (readline): User input: {repr(user_command.strip())}\n")
            return user_command
        
        # If no PDB prompt, return empty string (should not typically be reached)
        return "" 

    def enter_debugger_hook(self):
        """
        Called when a debugger session becomes active.
        """
        self.is_debugging.set()
        self._log_to_file("PDB Automation: Debugger session activated.\n")
        self._print_to_console("PDB Automation: Debugger session activated.\n")

    def exit_debugger_hook(self):
        """
        Called when a debugger session becomes inactive.
        """
        self.is_debugging.clear()
        self._log_to_file("PDB Automation: Debugger session deactivated.\n")
        self._print_to_console("PDB Automation: Debugger session deactivated.\n")

    def get_output(self):
        """
        Retrieves buffered output and clears the buffer.
        """
        output = self.output_buffer.getvalue()
        self.output_buffer.truncate(0)
        self.output_buffer.seek(0)
        return output

    def restore_io(self):
        """
        Restores the original standard I/O streams and displays a message about the log file.
        """
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self._print_to_console(f"\nPDB session log saved to '{self.log_file}'.\n")

def simplest_pal_main():
    """
    Main function for Simplest P.A.L. (PDB Automation Layer).
    Runs the specified Python script under the PDB debugger, providing
    automation and interaction capabilities.
    """
    parser = argparse.ArgumentParser(description="PDB debugger automation layer for AI integration.")
    parser.add_argument("script", help="Path to the Python script to run.")
    parser.add_argument("--pal-log", default=DEFAULT_LOG_FILE, help=f"PDB session log file (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--pal-quit-on-stop", default=False, action='store_true', help="Automatically quits the debugger when it stops.")
    args, remaining_args = parser.parse_known_args()

    original_stdin, original_stdout, original_stderr = sys.stdin, sys.stdout, sys.stderr
    pdb_auto = PdbAutomation(original_stdin, original_stdout, original_stderr, args.pal_log, args.pal_quit_on_stop)

    pal_debugger = pdb.Pdb(stdin=pdb_auto, stdout=pdb_auto)

    def set_trace_with_hooks(frame=None):
        """
        Overrides pdb.set_trace and calls debugger hooks.
        """
        pdb_auto.enter_debugger_hook()
        # Use frame from 2 levels up, as in the original script, for correct context
        pal_debugger.set_trace(sys._getframe(2) if frame is None else frame)
        pdb_auto.exit_debugger_hook()
    
    # Replace standard pdb.set_trace with the custom hook
    pdb.set_trace = set_trace_with_hooks

    pdb_auto._print_to_console(f"Simplest P.A.L.: Running target script: '{args.script}'\n")
    sys.argv = [args.script] + remaining_args
    
    script_completed = False
    script_force_quit = False # Set to True if script is explicitly quit
    try:
        # Loop to manage script execution
        while not script_completed:
            try:
                runpy.run_path(args.script, run_name="__main__")
                script_completed = True
                pdb_auto._print_to_console("Simplest P.A.L.: Target script execution completed normally.\n")
            except bdb.BdbQuit:
                # If PDB session is explicitly quit
                script_completed = True
                script_force_quit = True
                pdb_auto._print_to_console("Simplest P.A.L.: PDB session explicitly quit.\n")
            except Exception as e:
                # If any other exception occurs
                pdb_auto._print_to_console(f"Simplest P.A.L.: An exception occurred: {e}\n")
                traceback.print_exc(file=pdb_auto) # Print stack trace to log
                # If PDB is not active after an exception, the script has crashed
                if not pdb_auto.is_debugging.is_set():
                    pdb_auto._print_to_console("Simplest P.A.L.: Unhandled exception in target script, stopping.\n")
                    script_completed = True
                else:
                    pdb_auto._print_to_console("Simplest P.A.L.: Exception caught by PDB. Manual intervention may be required.\n")
            
            # If PDB is still active and not explicitly quit, retry script execution (handles 'c' from nested PDB sessions)
            if pdb_auto.is_debugging.is_set() and not script_force_quit:
                script_completed = False # Continue loop if debugger is still active

            time.sleep(IO_POLL_INTERVAL)

    finally:
        # Cleanup: Deactivate debugger if active, display any remaining buffered output, and restore I/O
        if pdb_auto.is_debugging.is_set():
            pdb_auto.exit_debugger_hook()
        remaining_output = pdb_auto.get_output()
        if remaining_output:
            pdb_auto._print_to_console(remaining_output)
        pdb_auto.restore_io()

if __name__ == "__main__":
    simplest_pal_main()
