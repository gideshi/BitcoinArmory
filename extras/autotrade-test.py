import sys
sys.path.append('..')
sys.path.append('.')

from armoryengine import *

import autotrade
import colortools

from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet.defer import Deferred
from twisted.internet import reactor


wlt = None
btcNetFactory = None

class FakeMain:
    def broadcastTransaction(self, tx):
        print "broadcast transaction"
        btcNetFactory.sendTx(tx)
        TheBDM.addNewZeroConfTx(tx.serialize(), long(RightNow()), True)
        TheBDM.rescanWalletZeroConf(wlt.cppWallet)

engine_set_main(FakeMain())


wltfile  = CLI_ARGS[0]

if not os.path.exists(wltfile):
   print 'Wallet file was not found: %s' % wltfile

BDM_LoadBlockchainFile()

mempoolfile = os.path.join(ARMORY_HOME_DIR,'mempool.bin')
TheBDM.enableZeroConf(mempoolfile)


wlt  = PyBtcWallet().readWalletFile(wltfile)
TheBDM.registerWallet( wlt.cppWallet )



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

def restart():
    print "RESTART"

def made_connect():
    print "made connect"

def after_handshake(proto):
    print "after handshake"
    runqqq()

def newtx(tx):
    print "got new tx:"
    tx.pprint()
    print wlt.getBalanceX(-2)


btcNetFactory = ArmoryClientFactory(def_handshake=after_handshake,
                                    func_madeConnect=made_connect,
                                    func_newTx=newtx,
                                    func_loseConnect=restart)


reactor.callWhenRunning(reactor.connectTCP, '127.0.0.1', BITCOIN_PORT, \
                            btcNetFactory)

reactor.run()

   
