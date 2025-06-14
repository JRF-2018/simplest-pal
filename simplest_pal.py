# simplest_pal.py
__version__ = '0.0.5' # Time-stamp: <2025-06-14T07:55:07Z>

# It seems to work now, though it didn't before. It appears the key was to append .apy to importlib.machinery.SOURCE_SUFFIXES before runpy is imported/used.
# This initial block ensures that .apy files can be imported by runpy.
import importlib.machinery
if '.apy' not in importlib.machinery.SOURCE_SUFFIXES:
    importlib.machinery.SOURCE_SUFFIXES.append('.apy')

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
    This implementation utilizes the original script's stable execution model
    while replacing the threaded input reader with a direct, non-threaded
    approach for improved Ctrl-C stability.
    """
    def __init__(self, original_stdin, original_stdout, original_stderr, log_file, quit_on_stop):
        self.original_stdin = original_stdin
        self.original_stdout = original_stdout
        self.original_stderr = original_stderr
        self.log_file = log_file
        self.quit_on_stop = quit_on_stop
        self.output_buffer = io.StringIO()
        self.is_debugging = threading.Event() # Event to indicate if the debugger is currently active

        sys.stdout = self # Hook standard output for PDB interaction and logging
        sys.stderr = self # Hook standard error output for PDB interaction and logging
        
        # Open the log file in write mode to start a new session log
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"--- PDB Session Log Started: {time.ctime()} ---\n")

    def _log_to_file(self, s):
        """
        Appends a string to the dedicated log file.
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(s)
        except Exception as e:
            # Fallback to original stdout if logging fails
            self.original_stdout.write(f"PDB Automation: Error writing to log file: {e}\n")

    def _print_to_console(self, s):
        """
        Writes a string directly to the original standard output (console).
        """
        self.original_stdout.write(s)
        self.original_stdout.flush()

    def write(self, s):
        """
        Overrides sys.stdout/stderr's write method.
        Writes to an internal buffer and the log file.
        """
        self.output_buffer.write(s)
        self._log_to_file(s)

    def flush(self):
        """
        Overrides sys.stdout/stderr's flush method.
        Flushes the original standard output and error streams.
        """
        self.original_stdout.flush()
        self.original_stderr.flush()

    def readline(self):
        """
        Processes output from PDB, determines whether to send an automatic command
        (continue, quit, step up), or waits for manual user input.
        """
        # Retrieve all buffered output and clear the buffer for the next cycle
        current_buffered_output = self.output_buffer.getvalue()
        self.output_buffer.truncate(0)
        self.output_buffer.seek(0)

        # Display the captured PDB output to the console
        self._print_to_console(current_buffered_output)

        # --- PDB Automation Logic ---
        ai_interaction_point_present = "AI Interaction Point" in current_buffered_output
        current_code_context_present = "Current Code Context (for AI reference)" in current_buffered_output
        human_consultation_present = "Human Consultation Requested" in current_buffered_output
        pdb_prompt_present = '(Pdb)' in current_buffered_output

        # Automatically continue ('c') if an AI interaction point with context is detected
        if ai_interaction_point_present and current_code_context_present:
            log_msg = "PDB Automation (readline): Auto-continuing (AI interaction context detected).\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "c\n"

        # Automatically quit ('q') if the PDB prompt is present and auto-quit-on-stop is enabled
        if pdb_prompt_present and self.quit_on_stop:
            log_msg = "PDB Automation (readline): Auto-quitting as '--pal-quit-on-stop' is enabled.\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "q\n"

        # Logic to automatically move up from internal PDB frames
        is_in_simplest_pal_frame = False
        if pdb_prompt_present:
            # Check if the current PDB frame points to a file within simplest_pal.py
            for line in current_buffered_output.splitlines():
                # PDB output typically shows the current line with a '>' prefix
                if line.strip().startswith('>') and os.path.basename(__file__) in line:
                    is_in_simplest_pal_frame = True
                    break
        
        # If PDB is in an internal simplest_pal.py frame, automatically send 'u' to move up
        if is_in_simplest_pal_frame:
            log_msg = "PDB Automation (readline): In internal PDB frame. Auto-sending 'u'.\n"
            self._log_to_file(log_msg)
            self._print_to_console(log_msg)
            return "u\n" # Move up one frame

        # --- Manual User Input Logic ---
        # If PDB is displaying a prompt and no automation condition is met, wait for user input
        if pdb_prompt_present:
            log_msg = "PDB Automation (readline): Waiting for manual user input.\n"
            self._log_to_file(log_msg)
            # Read command directly from original stdin (blocking read, robust against Ctrl-C)
            user_command = self.original_stdin.readline()
            if not user_command:
                # If EOF (e.g., input stream closed), send a quit command to PDB
                self._log_to_file("PDB Automation (readline): EOF detected on stdin, sending 'q'.\n")
                return "q\n"
            self._log_to_file(f"PDB Automation (readline): User input received: {repr(user_command.strip())}\n")
            return user_command
        
        # If no PDB prompt, return an empty string. This path should ideally not be reached
        # if PDB is consistently interacting.
        return "" 

    def enter_debugger_hook(self):
        """
        Hook called when a PDB debugger session becomes active.
        Sets the internal flag `is_debugging`.
        """
        self.is_debugging.set()
        self._log_to_file("PDB Automation: Debugger session activated.\n")
        self._print_to_console("PDB Automation: Debugger session activated.\n")

    def exit_debugger_hook(self):
        """
        Hook called when a PDB debugger session becomes inactive.
        Clears the internal flag `is_debugging`.
        """
        self.is_debugging.clear()
        self._log_to_file("PDB Automation: Debugger session deactivated.\n")
        self._print_to_console("PDB Automation: Debugger session deactivated.\n")

    def get_output(self):
        """
        Retrieves all accumulated buffered output and then clears the buffer.
        """
        output = self.output_buffer.getvalue()
        self.output_buffer.truncate(0)
        self.output_buffer.seek(0)
        return output

    def restore_io(self):
        """
        Restores the original `sys.stdin`, `sys.stdout`, and `sys.stderr` streams.
        Also prints a confirmation message about the log file.
        """
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self._print_to_console(f"\nPDB session log saved to '{self.log_file}'.\n")

