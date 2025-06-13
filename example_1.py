#!/usr/bin/python3
__version__ = '0.0.1' # Time-stamp: <2025-06-12T20:05:52Z>

import jrf_pdb_agent_lib as pal
import textwrap

pal.login()

x = 42

r = pal.do("Do something good.",
           current_code = textwrap.dedent("""\
               pal.do('Multiply 2',current_code='x=x*2')
               pal.do('Minus 1',current_code='x=x-1')
               pal.RESULT = x
           """))

print(r)

