from twisted.internet.protocol import Protocol, ClientFactory
from twisted.internet.defer import Deferred
from twisted.internet import reactor

from armoryengine import *


btcNetFactory = None

class ConMain:
    def __init__(self):
        self.wallets = []
    def addWallet(self, wallet):
        self.wallets.append(wallet)
    def broadcastTransaction(self, tx):
        btcNetFactory.sendTx(tx)
        TheBDM.addNewZeroConfTx(tx.serialize(), long(RightNow()), True)
        for w in self.wallets:
            TheBDM.rescanWalletZeroConf(w.cppWallet)

def init():
    engine_set_main(ConMain())
    BDM_LoadBlockchainFile()
    mempoolfile = os.path.join(ARMORY_HOME_DIR,'mempool.bin')
    TheBDM.enableZeroConf(mempoolfile)

def register_wallet(wlt):
   get_main().addWallet(wlt)
   TheBDM.registerWallet( wlt.cppWallet )

def lost():
    print "lost"

def made_connect():
    print "made connect"


def newtx(tx):
    print "got new tx:"
    tx.pprint()

def run(run_after_handshake=None):
    global btcNetFactory

    def after_handshake(proto):
        print "after handshake"
        if run_after_handshake:
            run_after_handshake()

    btcNetFactory = ArmoryClientFactory(def_handshake=after_handshake,
                                        func_madeConnect=made_connect,
                                        func_newTx=newtx,
                                        func_loseConnect=lost)

    reactor.callWhenRunning(reactor.connectTCP, '127.0.0.1', BITCOIN_PORT, \
                                btcNetFactory)

    reactor.run()

