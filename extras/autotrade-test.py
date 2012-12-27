import sys
sys.path.append('..')
sys.path.append('.')

from armoryengine import *
import connector

import autotrade
import colortools

connector.init()

wltfile  = CLI_ARGS[0]
if not os.path.exists(wltfile):
   print 'Wallet file was not found: %s' % wltfile

wlt  = PyBtcWallet().readWalletFile(wltfile)
connector.register_wallet(wlt)

in_addr = 'my9NkN8ztUUgXjHin16rV4V4dFm2U6a6dq'
accum_addr = 'mif84DfZ1mjheR19AES6qu6qHwh74PzjNZ'
out_addr = 'moBXS6E2TWKLfNBKKu4MjHeWV2Q4cdqtVN'
colorid = '26546d600e1a6a278eba2170559afe415ddcdd88'
rate = 0.001

at = autotrade.AutoTrade(wlt)
at.initAddresses(in_addr, accum_addr, out_addr)
coloridx = colortools.find_color_index(colorid)
at.initConversion(-1, coloridx, rate)

def runqqq():
    print wlt.getBalanceX(-2)
    at.check_and_trade()
    print wlt.getBalanceX(-2)
    #at.check_and_trade() # twice, to be sure
   
connector.run(runqqq)
