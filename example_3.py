#!/usr/bin/python3
__version__ = '0.0.3' # Time-stamp: <2025-06-14T02:36:19Z>

import jrf_pdb_agent_lib as pal
from textwrap import dedent as d_py
from textwrap import dedent as d_md
import time

pal.login()

x = 42
r = pal.do(d_md("Do something good."),
           current_code = d_py("""\
               pal.do('Multiply 2',current_code='x=x*2')
               pal.do('Minus 1',current_code='x=x-1')
               xpal.RESULT = x  # Syntax Error!
           """))

print(r)

time.sleep(10) # You may press 'Ctrl-c'.

pal.consult_human()
