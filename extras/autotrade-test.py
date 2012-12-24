import sys
sys.path.append('..')
sys.path.append('.')

from armoryengine import *

import autotrade
import colortools

wlt = None

wltfile  = CLI_ARGS[0]

if not os.path.exists(wltfile):
   print 'Wallet file was not found: %s' % wltfile

BDM_LoadBlockchainFile()

wlt  = PyBtcWallet().readWalletFile(wltfile)
TheBDM.registerWallet( wlt.cppWallet )

in_addr = 'my9NkN8ztUUgXjHin16rV4V4dFm2U6a6dq'
accum_addr = 'mif84DfZ1mjheR19AES6qu6qHwh74PzjNZ'
out_addr = 'moBXS6E2TWKLfNBKKu4MjHeWV2Q4cdqtVN'
colorid = '26546d600e1a6a278eba2170559afe415ddcdd88'
rate = 1.0

at = autotrade.AutoTrade(None, wlt)
at.initAddresses(in_addr, accum_addr, out_addr)
coloridx = colortools.find_color_index(colorid)
at.initConversion(-1, colorid, rate)

def runqqq():
    at.check_and_trade()
    at.check_and_trade() # twice, to be sure



from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet.defer import Deferred
from twisted.internet import reactor

def restart():
    print "RESTART"

def madeConnect():
    print "made connect"
    runqqq()

btcNetFactory = ArmoryClientFactory(func_madeConnect=madeConnect,
                                    func_loseConnect=restart)


reactor.callWhenRunning(reactor.connectTCP, '127.0.0.1', BITCOIN_PORT, \
                            btcNetFactory)

reactor.run()

   