def simplest_pal_main():
    """
    Main function for Simplest P.A.L. (PDB Automation Layer).
    This function parses command-line arguments, sets up the PDB automation
    system, and runs the target Python script under PDB.
    """
    parser = argparse.ArgumentParser(description="A PDB debugger automation layer designed for AI integration.")
    parser.add_argument("script", help="Path to the Python script to be run and debugged.")
    parser.add_argument("--pal-log", default=DEFAULT_LOG_FILE, help=f"Specifies the PDB session log file (default: {DEFAULT_LOG_FILE})")
    parser.add_argument("--pal-quit-on-stop", default=False, action='store_true', 
                        help="Automatically quits the debugger if it stops without an explicit 'continue' or user input.")
    args, remaining_args = parser.parse_known_args()

    original_stdin, original_stdout, original_stderr = sys.stdin, sys.stdout, sys.stderr
    pdb_auto = PdbAutomation(original_stdin, original_stdout, original_stderr, args.pal_log, args.pal_quit_on_stop)

    # Initialize PDB instance with the custom I/O handler
    pal_debugger = pdb.Pdb(stdin=pdb_auto, stdout=pdb_auto)

    def set_trace_with_hooks(frame=None):
        """
        Custom `pdb.set_trace` function that includes hooks for `PdbAutomation`.
        Ensures the `PdbAutomation` instance is notified when PDB activates/deactivates.
        """
        pdb_auto.enter_debugger_hook()
        # Use the provided 'frame' directly, as it's the intended breakpoint location.
        # This is typically the user's code or the point in jrf_pdb_agent_lib.py
        # where pdb.set_trace() was originally called. The PdbAutomation.readline
        # method will handle stepping up if PDB still lands in an internal frame.
        pal_debugger.set_trace(frame) 
        pdb_auto.exit_debugger_hook()
    
    # Override the standard pdb.set_trace with our custom hooked version
    pdb.set_trace = set_trace_with_hooks

    pdb_auto._print_to_console(f"Simplest P.A.L.: Running target script: '{args.script}'\n")
    sys.argv = [args.script] + remaining_args
    
    # Add the directory of the target script to sys.path to resolve local imports (e.g., jrf_pdb_agent_lib.py)
    script_dir = os.path.dirname(os.path.abspath(args.script))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir) # Insert at the beginning to prioritize local modules

    script_completed = False
    script_force_quit = False # Flag to indicate if the script was explicitly quit (e.g., via bdb.BdbQuit)
    try:
        # Main loop to repeatedly run the target script until completion or explicit quit
        while not script_completed:
            try:
                runpy.run_path(args.script, run_name="__main__")
                script_completed = True # Script finished without PDB stopping it
                pdb_auto._print_to_console("Simplest P.A.L.: Target script execution completed normally.\n")
            except bdb.BdbQuit:
                # This exception is raised when 'q' is entered in PDB, indicating an explicit quit
                script_completed = True
                script_force_quit = True
                pdb_auto._print_to_console("Simplest P.A.L.: PDB session explicitly quit.\n")
            except Exception as e:
                # Catch any other exceptions from the target script
                pdb_auto._print_to_console(f"Simplest P.A.L.: An exception occurred: {e}\n")
                traceback.print_exc(file=pdb_auto) # Print full stack trace to the log file
                
                # If PDB is not active after the exception, it means the script crashed outside PDB control
                if not pdb_auto.is_debugging.is_set():
                    pdb_auto._print_to_console("Simplest P.A.L.: Unhandled exception in target script, stopping.\n")
                    script_completed = True
                else:
                    # If PDB is active, the exception was caught within a PDB session
                    pdb_auto._print_to_console("Simplest P.A.L.: Exception caught by PDB. Manual intervention may be required.\n")
            
            # If the debugger is still active (e.g., due to 'c' in a nested session)
            # and not explicitly quit, then the script is not truly "completed" from P.A.L.'s perspective.
            if pdb_auto.is_debugging.is_set() and not script_force_quit:
                script_completed = False # Loop again to re-enter PDB or continue script

            time.sleep(IO_POLL_INTERVAL) # Small delay to prevent busy-waiting

    finally:
        # Final cleanup: Ensure debugger is deactivated, flush any remaining output, and restore original I/O
        if pdb_auto.is_debugging.is_set():
            pdb_auto.exit_debugger_hook()
        remaining_output = pdb_auto.get_output()
        if remaining_output:
            pdb_auto._print_to_console(remaining_output)
        pdb_auto.restore_io()

if __name__ == "__main__":
    simplest_pal_main()
